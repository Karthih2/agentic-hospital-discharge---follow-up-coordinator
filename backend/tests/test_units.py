from datetime import date

import pytest

from app.pipeline import dates, safety_gate as g
from app.pipeline.simplify_agent import RewriteRejected, check, numbers
from app.core.security import crypto

D = date(2026, 11, 2)


def codes(item, **kw):
    base = {"type": "care_instruction", "title": "t", "source_line": "x", "confidence": 0.95, "source_found": True,
            "instruction": "do it", "due_date": None, "date_ambiguous": False}
    return {f["reason_code"] for f in g.run_gate({**base, **item}, **kw)}


# ---- dates
@pytest.mark.parametrize("text,expected", [
    ("in 2 weeks", date(2026, 11, 16)), ("Day 7", date(2026, 11, 9)), ("after 48 hours", date(2026, 11, 4)),
    ("12 Nov 2026", date(2026, 11, 12)), ("12/11/2026", date(2026, 11, 12)), ("2026-11-12", date(2026, 11, 12)),
    ("in a week", date(2026, 11, 9)), ("in 1 month", date(2026, 12, 2)), ("tomorrow", date(2026, 11, 3))])
def test_dates_resolve(text, expected):
    r = dates.resolve(text, D)
    assert r.date == expected and not r.ambiguous


@pytest.mark.parametrize("text", ["soon", "as advised", "as needed", "gibberish words"])
def test_dates_vague_is_ambiguous(text):
    r = dates.resolve(text, D)
    assert r.date is None and r.ambiguous


def test_relative_without_discharge_date_is_ambiguous():
    assert dates.resolve("in 2 weeks", None).ambiguous


def test_recurring_is_not_an_error():
    r = dates.resolve("every 48 hours", D)
    assert r.date is None and not r.ambiguous


# ---- safety gate, one test per rule
MED = {"name": "Metformin", "dose": "500 mg", "timing": "twice daily", "duration": "30 days"}


def med(**over):
    m = {**MED, **over}
    return {"type": "medicine", "medicine": m, "source_line": "Tab. Metformin 500 mg twice daily for 30 days"}


def test_clean_medicine_passes():
    assert codes(med()) == set()


@pytest.mark.parametrize("field,code", [("dose", "MISSING_DOSE"), ("timing", "MISSING_TIMING"),
                                        ("duration", "MISSING_DURATION")])
def test_missing_medicine_fields(field, code):
    assert codes(med(**{field: None})) == {code}  # only that field is flagged


def test_missing_date_and_doctor_on_appointment():
    assert codes({"type": "appointment"}) == {"MISSING_DATE", "MISSING_DOCTOR"}
    assert codes({"type": "appointment", "due_date": D, "specialty": "Cardiology"}) == set()


def test_ambiguous_date():
    assert codes({"type": "test", "due_date_text": "soon", "date_ambiguous": True}) == {"AMBIGUOUS_DATE"}


def test_symptom_question_flags_but_plain_warning_sign_does_not():
    assert "SYMPTOM_QUESTION" in codes({"source_line": "What should I do if I feel dizzy?"})
    assert codes({"type": "warning_sign", "source_line": "Seek immediate care if chest pain occurs."}) == set()
    assert "SYMPTOM_QUESTION" in codes({"type": "warning_sign", "source_line": "What should I do if pain returns?"})


@pytest.mark.parametrize("line", ["Stop Metformin after 3 days", "Increase the dose of the tablet", "Switch to Tab. X"])
def test_medicine_change(line):
    assert "MEDICINE_CHANGE" in codes({**med(), "source_line": line + " 500 mg 30 days"})


def test_non_medicine_change_words_are_fine():
    assert codes({"source_line": "Reduce salt intake and change wound dressing."}) == set()


def test_medicine_conflict():
    a = {"type": "medicine", "medicine": MED}
    b = {"type": "medicine", "medicine": {**MED, "dose": "1000 mg"}}
    assert set(g.conflict_flags([a, b])) == {0, 1}
    assert g.conflict_flags([a, dict(a)]) == {}


def test_low_confidence_boundary():
    assert "LOW_CONFIDENCE" in codes({"confidence": 0.69})
    assert "LOW_CONFIDENCE" not in codes({"confidence": 0.70})


def test_source_not_found_and_invented_dose():
    assert "SOURCE_NOT_FOUND" in codes({"source_found": False})
    assert "SOURCE_NOT_FOUND" in codes({**med(dose="1000 mg"), "source_line": "Tab. Metformin 500 mg twice daily 30 days"})


def test_vague_duration_in_source_line_is_ambiguous():
    assert "AMBIGUOUS_DATE" in codes({**med(), "source_line": "Tab. Metformin 500 mg twice daily 30 days as advised"})


def test_doctor_review_rechecks_only_completeness():
    item = {**med(dose=None)}
    assert codes(item, doctor_reviewed=True) == {"MISSING_DOSE"}
    assert codes(med(), doctor_reviewed=True) == set()


# ---- rewrite checks
def test_rewrite_keeps_numbers():
    check("Change dressing every 48 hours", "Change the dressing every 48 hours.", {"ta": "48 மணி", "hi": "४८ घंटे"})
    with pytest.raises(RewriteRejected):
        check("Change dressing every 48 hours", "Change the dressing every day.", {})
    with pytest.raises(RewriteRejected):
        check("Change dressing every 48 hours", "Change it every 24 hours.", {})


def test_indic_digits_compare_equal():
    assert numbers("४८") == {"48"} and numbers("௪௮") == {"48"}


@pytest.mark.parametrize("bad", ["You should take two tablets 5", "This is a diagnosis of 5", "Stop taking it 5"])
def test_banned_patterns_blocked(bad):
    with pytest.raises(RewriteRejected):
        check("Take 5 days rest", bad, {})


def test_crypto_roundtrip_and_tamper():
    c = crypto.enc("Metformin 500 mg")
    assert c.startswith("v1:") and crypto.dec(c) == "Metformin 500 mg" and crypto.enc("a") != crypto.enc("a")
    assert crypto.dec_map(crypto.enc_map({"a": "x", "b": {"c": "y", "d": None}})) == {"a": "x", "b": {"c": "y", "d": None}}
    with pytest.raises(Exception):
        crypto.dec(c[:-4] + "AAAA")


def test_optional_languages_are_dropped_not_fatal():
    ok = check("Review in 2 weeks", "Review in 2 weeks.", {"ta": "2 வாரம்", "hi": "2 सप्ताह", "te": "వారం", "kn": "2 ವಾರ"})
    assert set(ok) == {"ta", "hi", "kn"}  # te lost its number, so it is dropped; the viewer sees English
    with pytest.raises(RewriteRejected):  # required language missing
        check("Review in 2 weeks", "Review in 2 weeks.", {"ta": "2 வாரம்", "te": "2 వారాలు"})


def test_rewrite_that_says_the_step_is_already_done_is_blocked():
    with pytest.raises(RewriteRejected):
        check("Lipid profile blood test on Day 10.", "A lipid profile blood test was done on Day 10.", {})
    check("Lipid profile blood test on Day 10.", "Have a lipid profile blood test on Day 10.", {"ta": "10", "hi": "10"})
