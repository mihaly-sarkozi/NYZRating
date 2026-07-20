import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import {
  useBillingOverview,
  useCancelSubscriptionMutation,
  useDeleteServiceAccessMutation,
  useRestoreSubscriptionRenewalMutation,
  useUpdateSubscriptionMutation,
} from "../../billing/hooks/useBilling";
import { useLocaleSettings } from "../../settings/hooks/useSettings";
import { formatDateOnly } from "../../../utils/dateTimeFormatting";
import {
  formatPlanResourceBlockMessage,
  planResourceBlock,
  readBillingResourceUsage,
} from "../planEligibility";
import Alert from "../../../components/ui/Alert";
import PageHeader from "../../../components/ui/PageHeader";
import PackageCurrentPlanBanner from "../components/PackageCurrentPlanBanner";
import PackageCancellationSection from "../components/PackageCancellationSection";
import PackageExpandBanner from "../components/PackageExpandBanner";
import PackagePlanCard from "../components/PackagePlanCard";
import PackageStatusModals from "../components/PackageStatusModals";
import {
  formatSubscriptionDateForBanner,
  includedNumber,
  isFreePlan,
  isScheduledChange,
  sortPlans,
  tBannerBilledPeriod,
  type BillingPeriod,
} from "../components/packageUtils";

export default function PackagesPage() {
  const { t, locale } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { data: settings } = useLocaleSettings({ enabled: user?.role === "owner" });
  const { data: billingOverview, isLoading: billingLoading, error: billingError } = useBillingOverview();
  const updateSubscriptionMutation = useUpdateSubscriptionMutation();
  const cancelSubscriptionMutation = useCancelSubscriptionMutation();
  const restoreSubscriptionRenewalMutation = useRestoreSubscriptionRenewalMutation();
  const deleteServiceAccessMutation = useDeleteServiceAccessMutation();
  const [selectedBillingPeriod, setSelectedBillingPeriod] = useState<BillingPeriod>("quarterly");
  const [planChangePending, setPlanChangePending] = useState<{ planCode: string; billingPeriod: BillingPeriod } | null>(null);
  const [planChangeSuccess, setPlanChangeSuccess] = useState<{ message: string; status: string } | null>(null);
  const [resourceBlockMessage, setResourceBlockMessage] = useState<string | null>(null);

  const billingErrMsg =
    billingError && typeof (billingError as { response?: { data?: { detail?: string } } })?.response?.data?.detail === "string"
      ? (billingError as { response?: { data?: { detail?: string } } }).response!.data!.detail
      : billingError
        ? t("common.errorGeneric")
        : null;
  const billingMutationError = updateSubscriptionMutation.error ? t("common.errorGeneric") : null;
  const displayError = billingErrMsg ?? billingMutationError;

  const catalog = useMemo(() => billingOverview?.catalog ?? [], [billingOverview?.catalog]);
  const planEntries = useMemo(() => catalog.filter((item) => item.entry_type === "plan"), [catalog]);
  const paidPlans = useMemo(() => sortPlans(planEntries.filter((p) => !isFreePlan(p))), [planEntries]);

  const subscription = billingOverview?.subscription ?? {};
  const currentPlanCode = String(subscription.plan_code ?? "free");
  const { usedGb: usedStorageGb, usedKbCount } = readBillingResourceUsage(
    billingOverview?.usage as Record<string, unknown> | undefined
  );
  const scheduledPlanCode = subscription.scheduled_plan_code != null ? String(subscription.scheduled_plan_code) : null;
  const rawBillingPeriod = String(subscription.billing_period ?? "monthly").toLowerCase();
  const currentBillingPeriod: BillingPeriod =
    rawBillingPeriod === "monthly" || rawBillingPeriod === "quarterly" || rawBillingPeriod === "yearly"
      ? rawBillingPeriod
      : "monthly";

  const smsPackCheckoutItems = "question_pack_50:1";
  useEffect(() => {
    if (!planChangePending && !planChangeSuccess && !resourceBlockMessage) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (resourceBlockMessage) setResourceBlockMessage(null);
      else if (planChangeSuccess) setPlanChangeSuccess(null);
      else if (planChangePending && !updateSubscriptionMutation.isPending) setPlanChangePending(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [planChangePending, planChangeSuccess, resourceBlockMessage, updateSubscriptionMutation.isPending]);

  useEffect(() => {
    const st = location.state as {
      checkoutComplete?: boolean;
      addonCheckoutComplete?: boolean;
      upgradeCheckoutComplete?: boolean;
      message?: string;
      status?: string;
    } | null;
    const msg = st?.message;
    const ok =
      (st?.checkoutComplete || st?.addonCheckoutComplete || st?.upgradeCheckoutComplete) &&
      typeof msg === "string" &&
      msg.length > 0;
    if (ok && msg) {
      setPlanChangeSuccess({ message: msg, status: st.status ?? "updated" });
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, location.pathname, navigate]);

  const handleSwitchToPlan = (planCode: string) => {
    const target = catalog.find((e) => e.entry_type === "plan" && e.code === planCode);
    if (!target) return;
    const isTargetCurrent = planCode === currentPlanCode;
    const block = planResourceBlock(target, usedStorageGb, usedKbCount, isTargetCurrent);
    if (block.blocked) {
      setResourceBlockMessage(formatPlanResourceBlockMessage(block, usedStorageGb, usedKbCount, t));
      return;
    }
    if (currentPlanCode === "free") {
      navigate(`/admin/pricing/checkout?plan=${encodeURIComponent(planCode)}&period=${selectedBillingPeriod}`);
      return;
    }
    if (isScheduledChange(currentPlanCode, planCode, currentBillingPeriod, selectedBillingPeriod)) {
      setPlanChangePending({ planCode, billingPeriod: selectedBillingPeriod });
      return;
    }
    navigate(
      `/admin/pricing/upgrade-checkout?plan=${encodeURIComponent(planCode)}&period=${selectedBillingPeriod}`
    );
  };

  const confirmPlanChange = async () => {
    if (!planChangePending) return;
    try {
      const res = await updateSubscriptionMutation.mutateAsync({
        plan_code: planChangePending.planCode,
        billing_period: planChangePending.billingPeriod,
      });
      setPlanChangePending(null);
      setPlanChangeSuccess({ message: res.message, status: res.status });
    } catch {
      /* hiba a mutáción */
    }
  };

  const periodToLabel =
    billingOverview?.current_period_end_iso != null && billingOverview.current_period_end_iso !== ""
      ? formatDateOnly(billingOverview.current_period_end_iso, {
          locale,
          timezone: settings?.timezone,
          dateFormat: settings?.date_format,
          dateStyle: settings?.date_format ? undefined : "long",
        })
      : "—";
  const currentPlanName =
    catalog.find((e) => e.entry_type === "plan" && e.code === currentPlanCode)?.name ?? currentPlanCode;
  const freePlanEntry = catalog.find((e) => e.entry_type === "plan" && e.code === "free");
  const freeSmsCount = includedNumber(freePlanEntry ?? null, "questions_monthly", 3);
  const scheduledPlanName =
    scheduledPlanCode != null ? catalog.find((e) => e.entry_type === "plan" && e.code === scheduledPlanCode)?.name ?? scheduledPlanCode : null;
  const scheduledPeriodRaw = String(subscription.scheduled_billing_period ?? "").toLowerCase();
  const scheduledBillingPeriod: BillingPeriod =
    scheduledPeriodRaw === "yearly" ? "yearly" : scheduledPeriodRaw === "quarterly" ? "quarterly" : "monthly";

  const trialEndLabel = formatSubscriptionDateForBanner(subscription.trial_ends_at, locale, settings?.timezone, settings?.date_format);
  const bannerValidityDate =
    currentPlanCode === "free"
      ? trialEndLabel ?? (periodToLabel !== "—" ? periodToLabel : null)
      : periodToLabel !== "—"
        ? periodToLabel
        : null;

  const pendingTargetPlan = planChangePending
    ? catalog.find((e) => e.entry_type === "plan" && e.code === planChangePending.planCode) ?? null
    : null;
  const pendingBilledPhrase =
    planChangePending != null ? tBannerBilledPeriod(planChangePending.billingPeriod, t) : "";
  const pendingIsDowngrade =
    planChangePending != null
      ? isScheduledChange(currentPlanCode, planChangePending.planCode, currentBillingPeriod, planChangePending.billingPeriod)
      : false;

  const showBannerExpandButton = currentPlanCode !== "free";
  const cancellationRequest =
    subscription.cancellation_request && typeof subscription.cancellation_request === "object"
      ? (subscription.cancellation_request as Record<string, unknown>)
      : null;
  const autoRenewal = subscription.auto_renewal == null ? cancellationRequest == null : Boolean(subscription.auto_renewal);
  const cancellationMutationError =
    deleteServiceAccessMutation.error ??
    restoreSubscriptionRenewalMutation.error ??
    cancelSubscriptionMutation.error;
  const cancellationError: string | null =
    cancellationMutationError &&
    typeof (cancellationMutationError as { response?: { data?: { detail?: string } } })?.response?.data?.detail === "string"
      ? ((cancellationMutationError as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? null)
      : cancellationMutationError
        ? t("common.errorGeneric")
        : null;

  const handleCancelSubscription = async (body: { reason_code: string; reason_text: string }) => {
    try {
      await cancelSubscriptionMutation.mutateAsync(body);
    } catch {
      /* axios error surfaced via mutation */
    }
  };

  const handleDeleteServiceAccess = async () => {
    try {
      await deleteServiceAccessMutation.mutateAsync();
      logout();
      navigate("/service-deleted", { replace: true });
    } catch {
      /* axios error surfaced via mutation */
    }
  };

  const handleRestoreSubscriptionRenewal = async () => {
    try {
      await restoreSubscriptionRenewalMutation.mutateAsync();
    } catch {
      /* axios error surfaced via mutation */
    }
  };

  if (!user || user.role !== "owner") {
    return (
      <div className="p-6 min-h-full bg-[var(--color-background)]">
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded">
          {t("settings.ownerOnly")}
        </div>
      </div>
    );
  }

  if (billingLoading) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)]">
        <div>{t("common.loading")}</div>
      </div>
    );
  }

  return (
    <div className="app-page text-[var(--color-foreground)]">
      <div className="w-full max-w-6xl mx-auto mb-6 px-2">
        <PageHeader
          eyebrow={t("nav.packages")}
          title={t("nav.packages")}
        />
      </div>

      <PackageCurrentPlanBanner
        currentPlanName={currentPlanName}
        currentPlanCode={currentPlanCode}
        currentBillingPeriod={currentBillingPeriod}
        bannerValidityDate={bannerValidityDate}
        freeSmsCount={freeSmsCount}
        scheduledPlanCode={scheduledPlanCode}
        scheduledPlanName={scheduledPlanName}
        scheduledBillingPeriod={scheduledBillingPeriod}
        selectedBillingPeriod={selectedBillingPeriod}
        t={t}
        onSelectBillingPeriod={setSelectedBillingPeriod}
      />

      {currentPlanCode !== "free" ? (
        <PackageCancellationSection
          activeKnowledgeBaseCount={usedKbCount}
          autoRenewal={autoRenewal}
          cancellationRequest={cancellationRequest}
          validUntilLabel={bannerValidityDate ?? periodToLabel}
          currentHost={typeof window !== "undefined" ? window.location.host : ""}
          locale={locale}
          t={t}
          cancelPending={cancelSubscriptionMutation.isPending}
          restorePending={restoreSubscriptionRenewalMutation.isPending}
          deletePending={deleteServiceAccessMutation.isPending}
          errorMessage={cancellationError}
          onCancel={(body) => void handleCancelSubscription(body)}
          onRestoreRenewal={() => void handleRestoreSubscriptionRenewal()}
          onDeleteAccess={() => void handleDeleteServiceAccess()}
          onOpenKnowledgeBases={() => navigate("/kb")}
        />
      ) : null}

      {displayError && (
        <Alert tone="error" className="mb-4">
          {displayError}
        </Alert>
      )}

      <div className="w-full max-w-6xl mx-auto space-y-10">
        <div className="grid gap-4 md:grid-cols-3 md:items-stretch">
          {paidPlans.map((plan) => (
            <PackagePlanCard
              key={plan.code}
              plan={plan}
              featured={plan.code === "pro"}
              currentPlanCode={currentPlanCode}
              scheduledPlanCode={scheduledPlanCode}
              selectedBillingPeriod={selectedBillingPeriod}
              currentBillingPeriod={currentBillingPeriod}
              pending={updateSubscriptionMutation.isPending}
              resourceBlocked={planResourceBlock(plan, usedStorageGb, usedKbCount, plan.code === currentPlanCode).blocked}
              t={t}
              locale={locale}
              onSwitch={handleSwitchToPlan}
            />
          ))}
        </div>

        {showBannerExpandButton ? (
          <PackageExpandBanner
            t={t}
            onOpen={() => navigate(`/admin/pricing/addon-checkout?items=${encodeURIComponent(smsPackCheckoutItems)}`)}
          />
        ) : null}

        <PackageStatusModals
          planChangePending={planChangePending}
          planChangeSuccess={planChangeSuccess}
          resourceBlockMessage={resourceBlockMessage}
          pendingTargetPlan={pendingTargetPlan}
          pendingBilledPhrase={pendingBilledPhrase}
          pendingIsDowngrade={pendingIsDowngrade}
          updatePending={updateSubscriptionMutation.isPending}
          t={t}
          onClosePending={() => setPlanChangePending(null)}
          onConfirmPlanChange={() => void confirmPlanChange()}
          onCloseSuccess={() => setPlanChangeSuccess(null)}
          onCloseResourceBlock={() => setResourceBlockMessage(null)}
        />

      </div>
    </div>
  );
}
