// frontend/src/features/settings/sections/billing/billingValidation.test.ts
// Feladat: Billing validációs szabályok tesztje (csak cég, HU adószám).
// Sárközi Mihály - 2026.05.29

import { describe, expect, it } from "vitest";
import { validateBillingForm } from "./billingValidation";
import type { BillingFormState } from "./billingTypes";

const t = (key: string) => key;

const baseForm: BillingFormState = {
  customerType: "company",
  fullName: "",
  companyName: "",
  taxId: "",
  addressLine: "Fo utca 1",
  postalCode: "1111",
  city: "Budapest",
  region: "",
  country: "HU",
};

describe("validateBillingForm", () => {
  it("requires company name and tax id", () => {
    const errors = validateBillingForm(baseForm, t);
    expect(errors.companyName).toBe("settings.billingFieldRequired");
    expect(errors.taxId).toBe("settings.billingFieldRequired");
  });

  it("rejects invalid hungarian tax id", () => {
    const errors = validateBillingForm({ ...baseForm, companyName: "Acme Kft", taxId: "12892312" }, t);
    expect(errors.taxId).toBe("settings.billingInvalidTaxId");
  });

  it("accepts valid hungarian tax id", () => {
    const errors = validateBillingForm({ ...baseForm, companyName: "Acme Kft", taxId: "12892312-1-42" }, t);
    expect(errors.taxId).toBeUndefined();
    expect(errors.companyName).toBeUndefined();
  });
});
