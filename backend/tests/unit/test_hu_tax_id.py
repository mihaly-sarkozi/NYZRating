# backend/tests/unit/test_hu_tax_id.py
# Feladat: Magyar adószám normalizálás és ellenőrzőszám unit tesztek.
# Sárközi Mihály - 2026.07.18

from apps.settings.domain.hu_tax_id import is_valid_hu_tax_id, normalize_hu_tax_id


def test_normalize_hu_tax_id_uses_domestic_format() -> None:
    assert normalize_hu_tax_id("12892312") == "12892312"
    assert normalize_hu_tax_id("12892312-1-42") == "12892312-1-42"
    assert normalize_hu_tax_id("HU-12892312") == "12892312"
    assert normalize_hu_tax_id("hu12892312142") == "12892312-1-42"


def test_is_valid_hu_tax_id_requires_full_domestic_format() -> None:
    assert is_valid_hu_tax_id("12892312-1-42") is True
    assert is_valid_hu_tax_id("12892312142") is True
    assert is_valid_hu_tax_id("HU12892312") is False
    assert is_valid_hu_tax_id("12892312") is False
    assert is_valid_hu_tax_id("12892313-1-42") is False
    assert is_valid_hu_tax_id("123") is False
