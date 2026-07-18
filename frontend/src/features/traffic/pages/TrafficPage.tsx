import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { useBillingOverview } from "../../billing/hooks/useBilling";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import { queryKeys } from "../../../queryKeys";
import TrafficSmsSection from "../components/TrafficSmsSection";
import { useTrafficSmsSends } from "../hooks/useTrafficSmsSends";

function localeTag(locale: string): string {
  if (locale === "en") return "en-GB";
  if (locale === "es") return "es-ES";
  return "hu-HU";
}

function numberValue(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatDate(value: string | undefined, locale: string): string {
  if (!value) return "—";
  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(localeTag(locale), { dateStyle: "long" });
}

const SMS_PACK_CHECKOUT_ITEMS = "question_pack_100:1";

export default function TrafficPage() {
  const { t, locale } = useTranslation();
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { data: billingOverview, isLoading, error: billingError } = useBillingOverview({
    refetchOnMount: "always",
  });
  const isOwner = user?.role === "owner";
  const canViewTraffic = user?.role === "owner" || user?.role === "admin";
  const [formOpen, setFormOpen] = useState(false);
  const { data: smsSends } = useTrafficSmsSends();

  useEffect(() => {
    const st = location.state as {
      addonCheckoutComplete?: boolean;
      checkoutComplete?: boolean;
      upgradeCheckoutComplete?: boolean;
      message?: string;
    } | null;
    const completed = Boolean(
      st?.addonCheckoutComplete || st?.checkoutComplete || st?.upgradeCheckoutComplete
    );
    if (!completed) return;
    const message =
      typeof st?.message === "string" && st.message.trim()
        ? st.message
        : t("packages.addonCheckoutSuccessMessage");
    toast.success(message);
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview }),
      queryClient.invalidateQueries({ queryKey: queryKeys.trafficSmsSends }),
      queryClient.invalidateQueries({ queryKey: queryKeys.trafficOverview }),
    ]);
    navigate(location.pathname, { replace: true, state: {} });
  }, [location.state, location.pathname, navigate, queryClient, t]);

  const billingErrMsg =
    billingError && typeof (billingError as { response?: { data?: { detail?: string } } })?.response?.data?.detail === "string"
      ? (billingError as { response?: { data?: { detail?: string } } }).response!.data!.detail
      : billingError
        ? t("common.errorGeneric")
        : null;

  if (!user || !canViewTraffic) {
    return (
      <div className="p-6 min-h-full bg-[var(--color-background)] flex justify-center">
        <div className="w-full max-w-2xl bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded">
          {t("settings.ownerOnly")}
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)] flex justify-center">
        <div className="max-w-2xl text-center">{t("common.loading")}</div>
      </div>
    );
  }

  const usage = billingOverview?.usage ?? {};
  const subscription = billingOverview?.subscription ?? {};
  const currentPlanCode = String(subscription.plan_code ?? "free");
  const canExpandPaidAddons = isOwner && currentPlanCode !== "free";
  const periodValidUntilLabel = formatDate(billingOverview?.current_period_end_iso, locale);
  const questions = (usage.questions as Record<string, unknown>) ?? {};
  const usedQuestions = numberValue(questions.used_total);
  const totalQuestions = numberValue(questions.available_total);
  const remainingQuestions = numberValue(
    smsSends?.remaining_total ?? questions.remaining_total ?? Math.max(0, totalQuestions - usedQuestions)
  );
  const exhausted = remainingQuestions <= 0;
  const isFreePlan = currentPlanCode === "free";

  const handleExpandQuota = () => {
    if (canExpandPaidAddons) {
      navigate(`/admin/pricing/addon-checkout?items=${encodeURIComponent(SMS_PACK_CHECKOUT_ITEMS)}`);
      return;
    }
    navigate("/admin/pricing");
  };

  return (
    <div className="app-page">
      <div className="app-page-container">
        <div className="app-page-header md:items-start">
          <div>
            <p className="app-page-eyebrow">{t("nav.traffic")}</p>
            <h1 className="app-page-title">{t("traffic.overviewLabel")}</h1>
            {!exhausted ? (
              <Button
                type="button"
                size="lg"
                className="mt-4 !px-6 !py-3.5 !text-base font-semibold"
                onClick={() => setFormOpen((open) => !open)}
              >
                {t("traffic.smsSendButton")}
              </Button>
            ) : (
              <div className="app-page-intro space-y-2">
                <p>{isFreePlan ? t("traffic.smsLimitExhaustedFree") : t("traffic.smsLimitExhausted")}</p>
                <Link
                  to="/admin/pricing"
                  className="inline-flex text-sm font-medium text-[var(--color-accent-foreground)] underline"
                >
                  {t("traffic.smsUpgradeLink")}
                </Link>
              </div>
            )}
          </div>
          <aside className="min-w-[220px] rounded-2xl border border-[var(--color-success-border)] bg-[var(--color-success-bg)] px-4 py-3 text-[var(--color-success-text)]">
            <p className="text-xs font-medium uppercase tracking-wide">{t("traffic.smsRemainingLabel")}</p>
            <div className="mt-1 flex flex-wrap items-center justify-between gap-3">
              <p className="text-3xl font-semibold tracking-tight">{Math.max(0, remainingQuestions)}</p>
              {isOwner ? (
                <Button type="button" variant="primary" size="sm" onClick={handleExpandQuota}>
                  {t("traffic.smsExpandQuota")}
                </Button>
              ) : null}
            </div>
            <p className="mt-2 text-xs">
              {t("traffic.smsPeriodValidUntil")}: <span className="font-medium">{periodValidUntilLabel}</span>
            </p>
          </aside>
        </div>

        {billingErrMsg ? (
          <Alert tone="error">{billingErrMsg}</Alert>
        ) : null}

        <TrafficSmsSection
          remainingTotal={remainingQuestions}
          formOpen={formOpen}
          onFormOpenChange={setFormOpen}
        />
      </div>
    </div>
  );
}
