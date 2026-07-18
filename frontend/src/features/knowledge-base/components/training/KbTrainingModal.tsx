import type { DragEvent, RefObject } from "react";

import Button from "../../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../../components/ui/Modal";
import type { TrainingQuotaErrorDetail } from "../../../../api/services/kb/kbIngestApi";
import { estimateCharsFromFile, TRAINING_FILE_ACCEPT } from "../../utils/kbTrainingFiles";

type KbTrainingModalProps = {
  open: boolean;
  kbName: string;
  textValue: string;
  selectedFiles: File[];
  dragOver: boolean;
  loading: boolean;
  canSubmit: boolean;
  fileInputRef: RefObject<HTMLInputElement | null>;
  quotaError?: TrainingQuotaErrorDetail | null;
  onClearQuotaError?: () => void;
  remainingTrainingChars?: number | null;
  t: (key: string) => string;
  onClose: () => void;
  onSubmit: () => void;
  onTextChange: (value: string) => void;
  onDragOver: (event: DragEvent<HTMLDivElement>) => void;
  onDragLeave: (event: DragEvent<HTMLDivElement>) => void;
  onDrop: (event: DragEvent<HTMLDivElement>) => void;
  onSelectFiles: (files: FileList | null) => void;
  onRemoveFile: (index: number) => void;
};

export default function KbTrainingModal({
  open,
  kbName,
  textValue,
  selectedFiles,
  dragOver,
  loading,
  canSubmit,
  fileInputRef,
  quotaError = null,
  onClearQuotaError,
  remainingTrainingChars = null,
  t,
  onClose,
  onSubmit,
  onTextChange,
  onDragOver,
  onDragLeave,
  onDrop,
  onSelectFiles,
  onRemoveFile,
}: KbTrainingModalProps) {
  const hasText = textValue.trim().length > 0;
  const hasFiles = selectedFiles.length > 0;
  const showTextInput = !hasFiles;
  const showFileSelect = !hasText;
  const showQuotaError = quotaError != null;
  const quotaTitle = quotaError?.message ?? t("kb.trainingQuotaExceededTitle");
  const numberFmt = new Intl.NumberFormat();
  const fmt = (value: number | null | undefined): string => numberFmt.format(Math.max(0, Number(value ?? 0)));
  const fmtChars = (value: number | null | undefined): string => `${fmt(value)} ${t("kb.trainingCharsUnit")}`;
  const planName = (quotaError?.plan_name ?? quotaError?.plan_code ?? "—").toString();
  const planLimit = Math.max(0, Number(quotaError?.included_chars ?? quotaError?.available_chars ?? 0));
  const trainedChars = Math.max(0, Number(quotaError?.trained_chars ?? 0));
  const requiredChars = Math.max(0, Number(quotaError?.required_chars ?? 0));
  const remainingChars = Math.max(0, Number(quotaError?.remaining_chars ?? 0));
  const overflowChars = Math.max(0, requiredChars - remainingChars);
  const isHighestTier = quotaError?.is_highest_tier === true;
  const isFreePlan = (quotaError?.plan_code ?? "").toLowerCase() === "free";
  const nextPlanName = (quotaError?.next_plan_name ?? quotaError?.next_plan_code ?? "").toString();
  const nextPlanChars = Math.max(0, Number(quotaError?.next_plan_included_chars ?? 0));
  let upgradeAdvice = "";
  if (showQuotaError) {
    if (isHighestTier) {
      upgradeAdvice = t("kb.trainingQuotaAdviceAddon");
    } else if (isFreePlan) {
      upgradeAdvice = t("kb.trainingQuotaAdviceFree")
        .replace("{{plan}}", nextPlanName)
        .replace("{{chars}}", fmt(nextPlanChars));
    } else {
      upgradeAdvice = t("kb.trainingQuotaAdvicePaid")
        .replace("{{plan}}", nextPlanName)
        .replace("{{chars}}", fmt(nextPlanChars));
    }
  }

  const safeRemaining =
    typeof remainingTrainingChars === "number" && remainingTrainingChars >= 0 ? remainingTrainingChars : null;
  const textCharCount = textValue.length;
  const fileCharCounts = selectedFiles.map((file) => estimateCharsFromFile(file));
  const fileCharsTotal = fileCharCounts.reduce((sum, count) => sum + count, 0);
  const pendingChars = hasFiles ? fileCharsTotal : textCharCount;
  const charsOverflow = safeRemaining !== null && pendingChars > safeRemaining;

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={TRAINING_FILE_ACCEPT}
        className="hidden"
        onChange={(event) => {
          onSelectFiles(event.target.files);
          if (fileInputRef.current) fileInputRef.current.value = "";
        }}
      />
      <Modal open={open} panelClassName="max-w-2xl">
        <ModalHeader
          eyebrow={kbName}
          title={t("kb.trainModalTitle")}
          description={t("kb.trainModalDescription")}
        />

        {showQuotaError ? (
          <div
            role="alert"
            className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900"
          >
            <p className="font-semibold">{quotaTitle}</p>
            <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1 text-red-900 sm:grid-cols-2">
              <div className="flex justify-between gap-2 sm:block">
                <dt className="text-red-800">{t("kb.trainingQuotaCurrentPlan")}</dt>
                <dd className="font-medium">{planName}</dd>
              </div>
              <div className="flex justify-between gap-2 sm:block">
                <dt className="text-red-800">{t("kb.trainingQuotaPlanLimit")}</dt>
                <dd className="font-medium">{fmt(planLimit)}</dd>
              </div>
              <div className="flex justify-between gap-2 sm:block">
                <dt className="text-red-800">{t("kb.trainingQuotaUsed")}</dt>
                <dd className="font-medium">{fmt(trainedChars)}</dd>
              </div>
              <div className="flex justify-between gap-2 sm:block">
                <dt className="text-red-800">{t("kb.trainingQuotaRequested")}</dt>
                <dd className="font-medium">{fmt(requiredChars)}</dd>
              </div>
              <div className="flex justify-between gap-2 sm:col-span-2 sm:block">
                <dt className="text-red-800">{t("kb.trainingQuotaOverflow")}</dt>
                <dd className="font-semibold text-red-700">{fmt(overflowChars)}</dd>
              </div>
            </dl>
            {upgradeAdvice ? <p className="mt-3 text-red-800">{upgradeAdvice}</p> : null}
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={() => {
                  window.location.href = "/admin/pricing";
                }}
              >
                {t("kb.trainingQuotaUpgrade")}
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => onClearQuotaError?.()}
              >
                {t("kb.trainingQuotaModalBack")}
              </Button>
            </div>
          </div>
        ) : null}

        {showTextInput ? (
          <>
            {safeRemaining !== null ? (
              <p className="mb-2 text-xs text-[var(--color-muted)]">
                <span>{t("kb.trainingCharsAvailableLabel")}</span>{" "}
                <span className="font-semibold text-[var(--color-foreground)]">{fmtChars(safeRemaining)}</span>
              </p>
            ) : null}
            <div
              className={`rounded-xl border-2 border-dashed transition-colors ${
                dragOver ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5" : "border-[var(--color-border)]"
              }`}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
            >
              <textarea
                value={textValue}
                onChange={(event) => onTextChange(event.target.value)}
                disabled={loading}
                className="chat-question-input min-h-[180px] w-full resize-y rounded-xl border-0 bg-transparent p-4 focus:outline-none"
                placeholder={t("kb.trainContentPlaceholder")}
              />
            </div>
            {hasText ? (
              <p className="mt-2 text-xs text-[var(--color-muted)]">
                <span>{t("kb.trainingCharsPendingText")}</span>{" "}
                <span className={`font-semibold ${charsOverflow ? "text-red-700" : "text-[var(--color-foreground)]"}`}>
                  {fmtChars(textCharCount)}
                </span>
              </p>
            ) : null}
            {charsOverflow && hasText ? (
              <p className="mt-1 text-xs font-medium text-red-700">{t("kb.trainingCharsOverflowHint")}</p>
            ) : null}
          </>
        ) : null}

        {hasFiles ? (
          <div className="mt-3">
            {safeRemaining !== null ? (
              <p className="mb-2 text-xs text-[var(--color-muted)]">
                <span>{t("kb.trainingCharsAvailableLabel")}</span>{" "}
                <span className="font-semibold text-[var(--color-foreground)]">{fmtChars(safeRemaining)}</span>
              </p>
            ) : null}
            <div
              className={`overflow-hidden rounded-lg border text-sm ${
                charsOverflow ? "border-red-200" : "border-[var(--color-border)]"
              }`}
            >
              <ul className="divide-y divide-[var(--color-border)]">
                {selectedFiles.map((file, index) => (
                  <li
                    key={`${file.name}-${file.size}-${file.lastModified}`}
                    className="flex items-center justify-between gap-3 bg-[var(--color-card-muted)] px-3 py-2"
                  >
                    <span className="min-w-0 flex-1 truncate text-[var(--color-foreground)]">{file.name}</span>
                    <span className="shrink-0 tabular-nums text-[var(--color-muted)]">{fmtChars(fileCharCounts[index] ?? 0)}</span>
                    <button
                      type="button"
                      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[var(--color-border)] text-[var(--color-muted)] transition hover:border-red-300 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-45"
                      disabled={loading}
                      onClick={() => onRemoveFile(index)}
                      aria-label={t("kb.trainRemoveFile")}
                      title={t("kb.trainRemoveFile")}
                    >
                      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                          stroke="currentColor"
                          strokeWidth="1.8"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </button>
                  </li>
                ))}
                {selectedFiles.length > 1 ? (
                  <li
                    className={`flex items-center justify-between gap-3 px-3 py-2 font-medium ${
                      charsOverflow ? "bg-red-50 text-red-900" : "bg-[var(--color-card-muted)] text-[var(--color-foreground)]"
                    }`}
                  >
                    <span>{t("kb.trainingCharsPendingFile")}</span>
                    <span className={`shrink-0 tabular-nums ${charsOverflow ? "text-red-700" : ""}`}>{fmtChars(fileCharsTotal)}</span>
                  </li>
                ) : null}
              </ul>
            </div>
            {charsOverflow ? (
              <p className="mt-1 text-xs font-medium text-red-700">{t("kb.trainingCharsOverflowHint")}</p>
            ) : null}
          </div>
        ) : null}

        {showFileSelect ? (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <Button type="button" variant="secondary" size="sm" disabled={loading} onClick={() => fileInputRef.current?.click()}>
              {t("kb.trainSelectFiles")}
            </Button>
            {hasFiles ? (
              <span className="text-xs text-[var(--color-muted)]">
                {t("kb.trainFilesSelected").replace("{{count}}", String(selectedFiles.length))}
              </span>
            ) : null}
          </div>
        ) : null}

        <ModalFooter>
          <Button type="button" variant="secondary" disabled={loading} onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button type="button" variant="primary" disabled={!canSubmit} onClick={onSubmit}>
            {loading ? t("common.loading") : t("kb.actionTrain")}
          </Button>
        </ModalFooter>
      </Modal>
    </>
  );
}
