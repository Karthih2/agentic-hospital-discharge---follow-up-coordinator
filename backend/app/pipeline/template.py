"""Hospital discharge summary template, read by CODE (no AI). Verbatim header facts, diagnoses, and the
completeness check. Nothing here explains or rewrites a diagnosis."""
import re

HEADER_KEYS = {"Date of Admission": "admission_date", "Attending Physician": "attending_physician",
               "PCP": "pcp", "Discharge Disposition": "disposition"}
DIAGNOSIS_KEYS = {"Admission Diagnosis": "admission", "Discharge Diagnosis": "discharge",
               "Secondary Diagnoses": "secondary"}
BAD_PCP = re.compile(r"^\s*(out of town|not recorded|none|n/?a|unknown|nil|-+)?\s*\.?\s*$", re.I)
NOTICE_TEXT = {
    "PCP_MISSING": "The summary has no usable primary care doctor (PCP).",
    "FOLLOWUP_NO_DATE": "A follow-up appointment has no date.",
    "MEDICINE_NO_DOSE": "A medicine line has no dose.",
    "MEDICINE_NO_ROUTE": "A medicine line has no route.",
}


def _line_value(raw: str, label: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(label)}\s*:\s*(.*)$", raw, re.M | re.I)
    return m.group(1).strip() if m else None


def parse(raw: str) -> dict:
    """{'header': {admission_date, attending_physician, pcp, disposition}, 'diagnoses': {admission, discharge, secondary}}.
    Values are copied from the text exactly. Missing labels give None."""
    return {"header": {v: _line_value(raw, k) for k, v in HEADER_KEYS.items()},
            "diagnoses": {v: _line_value(raw, k) for k, v in DIAGNOSIS_KEYS.items()}}


def pcp_ok(pcp: str | None) -> bool:
    return bool(pcp) and not BAD_PCP.match(pcp) and not re.search(r"\bout of town\b|\bnot recorded\b", pcp, re.I)


def completeness(header: dict, items: list[dict]) -> list[dict]:
    """Quiet notices for the doctor and admin. They are not tasks and never block the plan.
    items: gate items (after dates were resolved). Returns [{code, line}] where line is the source line or None."""
    out = []
    if not pcp_ok(header.get("pcp")):
        out.append({"code": "PCP_MISSING", "line": None})
    for it in items:
        if it["type"] == "appointment" and it.get("due_date") is None:
            out.append({"code": "FOLLOWUP_NO_DATE", "line": it["source_line"]})
        if it["type"] == "medicine":
            med = it.get("medicine") or {}
            if not (med.get("dose") or "").strip():
                out.append({"code": "MEDICINE_NO_DOSE", "line": it["source_line"]})
            if not (med.get("route") or "").strip():
                out.append({"code": "MEDICINE_NO_ROUTE", "line": it["source_line"]})
    return out


# ---- coverage: every actionable line must be accounted for, so the model cannot silently drop one
ACTION_SECTIONS = ("Pending Lab or Test Results", "Immunizations Given During Admission", "Diet",
                   "Discharge Medications", "Discharge Instructions", "Follow-up Appointments")
_HEAD = re.compile(r"^\s*([A-Za-z][A-Za-z /-]{1,60}?)\s*:\s*(.*)$")
_NUM = re.compile(r"^\s*\d+[.)]\s+(.*\S)\s*$")


def actionable_lines(raw: str) -> list[tuple[str, str]]:
    """(section, line) for every numbered line in the actionable sections, copied from the text."""
    out, cur = [], None
    for ln in raw.splitlines():
        m = _HEAD.match(ln)
        if m and not re.match(r"^\s*\d", ln):
            name = m.group(1).strip()
            cur = next((s for s in ACTION_SECTIONS if s.casefold() == name.casefold()), None)
            continue
        n = _NUM.match(ln)
        if cur and n:
            out.append((cur, n.group(1)))
    return out


def _norm(s: str) -> str:
    return " ".join((s or "").casefold().split()).strip(" .")


def uncovered(lines: list[tuple[str, str]], sources: list[str]) -> list[str]:
    """Lines no extracted item accounts for. These become visible Needs Review items.
    Exempt: Diet lines (plain statements) and immunizations already given (history, not a task)."""
    have = [_norm(s) for s in sources if s]
    out = []
    for section, line in lines:
        n = _norm(line)
        if section == "Diet" or re.fullmatch(r"(none|nil|n/?a|-+)", n):
            continue
        if section.startswith("Immunizations") and re.search(r"\bgiven\b", n):
            continue
        if not any(n in h or h in n for h in have):
            out.append(line)
    return out
