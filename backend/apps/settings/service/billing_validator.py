from __future__ import annotations

# backend/apps/settings/service/billing_validator.py
# Feladat: A settings billing adatok üzleti validációja és normalizálása külön szolgáltatásként.
# Sárközi Mihály - 2026.05.29

from dataclasses import dataclass

from fastapi import HTTPException

from apps.settings.domain.hu_tax_id import FIXED_BILLING_COUNTRY, is_valid_hu_tax_id, normalize_hu_tax_id


@dataclass(frozen=True)
class BillingSettingsUpdate:
    billing_customer_type: str | None = None
    billing_full_name: str | None = None
    billing_company_name: str | None = None
    billing_tax_id: str | None = None
    billing_address_line: str | None = None
    billing_postal_code: str | None = None
    billing_city: str | None = None
    billing_region: str | None = None
    billing_country: str | None = None


class BillingSettingsValidator:
    def __init__(
        self,
        *,
        eu_vat_validation_service=None,
        require_eu_vat_validation: bool = True,
    ) -> None:
        # eu_vat_validation_service megtartva a DI kompatibilitás miatt; egyelőre csak HU formátumot ellenőrzünk.
        _ = eu_vat_validation_service, require_eu_vat_validation

    def validate(self, payload: BillingSettingsUpdate) -> BillingSettingsUpdate:
        customer_type = (payload.billing_customer_type or "").strip() or "company"
        if customer_type != "company":
            raise HTTPException(status_code=422, detail="Only company billing is supported.")

        country = FIXED_BILLING_COUNTRY
        company_name = (payload.billing_company_name or "").strip()
        tax_id_raw = payload.billing_tax_id
        postal = (payload.billing_postal_code or "").strip()
        city = (payload.billing_city or "").strip()
        address = (payload.billing_address_line or "").strip()

        missing = [
            key
            for key, value in {
                "billing_company_name": company_name,
                "billing_tax_id": tax_id_raw,
                "billing_postal_code": postal,
                "billing_city": city,
                "billing_address_line": address,
            }.items()
            if not str(value or "").strip()
        ]
        if missing:
            raise HTTPException(status_code=422, detail="All company billing fields are required.")

        if not is_valid_hu_tax_id(tax_id_raw):
            raise HTTPException(status_code=422, detail="Invalid Hungarian tax ID.")

        return BillingSettingsUpdate(
            billing_customer_type="company",
            billing_full_name="",
            billing_company_name=company_name,
            billing_tax_id=normalize_hu_tax_id(tax_id_raw),
            billing_address_line=address,
            billing_postal_code=postal,
            billing_city=city,
            billing_region="",
            billing_country=country,
        )


__all__ = ["BillingSettingsUpdate", "BillingSettingsValidator"]
