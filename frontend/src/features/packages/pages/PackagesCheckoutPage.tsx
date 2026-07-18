import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { useBillingOverview, useUpdateSubscriptionMutation, type BillingCatalogEntry } from "../../billing/hooks/useBilling";
import { formatPlanResourceBlockMessage, planResourceBlock, readBillingResourceUsage } from "../planEligibility";
import {
  FIXED_BILLING_COUNTRY,
  isValidHuTaxId,
  isValidPostalCode,
  normalizeHuTaxId,
  normalizePostalCode,
} from "./checkoutOptions";
import { hasSavedCheckoutBillingDetails } from "./checkoutBillingDetails";
import { SavedBillingDetailsSummary } from "./SavedBillingDetailsSummary";
import { useBillingSettings, useLocaleSettings, usePatchBillingSettingsMutation } from "../../settings/hooks/useSettings";
import { formatDateOnly } from "../../../utils/dateTimeFormatting";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import {
  addMonthsToDateIso,
  billingPeriodMonths,
  flooredMonthlyEuroAfterDiscount,
  formatForintAmount,
  todayDateIso,
} from "../components/packageUtils";

const VALID_PERIODS = ["monthly", "quarterly", "yearly"] as const;
type BillingPeriod = (typeof VALID_PERIODS)[number];

function isFreePlan(plan: BillingCatalogEntry): boolean {
  return plan.code === "free" || plan.price_cents === 0;
}

export default function PackagesCheckoutPage() {
  const { t, locale } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuthStore();
  const { data: billingOverview, isLoading } = useBillingOverview();
  const { data: settings, isLoading: settingsLoading } = useBillingSettings();
  const { data: localeSettings } = useLocaleSettings();
  const updateSubscriptionMutation = useUpdateSubscriptionMutation();
  const patchBillingMutation = usePatchBillingSettingsMutation();

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
  const [formError, setFormError] = useState<string | null>(null);

  const catalog = useMemo(() => billingOverview?.catalog ?? [], [billingOverview?.catalog]);
  const plan = useMemo(
    () => catalog.find((e) => e.entry_type === "plan" && e.code === planCode && !isFreePlan(e)),
    [catalog, planCode]
  );

  const subscription = billingOverview?.subscription ?? {};
  const currentPlanCode = String(subscription.plan_code ?? "free");

  const summary = useMemo(() => {
    if (!plan) return null;
    const listM = Math.floor(Number(plan.price_cents) / 100);
    const effM = flooredMonthlyEuroAfterDiscount(plan.price_cents, billingPeriod);
    const monthEuro = billingPeriod === "monthly" ? listM : effM;
    let periodTotalEuro: number | null = null;
    if (billingPeriod === "quarterly") periodTotalEuro = effM * 3;
    if (billingPeriod === "yearly") periodTotalEuro = effM * 12;
    const dueNowEuro = periodTotalEuro ?? monthEuro;
    return { monthEuro, periodTotalEuro, dueNowEuro };
  }, [plan, billingPeriod]);

  const billedPhrase =
    billingPeriod === "monthly"
      ? t("packages.bannerBilledMonthly")
      : billingPeriod === "yearly"
        ? t("packages.bannerBilledYearly")
        : t("packages.bannerBilledQuarterly");

  const checkoutTotalPeriodAdverb =
    billingPeriod === "quarterly"
      ? t("packages.checkoutTotalAdverbQuarterly")
      : billingPeriod === "yearly"
        ? t("packages.checkoutTotalAdverbYearly")
        : "";
  const hasSavedBillingDetails = hasSavedCheckoutBillingDetails(settings);
  const billingDetailsLocked = hasSavedBillingDetails && !billingDetailsEditing;

  // Csak a settings betöltése után töltünk prefillel — különben a későn érkező válasz felülírja a begépelt adatokat.
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
    setFormError(null);
    if (!plan || !acceptTerms || currentPlanCode !== "free") return;

    const companyName = company.trim() || String(settings?.billing_company_name ?? "").trim();
    const address = addressLine.trim() || String(settings?.billing_address_line ?? "").trim();
    const cityName = city.trim() || String(settings?.billing_city ?? "").trim();
    const postal = normalizePostalCode(postalCode || settings?.billing_postal_code || "");
    const tax = normalizeHuTaxId(taxId || settings?.billing_tax_id || "");

    if (!companyName || !address || !cityName || !postal.trim()) {
      setFormError(t("packages.checkoutBillingRequiredError"));
      setBillingDetailsEditing(true);
      return;
    }
    if (!isValidPostalCode(postal)) {
      setFormError(t("packages.checkoutPostalCodeHint"));
      setBillingDetailsEditing(true);
      return;
    }
    if (!isValidHuTaxId(tax)) {
      setFormError(t("settings.billingInvalidTaxId"));
      setBillingDetailsEditing(true);
      return;
    }

    const { usedGb, usedKbCount } = readBillingResourceUsage(billingOverview?.usage as Record<string, unknown> | undefined);
    const block = planResourceBlock(plan, usedGb, usedKbCount, false);
    if (block.blocked) return;

    try {
      // Első csomagvásárláskor a cégadatokat kötelezően elmentjük a számlázáshoz.
      await patchBillingMutation.mutateAsync({
        billing_customer_type: "company",
        billing_full_name: "",
        billing_company_name: companyName,
        billing_tax_id: tax,
        billing_address_line: address,
        billing_postal_code: postal,
        billing_city: cityName,
        billing_country: FIXED_BILLING_COUNTRY,
      });
      const res = await updateSubscriptionMutation.mutateAsync({ plan_code: plan.code, billing_period: billingPeriod });
      navigate("/admin/forgalom", {
        state: { checkoutComplete: true, message: res.message },
        replace: true,
      });
    } catch (err) {
      setFormError(getApiErrorMessage(err) ?? t("packages.checkoutBillingSaveFailed"));
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

  if (isLoading || settingsLoading || !billingDetailsPrefilled) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)]">
        <div>{t("common.loading")}</div>
      </div>
    );
  }

  if (currentPlanCode !== "free") {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)] max-w-lg mx-auto">
        <p className="text-[var(--color-muted)] mb-4">{t("packages.checkoutOnlyFromFree")}</p>
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

  if (!plan || !summary) {
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
  const endIso = addMonthsToDateIso(startIso, billingPeriodMonths(billingPeriod));
  const fromLabel = formatDateOnly(startIso, {
    locale,
    timezone: localeSettings?.timezone,
    dateFormat: localeSettings?.date_format,
    dateStyle: localeSettings?.date_format ? undefined : "long",
  });
  const toLabel = formatDateOnly(endIso, {
    locale,
    timezone: localeSettings?.timezone,
    dateFormat: localeSettings?.date_format,
    dateStyle: localeSettings?.date_format ? undefined : "long",
  });

  const { usedGb: checkoutUsedGb, usedKbCount: checkoutUsedKb } = readBillingResourceUsage(
    billingOverview?.usage as Record<string, unknown> | undefined
  );
  const checkoutResourceBlock = planResourceBlock(plan, checkoutUsedGb, checkoutUsedKb, false);

  const submitDisabled =
    !acceptTerms ||
    updateSubscriptionMutation.isPending ||
    patchBillingMutation.isPending ||
    (!billingDetailsLocked &&
      (!company.trim() ||
        !isValidHuTaxId(taxId) ||
        !isValidPostalCode(postalCode) ||
        !city.trim() ||
        !addressLine.trim())) ||
    !cardNumber.trim() ||
    !cardExpiry.trim() ||
    !cardCvc.trim() ||
    checkoutResourceBlock.blocked;

  return (
    <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)]">
      <div className="max-w-xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold text-center">{t("packages.checkoutTitle")}</h1>

        {checkoutResourceBlock.blocked ? (
          <div
            className="rounded-xl border border-amber-600/40 bg-amber-500/10 p-4 text-sm text-[var(--color-foreground)] leading-relaxed whitespace-pre-wrap"
            role="alert"
          >
            <p className="font-semibold text-amber-950 dark:text-amber-100 mb-2">{t("packages.planBlockedModalTitle")}</p>
            <p>{formatPlanResourceBlockMessage(checkoutResourceBlock, checkoutUsedGb, checkoutUsedKb, t)}</p>
          </div>
        ) : null}

        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-sm space-y-2">
          <p className="font-medium">{t("packages.checkoutSummaryHeading")}</p>
          <p>
            <span className="text-[var(--color-muted)]">{t("packages.checkoutChosenPlan")}</span>{" "}
            <span className="font-medium">{plan.name}</span>
          </p>
          <p>
            <span className="text-[var(--color-muted)]">{t("packages.checkoutBillingCycle")}</span>{" "}
            <span className="font-medium">{billedPhrase}</span>
          </p>
          <p>
            <span className="text-[var(--color-muted)]">{t("packages.checkoutAmountHint")}</span>{" "}
            <span className="font-medium tabular-nums">
              {formatForintAmount(summary.monthEuro, locale)} Ft / {t("packages.perMonthSuffix")}
              {summary.periodTotalEuro != null && checkoutTotalPeriodAdverb
                ? ` · ${formatForintAmount(summary.periodTotalEuro, locale)} Ft / ${checkoutTotalPeriodAdverb}`
                : ""}
            </span>
          </p>
          <p>
            <span className="text-[var(--color-muted)]">{t("packages.checkoutDueNowTotal")}</span>{" "}
            <span className="font-semibold tabular-nums">{formatForintAmount(summary.dueNowEuro, locale)} Ft</span>
          </p>
          <p className="text-[var(--color-muted)] text-xs leading-relaxed pt-1">
            {t("packages.checkoutPeriodWindow")
              .replace("{{from}}", fromLabel)
              .replace("{{to}}", toLabel)}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
          <h2 className="text-sm font-semibold">{t("packages.checkoutBillingSection")}</h2>
          {billingDetailsLocked && settings ? (
            <SavedBillingDetailsSummary settings={settings} onEdit={() => setBillingDetailsEditing(true)} />
          ) : (
          <div className="space-y-3">
            <label className="block text-xs text-[var(--color-muted)]">
              {t("packages.checkoutCompanyRequired")}
              <input
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                autoComplete="organization"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutPostalCode")}
                <input
                  value={postalCode}
                  onChange={(e) => setPostalCode(normalizePostalCode(e.target.value))}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                  autoComplete="postal-code"
                  inputMode="numeric"
                  maxLength={5}
                />
                <span className="mt-1 block text-[11px] text-[var(--color-muted)]">{t("packages.checkoutPostalCodeHint")}</span>
              </label>
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutCity")}
                <input
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                  autoComplete="address-level2"
                />
              </label>
            </div>
            <label className="block text-xs text-[var(--color-muted)]">
              {t("packages.checkoutLocality")}
              <input
                value={addressLine}
                onChange={(e) => setAddressLine(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                autoComplete="street-address"
              />
            </label>
            <label className="block text-xs text-[var(--color-muted)]">
              {t("packages.checkoutTaxIdRequired")}
              <input
                value={taxId}
                onChange={(e) => setTaxId(normalizeHuTaxId(e.target.value))}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                placeholder="12892312-1-42"
              />
              <span className="mt-1 block text-[11px] text-[var(--color-muted)]">{t("packages.checkoutTaxIdFormatHint")}</span>
            </label>
          </div>
          )}

          <h2 className="text-sm font-semibold pt-2">{t("packages.checkoutPaymentSection")}</h2>
          <div className="space-y-3">
            <label className="block text-xs text-[var(--color-muted)]">
              {t("packages.checkoutCardNumber")}
              <input
                value={cardNumber}
                onChange={(e) => setCardNumber(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                autoComplete="cc-number"
                placeholder="4242 4242 4242 4242"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutCardExpiry")}
                <input
                  value={cardExpiry}
                  onChange={(e) => setCardExpiry(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                  autoComplete="cc-exp"
                  placeholder="MM/YY"
                />
              </label>
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutCardCvc")}
                <input
                  value={cardCvc}
                  onChange={(e) => setCardCvc(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                  autoComplete="cc-csc"
                  placeholder="CVC"
                />
              </label>
            </div>
          </div>

          <label className="flex items-start gap-3 text-sm pt-2 cursor-pointer text-left">
            <input type="checkbox" checked={acceptTerms} onChange={(e) => setAcceptTerms(e.target.checked)} className="mt-1 shrink-0" style={{ width: "auto" }} />
            <span className="relative top-px ml-[3px]">{t("packages.checkoutAcceptSimulated")}</span>
          </label>

          {formError || updateSubscriptionMutation.isError || patchBillingMutation.isError ? (
            <p className="text-sm text-red-600 dark:text-red-400">
              {formError ?? getApiErrorMessage(updateSubscriptionMutation.error ?? patchBillingMutation.error) ?? t("common.errorGeneric")}
            </p>
          ) : null}

          <div className="flex flex-wrap gap-3 pt-2">
            <button
              type="submit"
              disabled={submitDisabled}
              className="rounded-lg px-4 py-2.5 bg-[var(--color-primary)] text-[var(--color-on-primary)] text-sm font-semibold disabled:opacity-50"
            >
              {updateSubscriptionMutation.isPending || patchBillingMutation.isPending
                ? t("common.loading")
                : t("packages.checkoutSubmit")}
            </button>
            <button
              type="button"
              className="rounded-lg px-4 py-2.5 border border-[var(--color-border)] text-sm"
              onClick={() => navigate("/admin/pricing")}
            >
              {t("common.cancel")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
