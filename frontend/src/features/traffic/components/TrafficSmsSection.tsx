// frontend/src/features/traffic/components/TrafficSmsSection.tsx
// Feladat: Ajánlások oldal – ajánlás űrlap (keret nélkül), SMS keret státusz és kiküldési napló.
// Sárközi Mihály - 2026.07.18

import { useMemo, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { useCreateTrafficSmsSend, useTrafficSmsSends } from "../hooks/useTrafficSmsSends";
import { isValidHuMobile, normalizeHuMobile } from "../validation/huMobile";

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

function localDateString(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

function buildScheduledAt(date: string, hour: number): Date {
  const parsed = new Date(`${date}T12:00:00`);
  parsed.setHours(hour, 0, 0, 0);
  return parsed;
}

function formatDateTime(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const tag = locale === "en" ? "en-GB" : locale === "es" ? "es-ES" : "hu-HU";
  return date.toLocaleString(tag, { dateStyle: "short", timeStyle: "short" });
}

type TrafficSmsSectionProps = {
  remainingTotal: number;
  formOpen: boolean;
  onFormOpenChange: (open: boolean) => void;
};

export default function TrafficSmsSection({
  remainingTotal,
  formOpen,
  onFormOpenChange,
}: TrafficSmsSectionProps) {
  const { t, locale } = useTranslation();
  const { data, isLoading, error } = useTrafficSmsSends();
  const createMutation = useCreateTrafficSmsSend();
  const now = useMemo(() => new Date(), []);
  const [recipientName, setRecipientName] = useState("");
  const [phone, setPhone] = useState("");
  const [sendDate, setSendDate] = useState(localDateString(now));
  const [sendHour, setSendHour] = useState(now.getHours());
  const [fieldError, setFieldError] = useState<string | null>(null);

  const remaining = data?.remaining_total ?? remainingTotal;
  const exhausted = remaining <= 0;
  const items = data?.items ?? [];

  const resetForm = () => {
    const current = new Date();
    setRecipientName("");
    setPhone("");
    setSendDate(localDateString(current));
    setSendHour(current.getHours());
    setFieldError(null);
  };

  const handlePlusSixty = () => {
    const next = buildScheduledAt(sendDate, sendHour);
    next.setMinutes(next.getMinutes() + 60);
    setSendDate(localDateString(next));
    setSendHour(next.getHours());
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setFieldError(null);
    if (!recipientName.trim()) {
      setFieldError(t("traffic.smsNameRequired"));
      return;
    }
    if (!isValidHuMobile(phone)) {
      setFieldError(t("traffic.smsInvalidHuMobile"));
      return;
    }
    try {
      const scheduled = buildScheduledAt(sendDate, sendHour);
      await createMutation.mutateAsync({
        recipient_name: recipientName.trim(),
        phone: normalizeHuMobile(phone),
        scheduled_at: scheduled.toISOString(),
      });
      toast.success(t("traffic.smsSendSuccess"));
      resetForm();
      onFormOpenChange(false);
    } catch (err) {
      toast.error(getApiErrorMessage(err) ?? t("common.errorGeneric"));
    }
  };

  const closeForm = () => {
    resetForm();
    onFormOpenChange(false);
  };

  return (
    <section className="space-y-6">
      <Modal
        open={formOpen && !exhausted}
        onClose={closeForm}
        closeOnOverlay
        panelClassName="max-w-2xl w-full"
      >
        <ModalHeader title={t("traffic.smsSendButton")} />
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block text-sm text-[var(--color-label)]">
              {t("traffic.smsRecipientName")} *
              <input
                autoFocus
                value={recipientName}
                onChange={(event) => setRecipientName(event.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm"
                required
              />
            </label>
            <label className="block text-sm text-[var(--color-label)]">
              {t("traffic.smsPhone")} *
              <input
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                placeholder="06201234567"
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm"
                required
              />
              <span className="mt-1 block text-xs text-[var(--color-muted)]">{t("traffic.smsPhoneHint")}</span>
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-[1fr_auto_auto] md:items-end">
            <label className="block text-sm text-[var(--color-label)]">
              {t("traffic.smsDate")} *
              <input
                type="date"
                value={sendDate}
                onChange={(event) => setSendDate(event.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm"
                required
              />
            </label>
            <label className="block text-sm text-[var(--color-label)]">
              {t("traffic.smsHour")} *
              <select
                value={sendHour}
                onChange={(event) => setSendHour(Number(event.target.value))}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm"
              >
                {Array.from({ length: 24 }, (_, hour) => (
                  <option key={hour} value={hour}>
                    {pad2(hour)}:00
                  </option>
                ))}
              </select>
            </label>
            <Button type="button" size="sm" className="shrink-0 whitespace-nowrap px-2.5" onClick={handlePlusSixty}>
              {t("traffic.smsPlusSixty")}
            </Button>
          </div>

          {fieldError ? <Alert tone="error">{fieldError}</Alert> : null}

          <ModalFooter>
            <Button type="button" variant="secondary" onClick={closeForm}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? t("common.loading") : t("traffic.smsSubmit")}
            </Button>
          </ModalFooter>
        </form>
      </Modal>

      <div className="app-surface p-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-[var(--color-muted)]">{t("traffic.smsLogTitle")}</p>
            <h2 className="mt-1 text-xl font-semibold text-[var(--color-foreground)]">{t("traffic.smsLogSubtitle")}</h2>
          </div>
        </div>

        {error ? <Alert tone="error" className="mt-4">{getApiErrorMessage(error) ?? t("common.errorGeneric")}</Alert> : null}

        <div className="app-table-wrap mt-6">
          {isLoading ? (
            <p className="px-5 py-8 text-center text-sm text-[var(--color-muted)]">{t("common.loading")}</p>
          ) : items.length === 0 ? (
            <p className="px-5 py-8 text-center text-sm text-[var(--color-muted)]">{t("traffic.smsLogEmpty")}</p>
          ) : (
            <>
              <div className="app-table-head hidden grid-cols-[1.1fr_1fr_1fr_0.8fr] gap-4 px-5 py-3 text-sm font-medium md:grid">
                <div>{t("traffic.smsColName")}</div>
                <div>{t("traffic.smsColPhone")}</div>
                <div>{t("traffic.smsColScheduled")}</div>
                <div>{t("traffic.smsColStatus")}</div>
              </div>
              <div className="divide-y divide-[var(--color-border)]">
                {items.map((item) => (
                  <div key={item.id} className="grid gap-2 px-5 py-4 md:grid-cols-[1.1fr_1fr_1fr_0.8fr] md:items-center">
                    <div className="font-medium text-[var(--color-foreground)]">{item.recipient_name}</div>
                    <div className="text-[var(--color-muted-foreground)]">{item.phone}</div>
                    <div className="text-[var(--color-muted-foreground)]">{formatDateTime(item.scheduled_at, locale)}</div>
                    <div>
                      <span className="inline-flex rounded-full border border-[var(--color-success-border)] bg-[var(--color-success-bg)] px-2.5 py-1 text-xs font-medium text-[var(--color-success-text)]">
                        {t("traffic.smsStatusSent")}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
