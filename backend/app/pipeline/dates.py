"""Dates are resolved by code, never by the AI."""
import calendar
import math
import re
from dataclasses import dataclass
from datetime import date, timedelta

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
         "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}

VAGUE = re.compile(r"\b(soon|as advised|as needed|as directed|as required|when required|if required|when needed|"
                   r"prn|sos|shortly|some ?time)\b", re.I)
RECURRING = re.compile(r"\b(every|daily|weekly|hourly|each)\b", re.I)

_ABS = [
    (re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?[\s\-/]+([A-Za-z]{3,9})\.?,?[\s\-/]+(\d{4})\b"), "dmy_name"),
    (re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b"), "mdy_name"),
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b"), "dmy"),  # Indian order: day first
]
_REL = re.compile(r"(\d+|" + "|".join(WORDS) + r")\s*(hours?|hrs?|days?|weeks?|months?)\b", re.I)
_DAYN = re.compile(r"\bday\s+(\d+)\b", re.I)


@dataclass
class Resolved:
    date: date | None
    ambiguous: bool = False


def _mk(y, m, d):
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def parse_absolute(text: str) -> date | None:
    for rx, kind in _ABS:
        for m in rx.finditer(text):
            a, b, c = m.groups()
            if kind == "dmy_name" and b[:3].lower() in MONTHS:
                r = _mk(c, MONTHS[b[:3].lower()], a)
            elif kind == "mdy_name" and a[:3].lower() in MONTHS:
                r = _mk(c, MONTHS[a[:3].lower()], b)
            elif kind == "ymd":
                r = _mk(a, b, c)
            elif kind == "dmy":
                r = _mk(c, b, a)
            else:
                r = None
            if r:
                return r
    return None


def parse_discharge_date(text: str) -> date | None:
    for line in text.splitlines():
        i = line.lower().find("discharge")
        if i >= 0:
            d = parse_absolute(line[i:])  # Admitted 1 Nov, Discharged 5 Nov -> 5 Nov
            if d:
                return d
    return None


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def resolve(text: str | None, discharge: date | None) -> Resolved:
    if not text or not text.strip():
        return Resolved(None)
    t = text.strip()
    if VAGUE.search(t):
        return Resolved(None, True)
    if RECURRING.search(t):
        return Resolved(None)  # recurring: no single due date, not an error
    abs_d = parse_absolute(t)
    if abs_d:
        return Resolved(abs_d)
    low = t.lower()
    if discharge is None:
        return Resolved(None, True)
    if re.search(r"\b(today|on discharge)\b", low):
        return Resolved(discharge)
    if "tomorrow" in low:
        return Resolved(discharge + timedelta(days=1))
    if "next week" in low:
        return Resolved(discharge + timedelta(days=7))
    m = _DAYN.search(t)
    if m:
        return Resolved(discharge + timedelta(days=int(m.group(1))))
    m = _REL.search(t)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else WORDS[m.group(1).lower()]
        unit = m.group(2).lower()
        if unit.startswith("h"):
            return Resolved(discharge + timedelta(days=math.ceil(n / 24)))
        if unit.startswith("d"):
            return Resolved(discharge + timedelta(days=n))
        if unit.startswith("w"):
            return Resolved(discharge + timedelta(weeks=n))
        return Resolved(_add_months(discharge, n))
    return Resolved(None, True)


_TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b|\b([01]?\d|2[0-3]):([0-5]\d)\b", re.I)


def parse_time(text: str | None) -> tuple[int, int] | None:
    """'11:00 AM' -> (11, 0); '14:30' -> (14, 30). Code reads the time, the AI never does."""
    m = _TIME.search(text or "")
    if not m:
        return None
    if m.group(3):
        h, mi = int(m.group(1)) % 12, int(m.group(2) or 0)
        return (h + (12 if m.group(3).lower() == "pm" else 0), mi) if int(m.group(1)) <= 12 else None
    return int(m.group(4)), int(m.group(5))
