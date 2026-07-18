import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Modal, { ModalFooter, ModalHeader } from "../../../../components/ui/Modal";
import Button from "../../../../components/ui/Button";

export type TrainingItemActionMode = "delete" | "retrain";

export type RetrainQuotaInfo = {
  required: number;
  remaining: number;
  available: number;
  wouldExceed: boolean;
  loading: boolean;
};

type Props = {
  open: boolean;
  mode: TrainingItemActionMode;
  itemTitle: string | null;
  busy: boolean;
  errorMessage: string | null;
  onConfirm: () => Promise<void> | void;
  onClose: () => void;
  retrainQuota?: RetrainQuotaInfo | null;
  upgradeHref?: string;
  texts: {
    deleteTitle: string;
    deleteMessage: string;
    deleteAcknowledge: string;
    deleteConfirm: string;
    deleteCancel: string;
    retrainTitle: string;
    retrainMessage: string;
    retrainConfirm: string;
    retrainCancel: string;
    retrainQuotaLoading: string;
    retrainQuotaCost: string;
    retrainQuotaRemaining: string;
    retrainQuotaAfter: string;
    retrainQuotaExceededTitle: string;
    retrainQuotaExceededMessage: string;
    retrainQuotaUpgrade: string;
  };
};

function formatCharCount(value: number): string {
  if (!Number.isFinite(value)) return "0";
  return Math.max(0, Math.round(value)).toLocaleString();
}

function applyTokens(template: string, tokens: Record<string, string>): string {
  let out = template;
  for (const [key, val] of Object.entries(tokens)) {
    out = out.replaceAll(`{${key}}`, val);
  }
  return out;
}

export default function TrainingItemActionModal({
  open,
  mode,
  itemTitle,
  busy,
  errorMessage,
  onConfirm,
  onClose,
  retrainQuota,
  upgradeHref,
  texts,
}: Props) {
  const [acknowledged, setAcknowledged] = useState(false);

  useEffect(() => {
    if (!open) {
      setAcknowledged(false);
    }
  }, [open, mode]);

  const isDelete = mode === "delete";
  const title = isDelete ? texts.deleteTitle : texts.retrainTitle;
  const message = isDelete ? texts.deleteMessage : texts.retrainMessage;
  const confirmLabel = isDelete ? texts.deleteConfirm : texts.retrainConfirm;
  const cancelLabel = isDelete ? texts.deleteCancel : texts.retrainCancel;

  const quota = !isDelete ? retrainQuota ?? null : null;
  const quotaBlocked = !!quota && quota.wouldExceed && !quota.loading;
  const quotaLoading = !!quota?.loading;
  const confirmDisabled =
    busy || (isDelete && !acknowledged) || quotaBlocked || quotaLoading;

  const remainingAfter = quota
    ? Math.max(0, (quota.remaining || 0) - (quota.required || 0))
    : 0;

  return (
    <Modal
      open={open}
      onClose={busy ? undefined : onClose}
      closeOnOverlay={!busy}
      panelClassName="w-full max-w-md sm:max-w-lg"
    >
      <ModalHeader title={title} description={<span className="whitespace-pre-line">{message}</span>} />
      {itemTitle ? (
        <p className="mb-4 break-words whitespace-pre-line rounded-md border border-[var(--color-border-muted)] bg-[var(--color-surface-muted)] px-3 py-2 text-sm text-[var(--color-foreground)]">
          {itemTitle}
        </p>
      ) : null}
      {!isDelete && quota ? (
        <div
          className={
            "mb-3 rounded-md border px-3 py-2 text-sm " +
            (quotaBlocked
              ? "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-200"
              : "border-[var(--color-border-muted)] bg-[var(--color-surface-muted)] text-[var(--color-muted)]")
          }
        >
          {quotaLoading ? (
            <p className="leading-relaxed">{texts.retrainQuotaLoading}</p>
          ) : quotaBlocked ? (
            <div className="space-y-1">
              <p className="font-semibold leading-tight">
                {texts.retrainQuotaExceededTitle}
              </p>
              <p className="leading-relaxed">
                {applyTokens(texts.retrainQuotaExceededMessage, {
                  required: formatCharCount(quota.required),
                  remaining: formatCharCount(quota.remaining),
                  available: formatCharCount(quota.available),
                })}
              </p>
            </div>
          ) : (
            <ul className="space-y-1 leading-relaxed">
              <li>
                {applyTokens(texts.retrainQuotaCost, {
                  required: formatCharCount(quota.required),
                })}
              </li>
              <li>
                {applyTokens(texts.retrainQuotaRemaining, {
                  remaining: formatCharCount(quota.remaining),
                  available: formatCharCount(quota.available),
                })}
              </li>
              <li>
                {applyTokens(texts.retrainQuotaAfter, {
                  after: formatCharCount(remainingAfter),
                })}
              </li>
            </ul>
          )}
        </div>
      ) : null}
      {isDelete ? (
        <div className="mb-2 flex items-center text-sm text-[var(--color-muted)]">
          <input
            id="training-item-action-acknowledge"
            type="checkbox"
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.target.checked)}
            disabled={busy}
            className="kb-perm-checkbox focus:ring-0 focus:outline-none focus:shadow-none [&:focus]:outline-none [&:focus]:ring-0 [&:focus]:shadow-none"
          />
          <label
            htmlFor="training-item-action-acknowledge"
            className="!mb-0 ml-2 !block translate-y-px cursor-pointer !font-medium leading-4 !text-[var(--color-muted)]"
          >
            {texts.deleteAcknowledge}
          </label>
        </div>
      ) : null}
      {errorMessage ? (
        <p className="mt-2 rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-600 dark:text-rose-300">
          {errorMessage}
        </p>
      ) : null}
      <ModalFooter>
        <Button variant="secondary" onClick={onClose} disabled={busy}>
          {cancelLabel}
        </Button>
        {!isDelete && quotaBlocked && upgradeHref ? (
          <Link
            to={upgradeHref}
            className="inline-flex items-center justify-center rounded-md bg-amber-500 px-3 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-amber-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
            onClick={onClose}
          >
            {texts.retrainQuotaUpgrade}
          </Link>
        ) : null}
        <Button
          variant={isDelete ? "danger" : "primary"}
          onClick={() => {
            void onConfirm();
          }}
          disabled={confirmDisabled}
        >
          {confirmLabel}
        </Button>
      </ModalFooter>
    </Modal>
  );
}
