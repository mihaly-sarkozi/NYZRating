type KbTrainingProgressModalProps = {
  open: boolean;
  progress: number;
  statusDetail: string;
  t: (key: string) => string;
};

export default function KbTrainingProgressModal({ open, progress, statusDetail, t }: KbTrainingProgressModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[75] flex items-center justify-center bg-black/40 px-4 backdrop-blur-[1px]">
      <div className="w-full max-w-xs rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-6 text-center">
        <div className="relative mx-auto h-24 w-24">
          <div className="absolute inset-0 rounded-full border-4 border-[var(--color-border)]" />
          <div className="absolute inset-0 animate-spin rounded-full border-4 border-transparent border-t-[var(--color-primary)]" />
          <div className="absolute inset-0 flex items-center justify-center text-lg font-bold">{progress}%</div>
        </div>
        <div className="mt-4 text-sm font-medium">{t("kb.actionTrain")}</div>
        {statusDetail ? <div className="mt-1 text-xs text-[var(--color-muted)]">{statusDetail}</div> : null}
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-border)]">
          <div
            className="h-full bg-[var(--color-primary)] transition-all duration-150"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </div>
  );
}
