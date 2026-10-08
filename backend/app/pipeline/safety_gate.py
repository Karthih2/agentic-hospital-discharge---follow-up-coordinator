"""Safety gate. Fixed rules, NOT AI. Same input, same answer, every time.

Input item (dict): type, title, source_line, confidence, due_date, due_date_text, date_ambiguous,
doctor_name, specialty, medicine{name,dose,timing,duration,special}, instruction, source_found.
Output: list of flags {field, reason_code, note}. Empty list = clean.
"""
import re
from collections import defaultdict

from app.core.config import settings
from app.pipeline.dates import VAGUE

QUESTION = re.compile(r"\b(what (should|do|can|must) (i|we) do|what if|should i|can i)\b", re.I)
SYMPTOM_COND = re.compile(r"\bif (you|i|he|she|they) (feel|experience|notice|get)\b", re.I)
CHANGE = re.compile(r"\b(stop(ped|ping)?|chang\w+|discontinu\w+|increas\w+|reduc\w+|decreas\w+|switch\w*|replac\w+|"
                    r"skip\w*|double|halve|taper\w*)\b", re.I)
MED_WORDS = re.compile(r"\b(tab|tablet|cap|capsule|syrup|injection|inj|mg|ml|dose|medicine|medication|drug)s?\b", re.I)
NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _flag(field, code, note=""):
    return {"field": field, "reason_code": code, "note": note}


def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _missing(item) -> list[dict]:
    t, f = item["type"], []
    med = item.get("medicine") or {}
    no_date = item.get("due_date") is None and not item.get("date_ambiguous")
    if t == "appointment":
        if no_date:
            f.append(_flag("due_date", "MISSING_DATE"))
        if _blank(item.get("doctor_name")) and _blank(item.get("specialty")):
            f.append(_flag("doctor_name", "MISSING_DOCTOR"))
    elif t == "test":
        if _blank(item.get("title")):
            f.append(_flag("title", "UNCATEGORISED", "test name missing"))
        if no_date:
            f.append(_flag("due_date", "MISSING_DATE"))
    elif t == "referral":
        if _blank(item.get("specialty")):
            f.append(_flag("specialty", "MISSING_DOCTOR"))
    elif t == "medicine":
        if _blank(med.get("name")):
            f.append(_flag("medicine.name", "UNCATEGORISED", "medicine name missing"))
        for key, code in (("dose", "MISSING_DOSE"), ("timing", "MISSING_TIMING"), ("duration", "MISSING_DURATION")):
            if _blank(med.get(key)):
                f.append(_flag(f"medicine.{key}", code))
    elif t in ("care_instruction", "warning_sign"):
        if _blank(item.get("instruction")):
            f.append(_flag("instruction", "UNCATEGORISED", "instruction text missing"))
    elif t == "date":
        if _blank(item.get("due_date_text")) and item.get("due_date") is None:
            f.append(_flag("due_date", "MISSING_DATE"))
    return f


def _ambiguous_date(item, doctor_reviewed) -> list[dict]:
    med = item.get("medicine") or {}
    texts = [item.get("due_date_text") or ""]
    if item["type"] == "medicine":
        texts += [med.get("duration") or "", med.get("timing") or ""]
        if not doctor_reviewed:
            texts.append(item.get("source_line") or "")
    if item.get("date_ambiguous") or any(VAGUE.search(x) for x in texts):
        return [_flag("due_date", "AMBIGUOUS_DATE")]
    return []


def _symptom_question(item) -> list[dict]:
    text = item.get("source_line") or ""
    if QUESTION.search(text):
        return [_flag("item", "SYMPTOM_QUESTION")]
    # A plain warning sign ("Seek care if chest pain occurs") is NOT flagged; it is shown as an alert.
    if item["type"] != "warning_sign" and SYMPTOM_COND.search(text):
        return [_flag("item", "SYMPTOM_QUESTION")]
    return []


def _medicine_change(item) -> list[dict]:
    text = item.get("source_line") or ""
    if (item["type"] == "medicine" or MED_WORDS.search(text)) and CHANGE.search(text):
        return [_flag("item", "MEDICINE_CHANGE")]
    return []


def _low_confidence(item) -> list[dict]:
    return [_flag("item", "LOW_CONFIDENCE", f"{item.get('confidence', 0):.2f}")] \
        if item.get("confidence", 0) < settings.confidence_threshold else []


def _grounding(item) -> list[dict]:
    f = []
    if not item.get("source_found", False):
        f.append(_flag("source_line", "SOURCE_NOT_FOUND"))
    if item["type"] == "medicine":  # a dose or duration number must appear in the source line
        src = set(NUMBER.findall(item.get("source_line") or ""))
        med = item.get("medicine") or {}
        for k in ("dose", "timing", "duration"):
            if any(n not in src for n in NUMBER.findall(med.get(k) or "")):
                f.append(_flag(f"medicine.{k}", "SOURCE_NOT_FOUND", "number not in source line"))
    return f


def run_gate(item: dict, doctor_reviewed: bool = False) -> list[dict]:
    """doctor_reviewed=True re-checks a doctor's correction: only completeness and date clarity are re-run,
    because the doctor has already judged the source text itself."""
    flags = _missing(item) + _ambiguous_date(item, doctor_reviewed)
    if not doctor_reviewed:
        flags += _symptom_question(item) + _medicine_change(item) + _low_confidence(item) + _grounding(item)
    seen, out = set(), []
    for fl in flags:
        k = (fl["field"], fl["reason_code"])
        if k not in seen:
            seen.add(k)
            out.append(fl)
    return out


def conflict_flags(items: list[dict]) -> dict[int, list[dict]]:
    """Same medicine twice with a different dose or timing. Flags every item involved."""
    groups = defaultdict(list)
    for i, it in enumerate(items):
        if it["type"] == "medicine" and not _blank((it.get("medicine") or {}).get("name")):
            groups[it["medicine"]["name"].strip().casefold()].append(i)
    out = {}
    for idxs in groups.values():
        sigs = {tuple((items[i]["medicine"].get(k) or "").strip().casefold() for k in ("dose", "timing"))
                for i in idxs}
        if len(sigs) > 1:
            for i in idxs:
                out[i] = [_flag("item", "MEDICINE_CONFLICT")]
    return out


def mention_flags(items: list[dict], lines: list[str]) -> dict[int, list[dict]]:
    """A medicine whose name appears in ANOTHER instruction line that talks about changing it (an injected
    'change the dose' line, or a second order). The medicine item is flagged; nothing is applied."""
    out = {}
    own = [(it.get("source_line") or "").casefold() for it in items]
    for i, it in enumerate(items):
        name = ((it.get("medicine") or {}).get("name") or "").strip().casefold()
        if it["type"] != "medicine" or len(name) < 3:
            continue
        for line in lines:
            low = line.casefold()
            mine = own[i]  # only the medicine's OWN line is exempt; an injected or second order on any other line counts
            if re.search(rf"\b{re.escape(name)}\b", low) and CHANGE.search(line) \
                    and not (mine and (low in mine or mine in low)):
                out[i] = [_flag("item", "MEDICINE_CONFLICT", "another line mentions a change to this medicine")]
                break
    return out
