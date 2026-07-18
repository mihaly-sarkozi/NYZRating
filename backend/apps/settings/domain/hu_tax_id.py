# backend/apps/settings/domain/hu_tax_id.py
# Feladat: Magyar adószám formátum- és ellenőrzőszám-validáció (belföldi 8-1-2).
# Sárközi Mihály - 2026.07.18

from __future__ import annotations

import re

_WEIGHTS = (9, 7, 3, 1, 9, 7, 3, 1)
FIXED_BILLING_COUNTRY = "HU"


def _digits_only(value: str | None) -> str:
    compact = re.sub(r"[\s.]", "", str(value or "")).upper()
    if compact.startswith("HU"):
        compact = compact[2:]
    return re.sub(r"\D", "", compact)[:11]


def normalize_hu_tax_id(value: str | None) -> str:
    digits = _digits_only(value)
    if not digits:
        return ""
    if len(digits) <= 8:
        return digits
    if len(digits) == 9:
        return f"{digits[:8]}-{digits[8:]}"
    return f"{digits[:8]}-{digits[8]}-{digits[9:]}"


def _checksum_ok(eight_digits: str) -> bool:
    if not re.fullmatch(r"\d{8}", eight_digits):
        return False
    total = sum(weight * int(digit) for weight, digit in zip(_WEIGHTS, eight_digits, strict=True))
    return total % 10 == 0


def is_valid_hu_tax_id(value: str | None) -> bool:
    digits = _digits_only(value)
    if len(digits) != 11:
        return False
    return _checksum_ok(digits[:8])


__all__ = ["FIXED_BILLING_COUNTRY", "is_valid_hu_tax_id", "normalize_hu_tax_id"]
