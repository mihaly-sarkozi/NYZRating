// frontend/src/features/settings/sections/billing/BillingSettingsSection.tsx
// Feladat: Billing settings UI-only komponens, kizárólag kapott propsokra támaszkodva.
// Sárközi Mihály - 2026.05.29

import SettingsBlock from "../../components/SettingsBlock";
import type { Locale } from "../../../../i18n";
import type { BillingFieldErrors, BillingFormState } from "./billingTypes";

type BillingSettingsSectionProps = {
  title: string;
  disabled: boolean;
  locale: Locale;
  t: (key: string) => string;
  form: BillingFormState;
  errors: BillingFieldErrors;
  onFieldChange: <K extends keyof BillingFormState>(field: K, value: BillingFormState[K]) => void;
};

export default function BillingSettingsSection({ title, disabled, locale, t, form, errors, onFieldChange }: BillingSettingsSectionProps) {
  void locale;
  return (
    <SettingsBlock title={title}>
      <div className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <TextField
            label={t("settings.billingCompanyName")}
            value={form.companyName}
            setter={(value) => onFieldChange("companyName", value)}
            disabled={disabled}
            required
            error={errors.companyName}
          />
          <TextField
            label={t("settings.billingTaxId")}
            value={form.taxId}
            setter={(value) => onFieldChange("taxId", value)}
            disabled={disabled}
            required
            placeholder="12345678-1-42"
            error={errors.taxId}
          />
          <TextField
            label={t("settings.billingPostalCode")}
            value={form.postalCode}
            setter={(value) => onFieldChange("postalCode", value)}
            disabled={disabled}
            required
            error={errors.postalCode}
          />
          <TextField
            label={t("settings.billingCity")}
            value={form.city}
            setter={(value) => onFieldChange("city", value)}
            disabled={disabled}
            required
            error={errors.city}
          />
          <TextField
            label={t("settings.billingAddressLine")}
            value={form.addressLine}
            setter={(value) => onFieldChange("addressLine", value)}
            disabled={disabled}
            required
            error={errors.addressLine}
          />
        </div>
      </div>
    </SettingsBlock>
  );
}

function TextField({
  label,
  value,
  setter,
  disabled,
  required,
  placeholder,
  error,
}: {
  label: string;
  value: string;
  setter: (value: string) => void;
  disabled: boolean;
  required?: boolean;
  placeholder?: string;
  error?: string;
}) {
  return (
    <label className="block text-sm text-[var(--color-label)]">
      {label}
      {required ? " *" : ""}
      <input
        value={value}
        onChange={(event) => setter(event.target.value)}
        className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
        disabled={disabled}
        required={required}
        placeholder={placeholder}
        aria-invalid={Boolean(error)}
      />
      {error ? <span className="mt-1 block text-xs text-red-600 dark:text-red-400">{error}</span> : null}
    </label>
  );
}
