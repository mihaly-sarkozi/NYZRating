import { useState } from "react";
import { Link } from "react-router-dom";

import { downloadTrainingItemRaw, parseTrainingQuotaError } from "../../../../api/services/kb/kbIngestApi";
import type { SettingsDateFormat, SettingsTimeFormat, SettingsTimezone } from "../../../../api/services/settingsService";
import { formatDateTime } from "../../../../utils/dateTimeFormatting";
import { getApiErrorMessage } from "../../../../utils/getApiErrorMessage";
import {
  useDeleteTrainingItemMutation,
  useRetrainTrainingItemMutation,
  useRetrainTrainingItemPreview,
} from "../../hooks/useKb";
import type { ProcessingFlowSummary } from "../../utils/processingMonitorUtils";
import { isFlowInProgress, translateProcessingMonitorKey } from "../../utils/processingMonitorUtils";
import {
  buildItemSizeMetricLines,
  formatFlowStepCountLabel,
  formatItemCharacterCount,
} from "../../utils/itemStorageMetrics";
import ProcessingStatusBadge from "./ProcessingStatusBadge";
import TrainingItemActionModal, { type TrainingItemActionMode } from "./TrainingItemActionModal";

const ROW_GRID =
  "grid grid-cols-1 gap-3 px-5 py-4 transition hover:bg-[var(--color-card-muted)]/50 md:grid-cols-[minmax(0,2fr)_minmax(0,0.95fr)_minmax(0,0.65fr)_minmax(0,1fr)_minmax(8.5rem,auto)] md:items-center md:gap-4";

type ProcessingMonitorFlowListRowProps = {
  kbUuid: string;
  flow: ProcessingFlowSummary;
  t: (key: string) => string;
  locale: string;
  timezone?: SettingsTimezone | string;
  dateFormat?: SettingsDateFormat;
  timeFormat?: SettingsTimeFormat;
};

function resolveDisplayTitle(flow: ProcessingFlowSummary, t: (key: string) => string): string {
  if (flow.hasExplicitTitle) return flow.title;
  if (flow.inputType === "text") {
    const preview = (flow.textPreview ?? "").trim();
    if (preview) return `“${preview}”`;
    return t("kb.processingMonitor.typedTextLabel");
  }
  return flow.title;
}

export default function ProcessingMonitorFlowListRow({
  kbUuid,
  flow,
  t,
  locale,
  timezone,
  dateFormat,
  timeFormat,
}: ProcessingMonitorFlowListRowProps) {
  const detailUrl = `/kb/monitor/${kbUuid}/flows/${encodeURIComponent(flow.itemId)}`;
  const stepLabel = formatFlowStepCountLabel(
    flow.completedSteps,
    flow.progressTotalSteps,
    flow.failedSteps,
    t,
  );
  const sizeLines = buildItemSizeMetricLines(flow.storageMetrics);
  const displayTitle = resolveDisplayTitle(flow, t);
  const isDeleted = flow.status === "deleted";
  const isRunning = isFlowInProgress(flow.status);
  const showRawAction = !isDeleted && (flow.inputType === "file" || flow.inputType === "text");
  const showActionButtons = !isDeleted;
  const actionsDisabledTooltip = isRunning ? t("kb.processingMonitor.flowDisabledWhileRunning") : null;

  const [rawError, setRawError] = useState<string | null>(null);
  const [rawLoading, setRawLoading] = useState(false);

  const [actionMode, setActionMode] = useState<TrainingItemActionMode | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const deleteMutation = useDeleteTrainingItemMutation();
  const retrainMutation = useRetrainTrainingItemMutation();
  const retrainPreview = useRetrainTrainingItemPreview(
    kbUuid,
    flow.itemId,
    actionMode === "retrain",
  );

  const isBusyAction =
    deleteMutation.isPending || retrainMutation.isPending;
  const actionsDisabled = isBusyAction || isRunning;

  const openActionModal =
    (mode: TrainingItemActionMode) =>
    (event: React.MouseEvent<HTMLButtonElement>) => {
      event.preventDefault();
      event.stopPropagation();
      if (actionsDisabled) return;
      setActionError(null);
      setActionMode(mode);
    };

  const closeActionModal = () => {
    if (isBusyAction) return;
    setActionMode(null);
    setActionError(null);
  };

  const handleConfirmAction = async () => {
    if (!actionMode) return;
    setActionError(null);
    try {
      if (actionMode === "delete") {
        await deleteMutation.mutateAsync({ kbUuid, itemId: flow.itemId });
      } else {
        await retrainMutation.mutateAsync({ kbUuid, itemId: flow.itemId });
      }
      setActionMode(null);
    } catch (error) {
      const quota = parseTrainingQuotaError(error);
      if (quota) {
        await retrainPreview.refetch();
        setActionError(quota.message ?? t("kb.processingMonitor.retrainQuotaExceededMessage"));
        return;
      }
      const errorKey =
        actionMode === "delete"
          ? "kb.processingMonitor.deleteError"
          : "kb.processingMonitor.retrainError";
      setActionError(getApiErrorMessage(error) ?? t(errorKey));
    }
  };

  const handleOpenRaw = async (event: React.MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();
    if (rawLoading) return;
    setRawError(null);
    setRawLoading(true);
    try {
      const { blob } = await downloadTrainingItemRaw(kbUuid, flow.itemId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
      console.error("Failed to download training item raw content", error);
      setRawError(t("kb.processingMonitor.downloadRawError"));
    } finally {
      setRawLoading(false);
    }
  };

  return (
    <div key={flow.itemId} className={ROW_GRID}>
      <Link to={detailUrl} className="contents">
        <div className="min-w-0">
          <p className="text-xs text-[var(--color-muted)]">
            {flow.lastEventAt
              ? formatDateTime(flow.lastEventAt, { locale, timezone, dateFormat, timeFormat })
              : "—"}
          </p>
          <p className="mt-0.5 truncate font-medium text-[var(--color-foreground)]">{displayTitle}</p>
          {rawError ? (
            <p className="mt-0.5 text-xs text-red-600">{rawError}</p>
          ) : null}
        </div>

        <div>
          <ProcessingStatusBadge
            status={flow.status}
            label={translateProcessingMonitorKey(t, flow.status, "flowStatus")}
          />
          <p className="mt-1 text-xs text-[var(--color-muted)]">{stepLabel}</p>
        </div>

        <div className="text-sm font-medium text-[var(--color-foreground)] md:text-right">
          {formatItemCharacterCount(flow.storageMetrics)}
        </div>

        <div className="text-xs leading-5 text-[var(--color-muted-foreground)] md:text-right">
          {sizeLines.length ? (
            sizeLines.map((line) => (
              <div key={line.labelKey}>
                {t(line.labelKey)}: {line.value}
              </div>
            ))
          ) : (
            "—"
          )}
        </div>
      </Link>

      <div className="flex items-center justify-end gap-1 text-[var(--color-primary)]">
        {isDeleted ? (
          <span className="rounded-full border border-[var(--color-border-muted)] bg-[var(--color-surface-muted)] px-2 py-0.5 text-xs font-medium text-[var(--color-muted)]">
            {t("kb.processingMonitor.deletedBadge")}
          </span>
        ) : null}
        {showRawAction ? (
          <button
            type="button"
            onClick={handleOpenRaw}
            disabled={rawLoading}
            className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[var(--color-muted-foreground)] transition hover:bg-[var(--color-card-muted)] hover:text-[var(--color-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-50"
            aria-label={t("kb.processingMonitor.openRawAria")}
            title={t("kb.processingMonitor.openRawTooltip")}
          >
            {rawLoading ? (
              <svg
                viewBox="0 0 24 24"
                className="h-4 w-4 animate-spin"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M21 12a9 9 0 1 1-6.219-8.56" />
              </svg>
            ) : (
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
            )}
          </button>
        ) : null}
        {showActionButtons ? (
        <button
          type="button"
          onClick={openActionModal("retrain")}
          disabled={actionsDisabled}
          className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[var(--color-muted-foreground)] transition hover:bg-[var(--color-card-muted)] hover:text-[var(--color-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-50"
          aria-label={t("kb.processingMonitor.retrainAria")}
          title={actionsDisabledTooltip ?? t("kb.processingMonitor.retrainTooltip")}
        >
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
        </button>
        ) : null}
        {showActionButtons ? (
        <button
          type="button"
          onClick={openActionModal("delete")}
          disabled={actionsDisabled}
          className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[var(--color-muted-foreground)] transition hover:bg-rose-500/10 hover:text-rose-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 disabled:cursor-not-allowed disabled:opacity-50"
          aria-label={t("kb.processingMonitor.deleteAria")}
          title={actionsDisabledTooltip ?? t("kb.processingMonitor.deleteTooltip")}
        >
          <svg
            viewBox="0 0 24 24"
            className={`h-4 w-4 ${deleteMutation.isPending ? "animate-pulse" : ""}`}
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
        </button>
        ) : null}
        <span aria-hidden="true">→</span>
      </div>
      {actionMode ? (
        <TrainingItemActionModal
          open={actionMode !== null}
          mode={actionMode}
          itemTitle={displayTitle}
          busy={isBusyAction}
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

export const PROCESSING_MONITOR_FLOW_LIST_HEAD =
  "hidden grid-cols-[minmax(0,2fr)_minmax(0,0.95fr)_minmax(0,0.65fr)_minmax(0,1fr)_minmax(8.5rem,auto)] gap-4 !bg-[#efefef] px-5 py-3 text-sm font-medium !text-[var(--color-foreground)] md:grid";
