import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import { useTranslation } from "../../../i18n";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { downloadTrainingItemRaw } from "../../../api/services/kb/kbIngestApi";
import ProcessingMonitorLiveBanner from "../components/monitor/ProcessingMonitorLiveBanner";
import ProcessingMonitorBreadcrumb from "../components/monitor/ProcessingMonitorBreadcrumb";
import ProcessingStatusBadge from "../components/monitor/ProcessingStatusBadge";
import { useProcessingMonitorBundle } from "../hooks/useProcessingMonitorBundle";
import { useMonitorRouteRefetch } from "../hooks/useMonitorRouteRefetch";
import { useProgressClock } from "../hooks/useProgressClock";
import {
  useDeleteTrainingItemMutation,
  useKbList,
  useRetrainTrainingItemMutation,
  useRetrainTrainingItemPreview,
} from "../hooks/useKb";
import { parseTrainingQuotaError } from "../../../api/services/kb/kbIngestApi";
import TrainingItemActionModal, {
  type TrainingItemActionMode,
} from "../components/monitor/TrainingItemActionModal";
import {
  buildItemCatalogFromRuns,
  deriveActiveProgress,
  deriveFlowProgress,
  resolveFlowStatus,
  refineFlowStatusForProgress,
  isFlowInProgress,
  translateProcessingMonitorKey,
} from "../utils/processingMonitorUtils";

export default function KBProcessingFlowDetail() {
  const { uuid, itemId: rawItemId } = useParams();
  const itemId = rawItemId ? decodeURIComponent(rawItemId) : undefined;
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { data: kbList = [], isLoading: kbLoading } = useKbList();
  const kb = useMemo(() => kbList.find((item) => item.uuid === uuid), [kbList, uuid]);

  const { runsQuery, eventsQuery, referenceEventsQuery, issuesQuery, understandingQuery, isLive } =
    useProcessingMonitorBundle(uuid, { trainingItemId: itemId });
  useMonitorRouteRefetch(uuid);
  const progressNowMs = useProgressClock(isLive);

  useEffect(() => {
    if (kbLoading) return;
    if (!uuid) navigate("/kb", { replace: true });
  }, [kbLoading, navigate, uuid]);

  const catalog = useMemo(() => buildItemCatalogFromRuns(runsQuery.data?.items ?? []), [runsQuery.data?.items]);
  const meta = itemId ? catalog.get(itemId) : undefined;
  const charCountByItemId = useMemo(() => {
    const index = new Map<string, number>();
    for (const [id, entry] of catalog) {
      if (entry.charCount != null && entry.charCount > 0) {
        index.set(id, entry.charCount);
      }
    }
    return index;
  }, [catalog]);
  const fallbackTitle = meta?.title ?? itemId ?? t("kb.processingMonitor.unknownDocument");
  const title = (() => {
    if (meta && !meta.hasExplicitTitle && meta.inputType === "text") {
      const preview = (meta.textPreview ?? "").trim();
      if (preview) return `“${preview}”`;
      return t("kb.processingMonitor.typedTextLabel");
    }
    return fallbackTitle;
  })();
  const inputType = meta?.inputType ?? "unknown";
  const showRawAction = !!uuid && !!itemId && (inputType === "file" || inputType === "text");

  const job = understandingQuery.data?.job;

  const activeProgress = useMemo(
    () => deriveActiveProgress(eventsQuery.data?.items ?? []),
    [eventsQuery.data?.items],
  );

  const flowProgress = useMemo(
    () =>
      deriveFlowProgress(
        eventsQuery.data?.items ?? [],
        issuesQuery.data?.items ?? [],
        understandingQuery.data?.steps ?? [],
        {
          referenceEvents: referenceEventsQuery.data?.items ?? eventsQuery.data?.items ?? [],
          currentItemId: itemId ?? null,
          nowMs: progressNowMs,
          targetCharCount: meta?.charCount ?? null,
          charCountByItemId,
        },
      ),
    [
      eventsQuery.data?.items,
      issuesQuery.data?.items,
      understandingQuery.data?.steps,
      referenceEventsQuery.data?.items,
      itemId,
      progressNowMs,
      meta?.charCount,
      charCountByItemId,
    ],
  );

  const flowStatus = useMemo(() => {
    const base = resolveFlowStatus(eventsQuery.data?.items ?? [], issuesQuery.data?.items ?? [], {
      jobStatus: job?.status,
      ingestItemStatus: meta?.ingestStatus ?? null,
    });
    return refineFlowStatusForProgress(base, {
      completedSteps: flowProgress?.completedSteps ?? 0,
      hasActiveStep: Boolean(activeProgress?.module),
    });
  }, [
    activeProgress?.module,
    eventsQuery.data?.items,
    flowProgress?.completedSteps,
    issuesQuery.data?.items,
    job?.status,
    meta?.ingestStatus,
  ]);

  const isRunning = isFlowInProgress(flowStatus);

  const error =
    eventsQuery.error || issuesQuery.error || understandingQuery.error
      ? getApiErrorMessage(eventsQuery.error ?? issuesQuery.error ?? understandingQuery.error)
      : null;

  const monitorUrl = `/kb/monitor/${uuid}`;

  const [rawError, setRawError] = useState<string | null>(null);
  const [rawLoading, setRawLoading] = useState(false);

  const handleOpenRaw = async () => {
    if (!uuid || !itemId || rawLoading) return;
    setRawError(null);
    setRawLoading(true);
    try {
      const { blob } = await downloadTrainingItemRaw(uuid, itemId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (downloadError) {
      console.error("Failed to download training item raw content", downloadError);
      setRawError(t("kb.processingMonitor.downloadRawError"));
    } finally {
      setRawLoading(false);
    }
  };

  const [actionMode, setActionMode] = useState<TrainingItemActionMode | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const deleteMutation = useDeleteTrainingItemMutation();
  const retrainMutation = useRetrainTrainingItemMutation();
  const retrainPreview = useRetrainTrainingItemPreview(
    uuid ?? null,
    itemId ?? null,
    actionMode === "retrain",
  );
  const isActionBusy = deleteMutation.isPending || retrainMutation.isPending;
  const actionsDisabled = isActionBusy || isRunning;
  const actionsDisabledTooltip = isRunning ? t("kb.processingMonitor.flowDisabledWhileRunning") : null;

  const openActionModal = (mode: TrainingItemActionMode) => {
    if (actionsDisabled) return;
    setActionError(null);
    setActionMode(mode);
  };

  const closeActionModal = () => {
    if (isActionBusy) return;
    setActionMode(null);
    setActionError(null);
  };

  const handleConfirmAction = async () => {
    if (!actionMode || !uuid || !itemId) return;
    setActionError(null);
    try {
      if (actionMode === "delete") {
        await deleteMutation.mutateAsync({ kbUuid: uuid, itemId });
        setActionMode(null);
        navigate(monitorUrl);
      } else {
        await retrainMutation.mutateAsync({ kbUuid: uuid, itemId });
        setActionMode(null);
        navigate(monitorUrl);
      }
    } catch (mutationError) {
      const quota = parseTrainingQuotaError(mutationError);
      if (quota) {
        await retrainPreview.refetch();
        setActionError(quota.message ?? t("kb.processingMonitor.retrainQuotaExceededMessage"));
        return;
      }
      const fallbackKey =
        actionMode === "delete"
          ? "kb.processingMonitor.deleteError"
          : "kb.processingMonitor.retrainError";
      setActionError(getApiErrorMessage(mutationError) ?? t(fallbackKey));
    }
  };

  return (
    <div className="app-page">
      <div className="app-page-container">
        <ProcessingMonitorBreadcrumb
          crumbs={[
            { label: t("kb.title"), to: "/kb" },
            { label: kb?.name ?? t("kb.processingMonitor.title"), to: monitorUrl },
            { label: title },
          ]}
        />
        <PageHeader
          eyebrow={t("kb.processingMonitor.flowDetailEyebrow")}
          title={title}
          description={t("kb.processingMonitor.flowDetailIntro")}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              {showRawAction ? (
                <Button
                  variant="secondary"
                  onClick={handleOpenRaw}
                  disabled={rawLoading}
                  title={t("kb.processingMonitor.openRawTooltip")}
                >
                  <span className="inline-flex items-center gap-2">
                    <svg
                      viewBox="0 0 24 24"
                      className="h-4 w-4"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                      <polyline points="15 3 21 3 21 9" />
                      <line x1="10" y1="14" x2="21" y2="3" />
                    </svg>
                    {t("kb.processingMonitor.openRawTooltip")}
                  </span>
                </Button>
              ) : null}
              <Button
                variant="secondary"
                onClick={() => openActionModal("retrain")}
                disabled={actionsDisabled}
                title={actionsDisabledTooltip ?? t("kb.processingMonitor.retrainTooltip")}
              >
                <span className="inline-flex items-center gap-2">
                  <svg
                    viewBox="0 0 24 24"
                    className={`h-4 w-4 ${retrainMutation.isPending ? "animate-spin" : ""}`}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <polyline points="23 4 23 10 17 10" />
                    <polyline points="1 20 1 14 7 14" />
                    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10" />
                    <path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14" />
                  </svg>
                  {t("kb.processingMonitor.retrainTooltip")}
                </span>
              </Button>
              <Button
                variant="danger"
                onClick={() => openActionModal("delete")}
                disabled={actionsDisabled}
                title={actionsDisabledTooltip ?? t("kb.processingMonitor.deleteTooltip")}
              >
                <span className="inline-flex items-center gap-2">
                  <svg
                    viewBox="0 0 24 24"
                    className="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                    <path d="M10 11v6" />
                    <path d="M14 11v6" />
                    <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />
                  </svg>
                  {t("kb.processingMonitor.deleteTooltip")}
                </span>
              </Button>
              <Button variant="secondary" onClick={() => navigate(monitorUrl)}>
                {t("kb.processingMonitor.backToMonitor")}
              </Button>
            </div>
          }
        />

        {rawError ? <Alert tone="error">{rawError}</Alert> : null}

        <ProcessingMonitorLiveBanner
          isLive={isLive}
          activeFlow={
            activeProgress
              ? {
                  activeModule: activeProgress.module,
                  activeStage: activeProgress.stage,
                  activeStep: activeProgress.step,
                  latestMessage: activeProgress.message,
                }
              : null
          }
          progress={flowProgress}
        />

        {!isLive && !isFlowInProgress(flowStatus) ? (
          <section className="mb-6 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
            <div className="flex flex-wrap items-center gap-3">
              <ProcessingStatusBadge
                status={flowStatus}
                label={translateProcessingMonitorKey(t, flowStatus, "flowStatus")}
              />
              {flowStatus === "completed" || flowStatus === "partial" ? (
                <div className="min-w-[10rem] flex-1">
                  <div className="h-2 overflow-hidden rounded-full bg-[var(--color-card-muted)]">
                    <div className="h-full rounded-full bg-emerald-500" style={{ width: "100%" }} />
                  </div>
                </div>
              ) : null}
              {job?.error_message ? (
                <p className="basis-full text-sm text-red-700">{job.error_message}</p>
              ) : null}
            </div>
          </section>
        ) : null}

        {error ? <Alert tone="error">{error}</Alert> : null}
      </div>
      {actionMode ? (
        <TrainingItemActionModal
          open={actionMode !== null}
          mode={actionMode}
          itemTitle={title}
          busy={isActionBusy}
          errorMessage={actionError}
          onConfirm={handleConfirmAction}
          onClose={closeActionModal}
          upgradeHref="/settings/billing#addons"
          retrainQuota={
            actionMode === "retrain"
              ? {
                  required: retrainPreview.data?.required_chars ?? 0,
                  remaining: retrainPreview.data?.remaining_chars ?? 0,
                  available: retrainPreview.data?.available_chars ?? 0,
                  wouldExceed: retrainPreview.data?.would_exceed ?? false,
                  loading: retrainPreview.isLoading || retrainPreview.isFetching,
                }
              : null
          }
          texts={{
            deleteTitle: t("kb.processingMonitor.deleteConfirmTitle"),
            deleteMessage: t("kb.processingMonitor.deleteConfirmMessage"),
            deleteAcknowledge: t("kb.processingMonitor.deleteConfirmAcknowledge"),
            deleteConfirm: t("kb.processingMonitor.deleteConfirmAction"),
            deleteCancel: t("kb.processingMonitor.deleteConfirmCancel"),
            retrainTitle: t("kb.processingMonitor.retrainConfirmTitle"),
            retrainMessage: t("kb.processingMonitor.retrainConfirmMessage"),
            retrainConfirm: t("kb.processingMonitor.retrainConfirmAction"),
            retrainCancel: t("kb.processingMonitor.retrainConfirmCancel"),
            retrainQuotaLoading: t("kb.processingMonitor.retrainQuotaLoading"),
            retrainQuotaCost: t("kb.processingMonitor.retrainQuotaCost"),
            retrainQuotaRemaining: t("kb.processingMonitor.retrainQuotaRemaining"),
            retrainQuotaAfter: t("kb.processingMonitor.retrainQuotaAfter"),
            retrainQuotaExceededTitle: t("kb.processingMonitor.retrainQuotaExceededTitle"),
            retrainQuotaExceededMessage: t("kb.processingMonitor.retrainQuotaExceededMessage"),
            retrainQuotaUpgrade: t("kb.processingMonitor.retrainQuotaUpgrade"),
          }}
        />
      ) : null}
    </div>
  );
}
