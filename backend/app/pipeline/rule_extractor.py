"""Rule-based extraction (code, no AI). The fallback that makes sure a draft plan is ALWAYS generated.

Used when no model is configured, the model call fails, or the model returns nothing usable. It reads the hospital
template sections line by line and fills the same ExtractedItem schema the AI agent returns, so the rest of the
pipeline (evidence check, dates, safety gate, planner) is identical. Every value is copied from the line itself;
nothing is invented. Lines outside the template get a low confidence, so the safety gate sends them to the doctor.
"""
import re

from app.pipeline.extraction_agent import ExtractedItem, MedicineFields, Outcome
from app.pipeline.template import ACTION_SECTIONS, actionable_lines

CONF_TEMPLATE = 0.85   # a line from a known section, parsed by pattern
CONF_GUESS = 0.55      # a free-text line: below the review threshold on purpose

_DATE = re.compile(
    r"\b(\d{1,2}(?:st|nd|rd|th)?[\s\-/]+[A-Za-z]{3,9}\.?,?[\s\-/]+\d{4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}|"
    r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4})\b")
_REL = re.compile(r"\b(?:in|within|after)\s+(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
                  r"\s*(?:hours?|days?|weeks?|months?)\b|\bday\s+\d+\b|\bnext week\b|\btomorrow\b", re.I)
_VAGUE = re.compile(r"\b(soon|as advised|as needed|as directed|when required|shortly)\b", re.I)
_TIME = re.compile(r"\b(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm))\b|\b([01]?\d|2[0-3]):[0-5]\d\b")
_PHONE = re.compile(r"(?:phone|ph|tel|call)\.?\s*:?\s*(\+?[\d][\d\s\-]{6,}\d)", re.I)
_DOCTOR = re.compile(r"\b(Dr\.?\s+[A-Z][A-Za-z.]*(?:\s+[A-Z][A-Za-z.]*)*)")
_WARN = re.compile(r"\b(seek (immediate |urgent )?(medical )?(care|help|attention)|go to (the )?(emergency|hospital|casualty)|"
                   r"call (an )?ambulance|return to (the )?hospital|come back (to the hospital|immediately))\b", re.I)
_DOSE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|µg|g|ml|units?|iu|drops?|puffs?|tablets?|capsules?)\b"
                   r"(?:\s*\([^)]*\))?(?:\s+in each nostril)?", re.I)
_ROUTE = re.compile(r"\b(by mouth|orally|under the skin|subcutaneous(?:ly)?|into the (?:vein|muscle)|intravenous(?:ly)?|"
                    r"in each nostril|into each nostril|on the skin|inhaled|by inhaler|in the eye|in each eye|rectally)\b", re.I)
_TIMING = re.compile(r"\b((?:up to )?(?:once|twice|three times|four times|\d+ times)\s+(?:daily|a day|a week|weekly)"
                     r"(?:\s+(?:at night|in the morning|at bedtime|in the evening))?|every \d+ hours|at bedtime|"
                     r"before feeds|at night|in the morning)\b", re.I)
_DURATION = re.compile(r"\bfor\s+(\d+\s*(?:days?|weeks?|months?|years?))\b|\b(long[- ]term|lifelong|indefinitely)\b", re.I)
_SPECIAL = re.compile(r"\b(after food|before food|with food|before breakfast|after breakfast|on an empty stomach|"
                      r"(?:when required|as needed|if needed)[^,.;]*|for fever[^,.;]*)", re.I)
_STOP = re.compile(r"^\s*(stop|discontinue|hold)\s+([A-Za-z][A-Za-z \-]+?)\s*\.?\s*$", re.I)
_FORMS = re.compile(r"\b(tablet|tab|capsule|cap|injection|inj|syrup|suspension|oral suspension|drops|oral drops|"
                    r"nasal drops|cream|ointment|inhaler)\b\.?", re.I)
_REFERRAL = re.compile(r"\b(refer\w*|physiotherap\w*|rehab\w*|dietitian|counsell?ing)\b", re.I)
_MED_HINT = re.compile(r"\b(tab|tablet|cap|capsule|syrup|injection|inj|mg|mcg|ml|units?|drops)\b", re.I)
_APPT_HINT = re.compile(r"\b(follow[- ]?up|review with|visit|appointment|see dr|clinic)\b", re.I)
_TEST_HINT = re.compile(r"\b(test|x-?ray|scan|ultrasound|mri|ct|ecg|echo|culture|report|blood|urine|swab|biopsy)\b", re.I)
_NUM_LINE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+(.*\S)\s*$")


def _date_text(line: str) -> str | None:
    for rx in (_DATE, _REL, _VAGUE):
        m = rx.search(line)
        if m:
            return m.group(0)
    return None


def _short(line: str, n: int = 60) -> str:
    t = re.split(r"[;.]\s|, (?=on |in |at |report)", line.strip(), maxsplit=1)[0].strip(" .")
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "…"


def _medicine(line: str) -> tuple[str, MedicineFields]:
    stop = _STOP.match(line)
    if stop:
        return stop.group(2).strip(), MedicineFields(name=stop.group(2).strip())
    dose = _DOSE.search(line)
    cut = min([m.start() for m in (dose, _FORMS.search(line)) if m] + [line.find(",") if "," in line else len(line)])
    name = line[:cut].strip(" ,.") or None
    route = _ROUTE.search(line)
    timing = _TIMING.search(line)
    dur = _DURATION.search(line)
    special = _SPECIAL.search(line)
    med = MedicineFields(
        name=name, dose=dose.group(0).strip() if dose else None, route=route.group(0) if route else None,
        timing=timing.group(0) if timing else None,
        duration=(dur.group(1) or dur.group(2)) if dur else None,
        special=special.group(0).strip(" ,.") if special else None)
    return name or _short(line, 40), med


def _appointment(line: str) -> dict:
    parts = [p.strip() for p in line.split(",")]
    doctor = specialty = location = None
    if parts and re.match(r"^Dr\.?\s", parts[0]):
        doctor = parts[0]
        if len(parts) > 1 and not re.search(r"\d", parts[1]):
            specialty = parts[1]
        loc = []
        for p in parts[2:]:
            if re.match(r"^(on|in|at)\b|\d", p, re.I) or _REFERRAL.search(p) and loc:
                break
            loc.append(p)
        location = ", ".join(loc) or None
    else:
        m = _DOCTOR.search(line)
        if m:
            doctor = m.group(1).rstrip(".,")
            rest = line[m.end():]
            sm = re.match(r"\s*,\s*([A-Z][A-Za-z ]+?)(?:[.,]|$)", rest)
            specialty = sm.group(1).strip() if sm else None
    t = _TIME.search(line)
    ph = _PHONE.search(line)
    typ = "referral" if _REFERRAL.search(line) and specialty and _REFERRAL.search(specialty or "") else "appointment"
    if "refer" in line.casefold():
        typ = "referral"
    title = f"{specialty} {'referral' if typ == 'referral' else 'follow-up'}" if specialty else (
        f"Follow-up with {doctor}" if doctor else _short(line))
    return {"type": typ, "title": title, "doctor_name": doctor, "specialty": specialty, "location": location,
            "due_time": t.group(0) if t else None, "phone": ph.group(1).strip() if ph else None,
            "due_date_text": _date_text(line)}


def _item(section: str | None, line: str) -> ExtractedItem | None:
    conf = CONF_TEMPLATE if section else CONF_GUESS
    sec = section or ""
    if sec.startswith("Immunizations"):
        if re.search(r"\bgiven\b", line, re.I) or re.fullmatch(r"(none|nil|n/?a|-+)\.?", line.strip(), re.I):
            return None
        return ExtractedItem(type="date", title=_short(line), source_line=line, due_date_text=_date_text(line),
                             instruction=line, confidence=conf)
    if re.fullmatch(r"(none|nil|n/?a|-+)\.?", line.strip(), re.I):
        return None
    if sec == "Pending Lab or Test Results" or (not section and _TEST_HINT.search(line) and not _MED_HINT.search(line)
                                                  and not _WARN.search(line)):
        return ExtractedItem(type="test", title=_short(line), source_line=line, due_date_text=_date_text(line),
                             instruction=line, confidence=conf)
    if sec == "Discharge Medications" or (not section and _MED_HINT.search(line) and not _WARN.search(line)):
        title, med = _medicine(line)
        return ExtractedItem(type="medicine", title=title, source_line=line, medicine=med, confidence=conf)
    if sec == "Follow-up Appointments" or (not section and _APPT_HINT.search(line) and not _WARN.search(line)):
        a = _appointment(line)
        return ExtractedItem(source_line=line, confidence=conf, **a)
    if _WARN.search(line):
        return ExtractedItem(type="warning_sign", title="Warning signs: " + _short(line, 40).lower(), source_line=line,
                             instruction=line, confidence=conf)
    return ExtractedItem(type="care_instruction", title=_short(line), source_line=line, instruction=line,
                         due_date_text=None, confidence=conf)


def discharge_date_text(raw: str) -> str | None:
    m = re.search(r"^\s*(?:Date of )?Discharge(?:d| date)?\s*(?:date)?\s*:?\s*(.+)$", raw, re.I | re.M)
    if m:
        d = _DATE.search(m.group(1))
        return d.group(0) if d else None
    return None


def extract(raw: str) -> Outcome:
    """Same Outcome shape as the AI agent. Template sections first; free numbered lines when there is no template."""
    lines = actionable_lines(raw)
    items: list[ExtractedItem] = []
    if lines:
        for section, line in lines:
            it = _item(section, line)
            if it:
                items.append(it)
    else:
        for ln in raw.splitlines():
            m = _NUM_LINE.match(ln)
            if m:
                it = _item(None, m.group(1))
                if it:
                    items.append(it)
    return Outcome(discharge_date_text=discharge_date_text(raw), items=items)


__all__ = ["extract", "ACTION_SECTIONS"]
