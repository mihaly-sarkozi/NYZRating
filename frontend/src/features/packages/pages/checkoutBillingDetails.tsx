import type { BillingSettingsResponse } from "../../../api/services/settingsService";
import {
  FIXED_BILLING_COUNTRY,
  isValidHuTaxId,
  isValidPostalCode,
} from "../../billing/billingCountries";

export type BillingCustomerType = "company";

export function checkoutCustomerTypeFromSettings(
  settings?: BillingSettingsResponse | null,
): BillingCustomerType {
  void settings;
  return "company";
}

export function hasSavedCheckoutBillingDetails(
  settings?: BillingSettingsResponse | null,
): boolean {
  if (!settings) return false;

  const commonFieldsFilled =
    Boolean(settings.billing_address_line?.trim()) &&
    Boolean(settings.billing_country?.trim()) &&
    isValidPostalCode(settings.billing_postal_code ?? "") &&
    Boolean(settings.billing_city?.trim());

  if (!commonFieldsFilled) return false;

  const taxId = settings.billing_tax_id?.trim() ?? "";

  return (
    Boolean(settings.billing_company_name?.trim()) &&
    (settings.billing_country === FIXED_BILLING_COUNTRY ||
      !settings.billing_country) &&
    isValidHuTaxId(taxId)
  );
}