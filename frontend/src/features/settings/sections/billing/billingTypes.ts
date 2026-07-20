// frontend/src/features/settings/sections/billing/billingTypes.ts
// Feladat: Billing form state és validációs hibatípusok centralizálása.
// Sárközi Mihály - 2026.05.29

import type { BillingCustomerType } from "../../countries/billingCountries";

export type BillingFormState = {
  customerType: BillingCustomerType;
  fullName: string;
  companyName: string;
  taxId: string;
  addressLine: string;
  postalCode: string;
  city: string;
  region: string;
  country: string;
  googleReviewUrl: string;
};

export type BillingFieldKey =
  | "customerType"
  | "fullName"
  | "companyName"
  | "taxId"
  | "addressLine"
  | "postalCode"
  | "city"
  | "region"
  | "country"
  | "googleReviewUrl";

export type BillingFieldErrors = Partial<
  Record<
    "fullName" | "companyName" | "taxId" | "country" | "postalCode" | "region" | "city" | "addressLine" | "googleReviewUrl",
    string
  >
>;
