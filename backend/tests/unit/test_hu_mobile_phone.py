# backend/tests/unit/test_hu_mobile_phone.py
# Feladat: Magyar mobilszám normalizálás és validáció unit tesztek.
# Sárközi Mihály - 2026.07.18

from apps.traffic.domain.hu_mobile_phone import is_valid_hu_mobile, normalize_hu_mobile


def test_normalize_hu_mobile_accepts_common_forms() -> None:
    assert normalize_hu_mobile("+36 20 123 4567") == "+36201234567"
    assert normalize_hu_mobile("06-30-123-4567") == "+36301234567"
    assert normalize_hu_mobile("70/1234567") == "+36701234567"


def test_is_valid_hu_mobile_rejects_landline_and_short() -> None:
    assert is_valid_hu_mobile("+36201234567") is True
    assert is_valid_hu_mobile("061234567") is False
    assert is_valid_hu_mobile("123") is False
    assert is_valid_hu_mobile("+3611234567") is False
