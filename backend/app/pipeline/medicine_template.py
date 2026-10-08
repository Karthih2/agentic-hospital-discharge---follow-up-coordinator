"""Fixed medicine card. Values are copied from extraction. The AI never rewords them.
Labels (Dose, Timing...) come from constants.MEDICINE_LABELS, not from any model."""
from app.core.constants import MEDICINE_KEYS, MEDICINE_LABELS


def build_card(medicine: dict | None) -> dict:
    m = medicine or {}
    return {k: ((m.get(k) or "").strip() or None) for k in MEDICINE_KEYS}


def render(card: dict | None, lang: str) -> dict | None:
    """Card with its localized labels, in the fixed order."""
    if not card:
        return None
    labels = MEDICINE_LABELS.get(lang, MEDICINE_LABELS["en"])
    return {"rows": [{"label": labels[i], "key": k, "value": card.get(k)} for i, k in enumerate(MEDICINE_KEYS)]}


def spoken(card: dict, lang: str) -> str:
    """Text for the Listen button: the same fixed fields, read one by one."""
    labels = MEDICINE_LABELS.get(lang, MEDICINE_LABELS["en"])
    return ". ".join(f"{labels[i]}: {card[k]}" for i, k in enumerate(MEDICINE_KEYS) if card.get(k))
