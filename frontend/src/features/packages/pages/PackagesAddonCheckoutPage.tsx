import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { useBillingOverview, usePurchaseAddonMutation, type BillingCatalogEntry } from "../../billing/hooks/useBilling";
import { isAddonCheckoutCode, type AddonCheckoutCode } from "../addonCheckoutAllowed";
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
import { useBillingSettings } from "../../settings/hooks/useSettings";
import { formatEuroLocaleFromCents, includedNumber } from "../components/packageUtils";

function addonCheckoutName(entry: BillingCatalogEntry, t: (key: string) => string): string {
  switch (entry.code) {
    case "question_pack_100":
      return t("packages.expandQuestionsTitle").replace(
        "{{count}}",
        String(includedNumber(entry, "questions", 100))
      );
    default:
      return entry.name;
  }
}

type RequestedCheckoutItem = { addonCode: AddonCheckoutCode; quantity: number };
type CheckoutCatalogItem = RequestedCheckoutItem & { entry: BillingCatalogEntry };

export default function PackagesAddonCheckoutPage() {
  const { t, locale } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuthStore();
  const { data: billingOverview, isLoading } = useBillingOverview();
  const { data: settings, isLoading: settingsLoading } = useBillingSettings();
  const purchaseAddonMutation = usePurchaseAddonMutation();

  const addonCode = (searchParams.get("addon") ?? "").trim().toLowerCase();
  const quantity = Math.max(1, Math.min(99, parseInt(searchParams.get("qty") ?? "1", 10) || 1));

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
  const subscription = billingOverview?.subscription ?? {};
  const currentPlanCode = String(subscription.plan_code ?? "free");
  const isFreeAddonBlocked = currentPlanCode === "free";
  const itemsParam = searchParams.get("items") ?? "";

  const requestedItems = useMemo<RequestedCheckoutItem[]>(() => {
    if (itemsParam.trim()) {
      return itemsParam
        .split(",")
        .map((part) => {
          const [codeRaw, qtyRaw] = part.split(":");
          const code = (codeRaw ?? "").trim().toLowerCase();
          const qty = Math.max(1, Math.min(99, parseInt(qtyRaw ?? "1", 10) || 1));
          return isAddonCheckoutCode(code) ? { addonCode: code, quantity: qty } : null;
        })
        .filter((item): item is RequestedCheckoutItem => item != null);
    }
    return isAddonCheckoutCode(addonCode) ? [{ addonCode, quantity }] : [];
  }, [addonCode, itemsParam, quantity]);

  const checkoutItems = useMemo<CheckoutCatalogItem[]>(() => {
    return requestedItems
      .map((item) => {
        const entry = catalog.find((e) => e.entry_type === "addon" && e.code === item.addonCode);
        return entry ? { ...item, entry } : null;
      })
      .filter((item): item is CheckoutCatalogItem => item != null);
  }, [catalog, requestedItems]);
  const checkoutIsValid = requestedItems.length > 0 && checkoutItems.length === requestedItems.length;
  const lineTotalCents = checkoutItems.reduce((sum, item) => sum + Number(item.entry.price_cents) * item.quantity, 0);
  const lineTotalLabel = formatEuroLocaleFromCents(lineTotalCents, locale);
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
    if (!checkoutIsValid || isFreeAddonBlocked || !acceptTerms) return;
    if (!isValidPostalCode(postalCode) || !isValidHuTaxId(taxId)) return;
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
      for (const item of checkoutItems) {
        await purchaseAddonMutation.mutateAsync({ addon_code: item.addonCode, quantity: item.quantity });
      }
      navigate("/admin/forgalom", {
        state: { addonCheckoutComplete: true, message: t("packages.addonCheckoutSuccessMessage") },
        replace: true,
      });
    } catch {
      /* mutation error */
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

  if (!checkoutIsValid) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)] max-w-lg mx-auto">
        <p className="text-[var(--color-muted)] mb-4">{t("packages.addonCheckoutInvalidAddon")}</p>
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

  if (isFreeAddonBlocked) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)] max-w-lg mx-auto">
        <p className="text-[var(--color-muted)] mb-4">{t("packages.addonCheckoutDemoBlocked")}</p>
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

  const submitDisabled =
    !acceptTerms ||
    purchaseAddonMutation.isPending ||
    (!billingDetailsLocked &&
      (!company.trim() ||
        !isValidHuTaxId(taxId) ||
        !isValidPostalCode(postalCode) ||
        !city.trim() ||
        !addressLine.trim())) ||
    !cardNumber.trim() ||
    !cardExpiry.trim() ||
    !cardCvc.trim();

  return (
    <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)]">
      <div className="max-w-xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold text-center">{t("packages.addonCheckoutPageTitle")}</h1>
        <p className="text-sm text-[var(--color-muted)] text-center leading-relaxed">{t("packages.addonCheckoutIntro")}</p>

        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-sm space-y-2">
          <p className="font-medium">{t("packages.addonCheckoutSummaryHeading")}</p>
          {checkoutItems.map((item) => (
            <div key={item.addonCode} className="flex items-center justify-between gap-3 border-t border-[var(--color-border)] pt-2 first:border-t-0 first:pt-0">
              <div>
                <p className="font-medium">{addonCheckoutName(item.entry, t)}</p>
                <p className="text-xs text-[var(--color-muted)]">
                  {t("packages.addonCheckoutQuantity")} <span className="tabular-nums">{item.quantity}</span>
                </p>
              </div>
              <p className="font-medium tabular-nums">
                {formatEuroLocaleFromCents(Number(item.entry.price_cents) * item.quantity, locale)} Ft {t("packages.taxSuffix")}
              </p>
            </div>
          ))}
          <div className="flex items-center justify-between gap-3 border-t border-[var(--color-border)] pt-2">
            <span className="text-[var(--color-muted)]">{t("packages.addonCheckoutLineTotal")}</span>
            <span className="text-right font-medium tabular-nums">{lineTotalLabel} Ft {t("packages.taxSuffix")}</span>
          </div>
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
                placeholder="12345678-1-42"
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

          {purchaseAddonMutation.isError ? (
            <p className="text-sm text-red-600 dark:text-red-400">{t("common.errorGeneric")}</p>
          ) : null}

          <p className="text-xs text-[var(--color-muted)] leading-relaxed">{t("packages.flexNoteFinePrint")}</p>

          <div className="flex flex-wrap gap-3 pt-2">
            <button
              type="submit"
              disabled={submitDisabled}
              className="rounded-lg px-4 py-2.5 bg-[var(--color-primary)] text-[var(--color-on-primary)] text-sm font-semibold disabled:opacity-50"
            >
              {purchaseAddonMutation.isPending ? t("common.loading") : t("packages.addonCheckoutSubmit")}
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
