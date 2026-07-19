import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import api from "../../../api/axiosClient";
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import { useTranslation } from "../../../i18n";
import { queryKeys } from "../../../queryKeys";
import { useAuthStore } from "../../../store/authStore";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { formatForintFromCents } from "../../../utils/moneyFormatting";
import { useBillingOverview } from "../hooks/useBilling";

function moneyLabel(cents: unknown, locale: string): string {
  const value = Number(cents ?? 0);
  if (!Number.isFinite(value)) return `${formatForintFromCents(0, locale)} Ft`;
  return `${formatForintFromCents(value, locale)} Ft`;
}

function invoiceIssuedAtMs(invoice: Record<string, unknown>): number {
  const raw = String(invoice.issued_at ?? "");
  const parsed = new Date(raw).getTime();
  return Number.isFinite(parsed) ? parsed : 0;
}

export default function BillingSettleCheckoutPage() {
  const { t, locale } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const { data: billingOverview, isLoading } = useBillingOverview();
  const [cardNumber, setCardNumber] = useState("");
  const [cardExpiry, setCardExpiry] = useState("");
  const [cardCvc, setCardCvc] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!user || user.role !== "owner") {
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

  const estimated = billingOverview?.estimated_next_invoice ?? {};
  const invoices = Array.isArray(billingOverview?.invoices) ? billingOverview.invoices : [];
  const latestUnpaidInvoice = invoices
    .filter((invoice) => {
      const status = String((invoice as Record<string, unknown>).status ?? "").trim().toLowerCase();
      return status === "payment_failed" || status === "issued";
    })
    .sort((a, b) => invoiceIssuedAtMs(b as Record<string, unknown>) - invoiceIssuedAtMs(a as Record<string, unknown>))[0] as
    | Record<string, unknown>
    | undefined;
  const unpaidTotalCentsRaw = Number(latestUnpaidInvoice?.total_cents ?? 0);
  const unpaidTotalCents =
    Number.isFinite(unpaidTotalCentsRaw) && unpaidTotalCentsRaw > 0
      ? unpaidTotalCentsRaw
      : Math.max(0, Math.round(Number(latestUnpaidInvoice?.total ?? 0) * 100));
  const estimatedTotalCents = Number(estimated.total_cents ?? 0) || 0;
  const totalCents = unpaidTotalCents > 0 ? unpaidTotalCents : estimatedTotalCents;
  const submitDisabled = saving || !acceptTerms || !cardNumber.trim() || !cardExpiry.trim() || !cardCvc.trim();

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitDisabled) return;
    setSaving(true);
    setError(null);
    try {
      const res = await api.post<{ status?: string; message?: string }>("/billing/subscription/settle");
      const status = String(res.data?.status ?? "").trim().toLowerCase();
      if (status === "payment_failed" || status === "failed") {
        setError(res.data?.message || t("common.errorGeneric"));
        return;
      }
      // paid / simulated_paid / manual_paid / success — navigate away
      await queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview });
      await queryClient.invalidateQueries({ queryKey: queryKeys.billingAccessStatus });
      await queryClient.refetchQueries({ queryKey: queryKeys.billingOverview });
      navigate("/admin/szamlak");
    } catch (err) {
      setError(getApiErrorMessage(err) ?? t("common.errorGeneric"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="app-page">
      <div className="mx-auto max-w-2xl space-y-6">
        <PageHeader
          eyebrow={t("nav.invoices")}
          title={t("billing.settleCheckoutTitle")}
          description={t("billing.settleCheckoutIntro")}
        />

        {error ? <Alert tone="error">{error}</Alert> : null}

        <section className="app-surface p-6">
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm text-[var(--color-muted)]">{t("billing.settleCheckoutAmount")}</span>
            <span className="text-2xl font-semibold tabular-nums">{moneyLabel(totalCents, locale)}</span>
          </div>
        </section>

        <form onSubmit={handleSubmit} className="app-surface space-y-4 p-6">
          <p className="text-sm font-medium text-[var(--color-muted)]">{t("packages.checkoutPaymentSection")}</p>

          <label className="block">
            <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutCardNumber")}</span>
            <input
              value={cardNumber}
              onChange={(event) => setCardNumber(event.target.value)}
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
                onChange={(event) => setCardExpiry(event.target.value)}
                className="mt-1"
                autoComplete="cc-exp"
                placeholder="MM/YY"
              />
            </label>
            <label className="block">
              <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutCardCvc")}</span>
              <input
                value={cardCvc}
                onChange={(event) => setCardCvc(event.target.value)}
                className="mt-1"
                autoComplete="cc-csc"
                placeholder="CVC"
              />
            </label>
          </div>

          <label className="app-surface-muted flex cursor-pointer items-start gap-3 p-4 text-left text-sm text-[var(--color-muted)]">
            <input type="checkbox" checked={acceptTerms} onChange={(event) => setAcceptTerms(event.target.checked)} className="mt-1 shrink-0" style={{ width: "auto" }} />
            <span className="relative top-px ml-[3px]">{t("packages.checkoutAcceptSimulated")}</span>
          </label>

          <div className="flex gap-3 pt-2">
            <Button type="submit" disabled={submitDisabled} fullWidth size="lg">
              {saving ? t("common.loading") : t("billing.settlePayment")}
            </Button>
            <Button type="button" variant="secondary" size="lg" onClick={() => navigate("/admin/szamlak")}>
              {t("common.cancel")}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
