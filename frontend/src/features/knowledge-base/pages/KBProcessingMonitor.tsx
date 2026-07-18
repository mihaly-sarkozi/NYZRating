import { useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import { useTranslation } from "../../../i18n";
import { useBillingOverview } from "../../billing/hooks/useBilling";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { useLocaleSettings } from "../../settings/hooks/useSettings";
import ProcessingMonitorBreadcrumb from "../components/monitor/ProcessingMonitorBreadcrumb";
import ProcessingMonitorFlowListRow, {
  PROCESSING_MONITOR_FLOW_LIST_HEAD,
} from "../components/monitor/ProcessingMonitorFlowListRow";
import { useProcessingMonitorBundle } from "../hooks/useProcessingMonitorBundle";
import { collectMonitorFlowItemIds, useScopedFlowEventsByItem } from "../hooks/useScopedFlowEventsByItem";
import { useMonitorRouteRefetch } from "../hooks/useMonitorRouteRefetch";
import { useProgressClock } from "../hooks/useProgressClock";
import { useKbList } from "../hooks/useKb";
import { useKbTrainingSession } from "../hooks/useKbTrainingSession";
import { KbTrainingDialogs } from "../components/training/KbTrainingDialogs";
import {
  buildFlowSummaries,
  countOpenBlockingIssues,
} from "../utils/processingMonitorUtils";

export default function KBProcessingMonitor() {
  const { uuid } = useParams();
  const navigate = useNavigate();
  const { t, locale } = useTranslation();
  const { data: settings } = useLocaleSettings();
  const { data: kbList = [], isLoading: kbLoading } = useKbList();
  const kb = useMemo(() => kbList.find((item) => item.uuid === uuid), [kbList, uuid]);
  const { data: billingOverview } = useBillingOverview({ refetchOnMount: false });
  const paymentWarning = (billingOverview?.payment_warning as Record<string, unknown> | null | undefined) ?? null;
  const billingRestricted =
    String((billingOverview?.subscription as Record<string, unknown> | undefined)?.status ?? "").toLowerCase() ===
      "restricted" || paymentWarning?.is_expired === true;

  useEffect(() => {
    if (kbLoading) return;
    if (!uuid || !kb) {
      navigate("/kb", { replace: true });
    }
  }, [kb, kbLoading, navigate, uuid]);

  const { runsQuery, eventsQuery, issuesQuery, metricsQuery, isLive, pollOptions } =
    useProcessingMonitorBundle(uuid);
  const trainingSession = useKbTrainingSession({ billingRestricted, t });
  useMonitorRouteRefetch(uuid);
  const progressNowMs = useProgressClock(isLive);

  const flowItemIds = useMemo(
    () => collectMonitorFlowItemIds(runsQuery.data?.items, eventsQuery.data?.items),
    [runsQuery.data?.items, eventsQuery.data?.items],
  );
  const scopedEventsByItem = useScopedFlowEventsByItem(uuid, flowItemIds, pollOptions);

  const flows = useMemo(() => {
    const runs = runsQuery.data?.items ?? [];
    const events = eventsQuery.data?.items ?? [];
    const issues = issuesQuery.data?.items ?? [];
    return buildFlowSummaries(runs, events, issues, {
      nowMs: progressNowMs,
      scopedEventsByItem,
    });
  }, [
    eventsQuery.data?.items,
    issuesQuery.data?.items,
    progressNowMs,
    runsQuery.data?.items,
    scopedEventsByItem,
  ]);

  const blockingIssueCount = useMemo(
    () => countOpenBlockingIssues(issuesQuery.data?.items ?? []),
    [issuesQuery.data?.items],
  );

  const error =
    runsQuery.error || eventsQuery.error || issuesQuery.error
      ? getApiErrorMessage(runsQuery.error ?? eventsQuery.error ?? issuesQuery.error)
      : null;
  const loading = runsQuery.isLoading || eventsQuery.isLoading;

  return (
    <div className="app-page">
      <div className="app-page-container">
        <ProcessingMonitorBreadcrumb
          crumbs={[
            { label: t("kb.title"), to: "/kb" },
            { label: kb?.name ?? t("kb.processingMonitor.title") },
          ]}
        />
        <PageHeader
          eyebrow={t("kb.processingMonitor.eyebrow")}
          title={kb?.name ?? t("kb.processingMonitor.title")}
          description={t("kb.processingMonitor.intro")}
          actions={
            <div className="flex flex-wrap gap-2">
              {kb?.can_train ? (
                <Button
                  onClick={() => trainingSession.openTraining(kb)}
                  disabled={billingRestricted || trainingSession.loading}
                >
                  {t("kb.actionTrain")}
                </Button>
              ) : null}
              <Button variant="secondary" onClick={() => navigate("/kb")}>
                {t("kb.processingMonitor.backToList")}
              </Button>
            </div>
          }
        />

        {error ? <Alert tone="error">{error}</Alert> : null}

        <section className="mb-6 grid grid-cols-2 gap-3 rounded-2xl bg-[var(--color-card-muted)]/60 px-4 py-3 md:grid-cols-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.metrics.flows")}</p>
            <p className="text-lg font-semibold">{flows.length}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.metrics.chunks")}</p>
            <p className="text-lg font-semibold">{metricsQuery.data?.chunks_total ?? "—"}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.metrics.openIssues")}</p>
            <p className="text-lg font-semibold">{blockingIssueCount}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.metrics.failedDocs")}</p>
            <p className="text-lg font-semibold">{metricsQuery.data?.documents_failed ?? "—"}</p>
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-semibold text-[var(--color-foreground)]">{t("kb.processingMonitor.flowListTitle")}</h2>
          {loading ? <p className="text-sm text-[var(--color-muted)]">{t("common.loading")}</p> : null}
          {!loading && !flows.length ? <Alert tone="info">{t("kb.processingMonitor.emptyFlows")}</Alert> : null}
          {flows.length ? (
            <div className="app-table-wrap">
              <div className={`app-table-head ${PROCESSING_MONITOR_FLOW_LIST_HEAD}`}>
                <div>{t("kb.processingMonitor.table.document")}</div>
                <div>{t("kb.processingMonitor.table.status")}</div>
                <div className="md:text-right">{t("kb.processingMonitor.table.characters")}</div>
                <div className="md:text-right">{t("kb.processingMonitor.table.sizes")}</div>
                <div className="md:text-right">{t("kb.processingMonitor.table.actions")}</div>
              </div>
              <div className="divide-y divide-[var(--color-border)]">
                {flows.map((flow) => (
                  <ProcessingMonitorFlowListRow
                    key={flow.itemId}
                    kbUuid={uuid!}
                    flow={flow}
                    t={t}
                    locale={locale}
                    timezone={settings?.timezone}
                    dateFormat={settings?.date_format}
                    timeFormat={settings?.time_format}
                  />
                ))}
              </div>
            </div>
          ) : null}
        </section>
      </div>
      <KbTrainingDialogs t={t} session={trainingSession} />
    </div>
  );
}
