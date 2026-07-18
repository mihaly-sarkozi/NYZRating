// frontend/src/features/settings/sections/billing/billingMapper.ts
// Feladat: Billing settings API payload és frontend form state közötti mappolás.
// Sárközi Mihály - 2026.05.29

import { FIXED_BILLING_COUNTRY, normalizeHuTaxId, normalizePostalCode } from "../../../billing/billingCountries";
import type { BillingSettingsResponse, PatchBillingSettingsPayload } from "../../api/settingsService";
import type { BillingFormState } from "./billingTypes";

export function mapBillingResponseToForm(response: BillingSettingsResponse): BillingFormState {
  return {
    customerType: "company",
    fullName: "",
    companyName: response.billing_company_name ?? "",
    taxId: normalizeHuTaxId(response.billing_tax_id ?? ""),
    addressLine: response.billing_address_line ?? "",
    postalCode: response.billing_postal_code ?? "",
    city: response.billing_city ?? "",
    region: "",
    country: FIXED_BILLING_COUNTRY,
  };
}

export function mapBillingFormToPayload(form: BillingFormState): PatchBillingSettingsPayload {
  return {
    billing_customer_type: "company",
    billing_full_name: "",
    billing_company_name: form.companyName.trim(),
    billing_tax_id: normalizeHuTaxId(form.taxId),
    billing_address_line: form.addressLine,
    billing_postal_code: normalizePostalCode(form.postalCode),
    billing_city: form.city,
    billing_region: "",
    billing_country: FIXED_BILLING_COUNTRY,
  };
}
