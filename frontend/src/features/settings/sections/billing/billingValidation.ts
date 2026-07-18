// frontend/src/features/settings/sections/billing/billingValidation.ts
// Feladat: Billing form kliensoldali validációs szabályai (csak cég, HU adószám).
// Sárközi Mihály - 2026.05.29

import { isValidHuTaxId } from "../../../billing/billingCountries";
import type { BillingFieldErrors, BillingFormState } from "./billingTypes";

export function validateBillingForm(form: BillingFormState, t: (key: string) => string): BillingFieldErrors {
  const validateRequired = (value: string) => (value.trim() ? "" : t("settings.billingFieldRequired"));
  const errors: BillingFieldErrors = {};

  const companyNameError = validateRequired(form.companyName);
  if (companyNameError) errors.companyName = companyNameError;
  const taxIdError = validateRequired(form.taxId);
  if (taxIdError) {
    errors.taxId = taxIdError;
  } else if (!isValidHuTaxId(form.taxId)) {
    errors.taxId = t("settings.billingInvalidTaxId");
  }

  const postalCodeError = validateRequired(form.postalCode);
  if (postalCodeError) errors.postalCode = postalCodeError;
  const cityError = validateRequired(form.city);
  if (cityError) errors.city = cityError;
  const addressLineError = validateRequired(form.addressLine);
  if (addressLineError) errors.addressLine = addressLineError;

  return errors;
}
