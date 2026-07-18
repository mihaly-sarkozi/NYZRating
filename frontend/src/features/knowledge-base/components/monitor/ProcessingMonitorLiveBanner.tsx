import { useTranslation } from "../../../../i18n";
import { translateProcessingMonitorKey } from "../../utils/processingMonitorUtils";
import type { FlowProgressDetail, ProcessingFlowSummary } from "../../utils/processingMonitorUtils";

type ProcessingMonitorLiveBannerProps = {
  isLive: boolean;
  activeFlowCount?: number;
  activeFlow?: Pick<
    ProcessingFlowSummary,
    "activeModule" | "activeStage" | "activeStep" | "latestMessage"
  > | null;
  progress?: FlowProgressDetail | null;
};

export default function ProcessingMonitorLiveBanner({
  isLive,
  activeFlowCount = 0,
  activeFlow = null,
  progress = null,
}: ProcessingMonitorLiveBannerProps) {
  const { t } = useTranslation();

  if (!isLive) return null;

  const moduleLabel = activeFlow?.activeModule
    ? translateProcessingMonitorKey(t, activeFlow.activeModule, "module")
    : null;
  const stepLabel = activeFlow?.activeStep
    ? translateProcessingMonitorKey(t, activeFlow.activeStep, "stepOrStage")
    : null;
  const stageLabel = activeFlow?.activeStage
    ? translateProcessingMonitorKey(t, activeFlow.activeStage, "stage")
    : null;
  const progressParts = [moduleLabel, stageLabel ?? stepLabel].filter(Boolean);
  const progressText = progressParts.length
    ? t("kb.processingMonitor.activeProgress")
        .replace("{{module}}", progressParts[0] ?? "")
        .replace("{{step}}", progressParts[1] ?? progressParts[0] ?? "")
    : null;

  const percent = progress?.percent ?? null;

  return (
    <div
      className="mb-4 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-950"
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-wrap items-start gap-3">
        <span className="relative mt-1 flex h-2.5 w-2.5 shrink-0" aria-hidden="true">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-sky-500" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <p className="font-medium">{t("kb.processingMonitor.liveUpdating")}</p>
            {percent != null ? (
              <span className="rounded-full bg-sky-200/80 px-2 py-0.5 text-xs font-semibold text-sky-950">
                {t("kb.processingMonitor.percentComplete").replace("{{percent}}", String(percent))}
              </span>
            ) : null}
          </div>
          {progressText ? <p className="mt-0.5 text-sky-900">{progressText}</p> : null}
          {activeFlow?.latestMessage && !progressText ? (
            <p className="mt-0.5 text-sky-900">{activeFlow.latestMessage}</p>
          ) : null}
          {activeFlowCount > 1 ? (
            <p className="mt-0.5 text-xs text-sky-800">
              {t("kb.processingMonitor.activeFlowCount").replace("{{count}}", String(activeFlowCount))}
            </p>
          ) : null}
        </div>
      </div>
      {percent != null ? (
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-sky-200/70" aria-hidden="true">
          <div
            className="h-full rounded-full bg-sky-600 transition-[width] duration-1000 ease-linear"
            style={{ width: `${Math.max(percent, 2)}%` }}
          />
        </div>
      ) : null}
    </div>
  );
}
