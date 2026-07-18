# backend/tests/unit/test_app_settings_billing_validator.py
# Feladat: BillingSettingsValidator cég/HU adószám validációs szabályainak unit tesztje.
# Sárközi Mihály - 2026.05.29

from __future__ import annotations

import pytest
from fastapi import HTTPException

from apps.settings.service.billing_validator import BillingSettingsUpdate, BillingSettingsValidator

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]

VALID_HU_TAX = "12892312-1-42"


def test_validator_accepts_valid_company_payload() -> None:
    validator = BillingSettingsValidator()
    payload = validator.validate(
        BillingSettingsUpdate(
            billing_customer_type="company",
            billing_company_name="Acme Kft.",
            billing_tax_id=VALID_HU_TAX,
            billing_country="DE",
            billing_postal_code="1111",
            billing_city="Budapest",
            billing_address_line="Fo utca 1.",
        )
    )
    assert payload.billing_customer_type == "company"
    assert payload.billing_country == "HU"
    assert payload.billing_tax_id == VALID_HU_TAX
    assert payload.billing_full_name == ""


def test_validator_rejects_private_payload() -> None:
    validator = BillingSettingsValidator()
    with pytest.raises(HTTPException) as exc:
        validator.validate(
            BillingSettingsUpdate(
                billing_customer_type="private",
                billing_full_name="Teszt Elek",
                billing_country="HU",
                billing_postal_code="1111",
                billing_city="Budapest",
                billing_address_line="Fo utca 1.",
            )
        )
    assert exc.value.status_code == 422
    assert "company" in str(exc.value.detail).lower()


def test_validator_rejects_missing_required_fields() -> None:
    validator = BillingSettingsValidator()
    with pytest.raises(HTTPException) as exc:
        validator.validate(
            BillingSettingsUpdate(
                billing_customer_type="company",
                billing_company_name="Acme Kft.",
                billing_country="HU",
                billing_city="Budapest",
            )
        )
    assert exc.value.status_code == 422


def test_validator_rejects_invalid_hu_tax_id() -> None:
    validator = BillingSettingsValidator()
    with pytest.raises(HTTPException) as exc:
        validator.validate(
            BillingSettingsUpdate(
                billing_customer_type="company",
                billing_company_name="Acme Kft.",
                billing_tax_id="HU12345678",
                billing_country="HU",
                billing_postal_code="1111",
                billing_city="Budapest",
                billing_address_line="Fo utca 1.",
            )
        )
    assert exc.value.status_code == 422
    assert "tax" in str(exc.value.detail).lower()
