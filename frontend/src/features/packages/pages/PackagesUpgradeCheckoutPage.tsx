import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import {
  useBillingOverview,
  useBillingUpgradePreview,
  useCompleteUpgradeMutation,
  type BillingCatalogEntry,
} from "../../billing/hooks/useBilling";
import { formatPlanResourceBlockMessage, planResourceBlock, readBillingResourceUsage } from "../planEligibility";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import { patchBillingSettings } from "../../../api/services/settingsService";
import {
  FIXED_BILLING_COUNTRY,
  isValidHuTaxId,
  isValidPostalCode,
  normalizeHuTaxId,
  normalizePostalCode,
} from "./checkoutOptions";
import { hasSavedCheckoutBillingDetails } from "./checkoutBillingDetails";
import { SavedBillingDetailsSummary } from "./SavedBillingDetailsSummary";
import { useBillingSettings, useLocaleSettings } from "../../settings/hooks/useSettings";
import { formatDateOnly } from "../../../utils/dateTimeFormatting";
import { formatEuroLocaleFromCents, todayDateIso } from "../components/packageUtils";

const VALID_PERIODS = ["monthly", "quarterly", "yearly"] as const;
type BillingPeriod = (typeof VALID_PERIODS)[number];

function isFreePlan(plan: BillingCatalogEntry): boolean {
  return plan.code === "free" || plan.price_cents === 0;
}

function formatEuroFromCents(cents: number, loc: string): string {
  return formatEuroLocaleFromCents(cents, loc);
}

function percentValue(part: number, total: number): number {
  if (total <= 0) return 0;
  return Math.max(0, Math.min((part / total) * 100, 100));
}

export default function PackagesUpgradeCheckoutPage() {
  const { t, locale } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuthStore();
  const { data: billingOverview, isLoading: overviewLoading } = useBillingOverview();
  const { data: settings, isLoading: settingsLoading } = useBillingSettings();
  const { data: localeSettings } = useLocaleSettings();
  const completeUpgradeMutation = useCompleteUpgradeMutation();

  const planCode = (searchParams.get("plan") ?? "").toLowerCase();
  const rawPeriod = (searchParams.get("period") ?? "quarterly").toLowerCase();
  const billingPeriod: BillingPeriod = VALID_PERIODS.includes(rawPeriod as BillingPeriod) ? (rawPeriod as BillingPeriod) : "quarterly";

  const [cardNumber, setCardNumber] = useState("");
  const [cardExpiry, setCardExpiry] = useState("");
  const [cardCvc, setCardCvc] = useState("");
  const [company, setCompany] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [city, setCity] = useState("");
  const [taxId, setTaxId] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [billingDetailsEditing, setBillingDetailsEditing] = useState(true);
  const [billingDetailsPrefilled, setBillingDetailsPrefilled] = useState(false);

  const catalog = useMemo(() => billingOverview?.catalog ?? [], [billingOverview?.catalog]);
  const plan = useMemo(
    () => catalog.find((e) => e.entry_type === "plan" && e.code === planCode && !isFreePlan(e)),
    [catalog, planCode]
  );

  const subscription = billingOverview?.subscription ?? {};
  const currentPlanCode = String(subscription.plan_code ?? "free");

  const previewEnabled = Boolean(plan) && currentPlanCode !== "free";
  const {
    data: preview,
    isLoading: previewLoading,
    isError: previewError,
    error: previewErr,
  } = useBillingUpgradePreview(planCode, billingPeriod, { enabled: previewEnabled });

  const billedPhrase =
    billingPeriod === "monthly"
      ? t("packages.bannerBilledMonthly")
      : billingPeriod === "yearly"
        ? t("packages.bannerBilledYearly")
        : t("packages.bannerBilledQuarterly");

  const previewErrMsg = previewError ? getApiErrorMessage(previewErr) ?? t("common.errorGeneric") : null;
  const hasSavedBillingDetails = hasSavedCheckoutBillingDetails(settings);
  const billingDetailsLocked = hasSavedBillingDetails && !billingDetailsEditing;

  useEffect(() => {
    if (settingsLoading || billingDetailsPrefilled) return;
    if (!settings) {
      setBillingDetailsPrefilled(true);
      return;
    }
    setCompany(settings.billing_company_name ?? "");
    setAddressLine(settings.billing_address_line ?? "");
    setPostalCode(normalizePostalCode(settings.billing_postal_code ?? ""));
    setCity(settings.billing_city ?? "");
    setTaxId(normalizeHuTaxId(settings.billing_tax_id ?? ""));
    setBillingDetailsEditing(!hasSavedCheckoutBillingDetails(settings));
    setBillingDetailsPrefilled(true);
  }, [billingDetailsPrefilled, settings, settingsLoading]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!plan || !acceptTerms || !preview || currentPlanCode === "free") return;
    if (!isValidPostalCode(postalCode) || !isValidHuTaxId(taxId)) return;
    const { usedGb, usedKbCount } = readBillingResourceUsage(billingOverview?.usage as Record<string, unknown> | undefined);
    const block = planResourceBlock(plan, usedGb, usedKbCount, false);
    if (block.blocked) return;
    try {
      await patchBillingSettings({
        billing_customer_type: "company",
        billing_full_name: "",
        billing_company_name: company,
        billing_tax_id: normalizeHuTaxId(taxId),
        billing_address_line: addressLine,
        billing_postal_code: postalCode,
        billing_city: city,
        billing_country: FIXED_BILLING_COUNTRY,
      });
      const res = await completeUpgradeMutation.mutateAsync({ plan_code: plan.code, billing_period: billingPeriod });
      const amountLabel = formatEuroFromCents(res.total_charge_cents, locale);
      const activated = res.status === "updated" || res.status === "already_active";
      const message = !activated
        ? t("packages.upgradeCheckoutPending")
        : res.total_charge_cents > 0
          ? t("packages.upgradeCheckoutSuccessPaid")
              .replace("{{amount}}", amountLabel)
              .replace(
                "{{date}}",
                formatDateOnly(res.paid_until_iso, {
                  locale,
                  timezone: localeSettings?.timezone,
                  dateFormat: localeSettings?.date_format,
                  dateStyle: localeSettings?.date_format ? undefined : "long",
                })
              )
          : t("packages.upgradeCheckoutSuccessZero");
      navigate("/admin/forgalom", {
        state: { upgradeCheckoutComplete: true, message },
        replace: true,
      });
    } catch {
      /* axios error surfaced via mutation */
    }
  };

  if (!user || user.role !== "owner") {
    return (
      <div className="p-6 min-h-full bg-[var(--color-background)]">
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded max-w-lg mx-auto">
          {t("settings.ownerOnly")}
        </div>
      </div>
    );
  }

  if (overviewLoading || settingsLoading || !billingDetailsPrefilled) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)]">
        <div>{t("common.loading")}</div>
      </div>
    );
  }

  if (currentPlanCode === "free") {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)] max-w-lg mx-auto">
        <p className="text-[var(--color-muted)] mb-4">{t("packages.upgradeCheckoutOnlyFromPaid")}</p>
        <button
          type="button"
          className="rounded-lg px-4 py-2 bg-[var(--color-primary)] text-[var(--color-on-primary)] text-sm font-medium"
          onClick={() => navigate("/admin/pricing")}
        >
          {t("packages.checkoutBackToPackages")}
        </button>
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)] max-w-lg mx-auto">
        <p className="text-[var(--color-muted)] mb-4">{t("packages.checkoutInvalidPlan")}</p>
        <button
          type="button"
          className="rounded-lg px-4 py-2 bg-[var(--color-primary)] text-[var(--color-on-primary)] text-sm font-medium"
          onClick={() => navigate("/admin/pricing")}
        >
          {t("packages.checkoutBackToPackages")}
        </button>
      </div>
    );
  }

  const startIso = todayDateIso();
  const endIso = preview?.paid_until_iso ?? "";
  const fromLabel = formatDateOnly(startIso, {
    locale,
    timezone: localeSettings?.timezone,
    dateFormat: localeSettings?.date_format,
    dateStyle: localeSettings?.date_format ? undefined : "long",
  });
  const toLabel = endIso
    ? formatDateOnly(endIso, {
        locale,
        timezone: localeSettings?.timezone,
        dateFormat: localeSettings?.date_format,
        dateStyle: localeSettings?.date_format ? undefined : "long",
      })
    : "—";

  const { usedGb: checkoutUsedGb, usedKbCount: checkoutUsedKb } = readBillingResourceUsage(
    billingOverview?.usage as Record<string, unknown> | undefined
  );
  const checkoutResourceBlock = planResourceBlock(plan, checkoutUsedGb, checkoutUsedKb, false);

  const submitDisabled =
    !acceptTerms ||
    completeUpgradeMutation.isPending ||
    (!billingDetailsLocked &&
      (!company.trim() ||
        !isValidHuTaxId(taxId) ||
        !isValidPostalCode(postalCode) ||
        !city.trim() ||
        !addressLine.trim())) ||
    !cardNumber.trim() ||
    !cardExpiry.trim() ||
    !cardCvc.trim() ||
    checkoutResourceBlock.blocked ||
    previewLoading ||
    !preview ||
    Boolean(previewErrMsg);

  const remainingMonths = preview?.remaining_prepaid_months ?? preview?.remaining_period_days ?? 0;
  const totalMonths = preview?.total_prepaid_months ?? preview?.total_period_days ?? 0;
  const prorationLine =
    preview != null
      ? t("packages.upgradeCheckoutProrationLine")
          .replace("{{remaining}}", String(remainingMonths))
          .replace("{{total}}", String(totalMonths))
          .replace("{{amount}}", formatEuroFromCents(preview.old_remaining_credit_cents, locale))
      : null;
  const paidUntilLabel =
    preview?.paid_until_iso != null
      ? formatDateOnly(preview.paid_until_iso, {
          locale,
          timezone: localeSettings?.timezone,
          dateFormat: localeSettings?.date_format,
          dateStyle: localeSettings?.date_format ? undefined : "long",
        })
      : "—";
  const progressPercent = preview != null ? percentValue(remainingMonths, totalMonths) : 0;
  const payNowLabel = preview != null ? `${formatEuroFromCents(preview.total_charge_cents, locale)} Ft` : "—";

  return (
    <div className="app-page">
      <div className="mx-auto max-w-3xl space-y-6">
        <PageHeader
          eyebrow={t("nav.packages")}
          title={t("packages.upgradeCheckoutTitle")}
          description={t("packages.upgradeCheckoutIntro")}
        />

        {checkoutResourceBlock.blocked ? (
          <Alert tone="warning" className="whitespace-pre-wrap leading-relaxed" role="alert">
            <p className="mb-2 font-semibold">{t("packages.planBlockedModalTitle")}</p>
            <p>{formatPlanResourceBlockMessage(checkoutResourceBlock, checkoutUsedGb, checkoutUsedKb, t)}</p>
          </Alert>
        ) : null}

        {previewErrMsg ? (
          <Alert tone="error" role="alert">{previewErrMsg}</Alert>
        ) : null}

        {previewLoading ? <div className="text-center text-sm text-[var(--color-muted)]">{t("common.loading")}</div> : null}

        <section className="app-surface p-6">
          <p className="text-sm font-medium text-[var(--color-muted)]">{t("packages.checkoutSummaryHeading")}</p>

          <div className="mt-4 space-y-4">
            <div className="flex justify-between gap-4">
              <span className="text-[var(--color-muted)]">{t("packages.checkoutChosenPlan")}</span>
              <span className="font-medium text-[var(--color-foreground)]">{plan.name}</span>
            </div>

            <div className="flex justify-between gap-4">
              <span className="text-[var(--color-muted)]">{t("packages.checkoutBillingCycle")}</span>
              <span className="font-medium text-[var(--color-foreground)]">{billedPhrase}</span>
            </div>

            <div className="flex justify-between gap-4">
              <span className="text-[var(--color-muted)]">{t("packages.checkoutPeriodLabel")}</span>
              <span className="text-right font-medium text-[var(--color-foreground)]">
                {fromLabel} - {toLabel}
              </span>
            </div>

            <div className="flex justify-between gap-4">
              <span className="text-[var(--color-muted)]">{t("packages.upgradeCheckoutPaidUntil")}</span>
              <span className="text-right font-medium text-[var(--color-foreground)]">{paidUntilLabel}</span>
            </div>
          </div>

          <div className="mt-6">
            <div className="h-3 w-full overflow-hidden rounded-full bg-[var(--color-card-muted)]">
              <div className="h-full bg-[var(--color-accent)]" style={{ width: `${progressPercent}%` }} />
            </div>
            <div className="mt-2 flex justify-between text-sm text-[var(--color-muted)]">
              <span>
                {preview != null ? `${remainingMonths} / ${totalMonths} ${t("packages.upgradeCheckoutDaysRemaining")}` : "—"}
              </span>
              <span>{Math.round(progressPercent)}%</span>
            </div>
          </div>

          <div className="mt-6 rounded-2xl bg-[var(--color-card-strong)] p-5 text-[var(--color-on-primary)]">
            <p className="text-sm opacity-70">{t("packages.upgradeCheckoutPayNowLabel")}</p>
            <p className="mt-2 text-3xl font-semibold">{payNowLabel}</p>
            {preview ? (
              <div className="mt-3 space-y-1 text-sm opacity-70">
                <p>
                  {t("packages.upgradeCheckoutNextPeriodShort")}: + {formatEuroFromCents(preview.next_period_charge_cents, locale)} Ft
                </p>
                <p>
                  {t("packages.upgradeCheckoutProrationShort")}: - {formatEuroFromCents(preview.old_remaining_credit_cents, locale)} Ft
                </p>
                {(preview.sms_carryover_from_old_plan ?? 0) > 0 ? (
                  <p>
                    {t("packages.upgradeCheckoutSmsCarryoverShort")}: + {preview.sms_carryover_from_old_plan}
                  </p>
                ) : null}
                <p className="mt-2 border-t border-[var(--color-on-primary)]/20 pt-2 font-semibold opacity-100">
                  {t("packages.upgradeCheckoutPayNowLabel")}: {payNowLabel}
                </p>
              </div>
            ) : null}
            {prorationLine ? <p className="mt-3 text-sm opacity-70">{prorationLine}</p> : null}
          </div>
        </section>

        <form onSubmit={handleSubmit} className="app-surface p-6">
          <p className="text-sm font-medium text-[var(--color-muted)]">{t("packages.checkoutBillingSection")}</p>

          <div className="mt-4 space-y-4">
            {billingDetailsLocked && settings ? (
              <SavedBillingDetailsSummary settings={settings} onEdit={() => setBillingDetailsEditing(true)} />
            ) : (
            <div className="space-y-3 pt-2">
              <label className="block">
                <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutCompanyRequired")}</span>
                <input
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  className="mt-1"
                  autoComplete="organization"
                />
              </label>
              <div className="grid grid-cols-2 gap-4">
                <label className="block">
                  <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutPostalCode")}</span>
                  <input
                    value={postalCode}
                    onChange={(e) => setPostalCode(normalizePostalCode(e.target.value))}
                    className="mt-1"
                    autoComplete="postal-code"
                    inputMode="numeric"
                    maxLength={5}
                  />
                  <span className="mt-1 block text-[11px] text-[var(--color-muted)]">{t("packages.checkoutPostalCodeHint")}</span>
                </label>
                <label className="block">
                  <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutCity")}</span>
                  <input
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    className="mt-1"
                    autoComplete="address-level2"
                  />
                </label>
              </div>
              <label className="block">
                <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutLocality")}</span>
                <input
                  value={addressLine}
                  onChange={(e) => setAddressLine(e.target.value)}
                  className="mt-1"
                  autoComplete="street-address"
                />
              </label>
              <label className="block">
                <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutTaxIdRequired")}</span>
                <input
                  value={taxId}
                  onChange={(e) => setTaxId(normalizeHuTaxId(e.target.value))}
                  className="mt-1"
                  placeholder="12345678-1-42"
                />
                <span className="mt-1 block text-[11px] text-[var(--color-muted)]">{t("packages.checkoutTaxIdFormatHint")}</span>
              </label>
            </div>
            )}

            <p className="pt-2 text-sm font-medium text-[var(--color-muted)]">{t("packages.checkoutPaymentSection")}</p>
            <label className="block">
              <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutCardNumber")}</span>
              <input
                value={cardNumber}
                onChange={(e) => setCardNumber(e.target.value)}
                className="mt-1"
                autoComplete="cc-number"
                placeholder="4242 4242 4242 4242"
              />
            </label>

            <div className="grid grid-cols-2 gap-4">
              <label className="block">
                <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutCardExpiry")}</span>
                <input
                  value={cardExpiry}
                  onChange={(e) => setCardExpiry(e.target.value)}
                  className="mt-1"
                  autoComplete="cc-exp"
                  placeholder="MM/YY"
                />
              </label>
              <label className="block">
                <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutCardCvc")}</span>
                <input
                  value={cardCvc}
                  onChange={(e) => setCardCvc(e.target.value)}
                  className="mt-1"
                  autoComplete="cc-csc"
                  placeholder="CVC"
                />
              </label>
            </div>

            <label className="app-surface-muted flex cursor-pointer items-start gap-3 p-4 text-left text-sm text-[var(--color-muted)]">
              <input type="checkbox" checked={acceptTerms} onChange={(e) => setAcceptTerms(e.target.checked)} className="mt-1 shrink-0" style={{ width: "auto" }} />
              <span className="relative top-px ml-[3px]">{t("packages.checkoutAcceptSimulated")}</span>
            </label>
          </div>

          {completeUpgradeMutation.isError ? (
            <Alert tone="error" className="mt-4">{getApiErrorMessage(completeUpgradeMutation.error) ?? t("common.errorGeneric")}</Alert>
          ) : null}

          <div className="mt-6 flex gap-3">
            <Button
              type="submit"
              disabled={submitDisabled}
              fullWidth
              size="lg"
            >
              {completeUpgradeMutation.isPending ? t("common.loading") : t("packages.upgradeCheckoutSubmit")}
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="lg"
              onClick={() => navigate("/admin/pricing")}
            >
              {t("common.cancel")}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
