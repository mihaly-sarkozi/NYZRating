import { useTranslation } from "../../../i18n";
import type { BillingSettingsResponse } from "../../../api/services/settingsService";

function SummaryRow({ label, value }: { label: string; value?: string | null }) {
  if (!value?.trim()) return null;
  return (
    <div className="flex justify-between gap-4 border-b border-[var(--color-border)]/60 pb-2 last:border-b-0">
      <span className="text-[var(--color-muted)]">{label}</span>
      <span className="text-right font-medium text-[var(--color-foreground)]">{value}</span>
    </div>
  );
}

export function SavedBillingDetailsSummary({ settings, onEdit }: { settings: BillingSettingsResponse; onEdit: () => void }) {
  const { t } = useTranslation();

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[var(--color-foreground)]">{t("packages.checkoutSavedBillingTitle")}</p>
          <p className="mt-1 text-xs text-[var(--color-muted)]">{t("packages.checkoutSavedBillingHint")}</p>
        </div>
        <button
          type="button"
          onClick={onEdit}
          className="shrink-0 rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--color-border)]/20"
        >
          {t("common.edit")}
        </button>
      </div>
      <div className="space-y-2 text-sm">
        <SummaryRow label={t("packages.checkoutCompanyRequired")} value={settings.billing_company_name} />
        <SummaryRow label={t("packages.checkoutPostalCode")} value={settings.billing_postal_code} />
        <SummaryRow label={t("packages.checkoutCity")} value={settings.billing_city} />
        <SummaryRow label={t("packages.checkoutLocality")} value={settings.billing_address_line} />
        <SummaryRow label={t("packages.checkoutTaxIdRequired")} value={settings.billing_tax_id} />
      </div>
    </div>
  );
}
