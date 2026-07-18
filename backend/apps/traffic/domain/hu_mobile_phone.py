# backend/apps/traffic/domain/hu_mobile_phone.py
# Feladat: Magyar mobiltelefonszám formátum normalizálása és validációja.
# Sárközi Mihály - 2026.07.18

from __future__ import annotations

import re

_MOBILE_PREFIXES = ("20", "30", "31", "50", "70")


def normalize_hu_mobile(value: str | None) -> str:
    """Normalizál magyar mobil számot +36XXXXXXXXX formára, vagy üres stringet ad."""

    raw = re.sub(r"[\s./()-]", "", str(value or ""))
    if not raw:
        return ""
    if raw.startswith("00"):
        raw = f"+{raw[2:]}"
    if raw.startswith("+"):
        digits = re.sub(r"\D", "", raw[1:])
    else:
        digits = re.sub(r"\D", "", raw)
        if digits.startswith("06"):
            digits = f"36{digits[2:]}"
        elif digits.startswith("6") and len(digits) == 10:
            digits = f"3{digits}"
        elif len(digits) == 9 and digits[:2] in _MOBILE_PREFIXES:
            digits = f"36{digits}"
    if not digits.startswith("36"):
        return ""
    return f"+{digits}"


def is_valid_hu_mobile(value: str | None) -> bool:
    """Elfogad: +36201234567, 06 20 123 4567, 20/123-4567 (összesen 9 jegy a 36 után)."""

    normalized = normalize_hu_mobile(value)
    if not re.fullmatch(r"\+36\d{9}", normalized):
        return False
    local = normalized[3:]
    return local[:2] in _MOBILE_PREFIXES


def hu_mobile_validation_error(value: str | None) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("06"):
        local_len = len(digits) - 2
    elif digits.startswith("36"):
        local_len = len(digits) - 2
    else:
        local_len = len(digits)
    if local_len != 9:
        return (
            "Érvénytelen magyar mobilszám. "
            "Formátum: 06 XX XXX XXXX (11 számjegy), pl. 06201234567."
        )
    return "Érvénytelen magyar mobilszám. Csak 20/30/31/50/70-es előhívó fogadható el."


__all__ = ["hu_mobile_validation_error", "is_valid_hu_mobile", "normalize_hu_mobile"]
