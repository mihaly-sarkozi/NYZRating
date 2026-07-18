import Button from "../../../../components/ui/Button";
import type { KbItem } from "../../hooks/useKb";
import { formatBytes, formatThousands, isDeletedKb, metricValue } from "./kbListUtils";

type KBCardProps = {
  kb: KbItem;
  canManage: boolean;
  canDeleteKb: boolean;
  billingRestricted: boolean;
  actionLoading: boolean;
  t: (key: string) => string;
  onTrain: (kb: KbItem) => void;
  onTrainingLog: (kb: KbItem) => void;
  onSettings: (kb: KbItem) => void;
  onDelete: (kb: KbItem) => void;
};

export default function KBCard({
  kb,
  canManage,
  canDeleteKb,
  billingRestricted,
  actionLoading,
  t,
  onTrain,
  onTrainingLog,
  onSettings,
  onDelete,
}: KBCardProps) {
  const deleted = isDeletedKb(kb);
  const canTrain = kb.can_train === true;
  const showTrainActions = canManage && canTrain && !deleted;
  const showSettings = showTrainActions && !billingRestricted;
  const showDelete = canDeleteKb && !billingRestricted && !deleted;
  const actionButtonClass = "w-full md:flex-1 md:min-w-0";

  return (
    <div className={`grid gap-4 px-5 py-4 md:grid-cols-[0.75fr_2fr_1.25fr] md:items-center ${deleted ? "text-[var(--color-muted)]" : ""}`}>
      <div className="min-w-0">
        <p className={`truncate font-medium ${deleted ? "text-[var(--color-muted)]" : "text-[var(--color-foreground)]"}`}>{kb.name}</p>
        <span className={`mt-1 inline-block rounded-lg px-2 py-0.5 text-xs font-medium text-white ${deleted ? "bg-[var(--color-danger-text)]" : "bg-[var(--color-success-text)]"}`}>
          {deleted ? t("kb.statusDeleted") : t("kb.statusActive")}
        </span>
      </div>

      <div className="text-sm text-[var(--color-muted)]">
        <div className="rounded-lg bg-[var(--color-card-muted)] px-3 py-2 text-xs leading-5 text-[var(--color-muted-foreground)]">
          <span className={`font-medium ${deleted ? "text-[var(--color-muted)]" : "text-[var(--color-foreground)]"}`}>
            {t("kb.metricCharacters")}: {formatThousands(metricValue(kb, "training_char_count"))}
          </span>
          {(() => {
            const lifetime = metricValue(kb, "lifetime_training_char_count");
            const live = metricValue(kb, "training_char_count");
            if (lifetime > live) {
              return (
                <span
                  className="ml-2 inline-block rounded-md bg-[var(--color-surface-muted)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--color-muted-foreground)]"
                  title={t("kb.metricLifetimeCharactersTooltip")}
                >
                  Σ {t("kb.metricLifetimeChars")}: {formatThousands(lifetime)}
                </span>
              );
            }
            return null;
          })()}
          <span className="mx-2">|</span>
          {t("kb.metricSize")}: {formatBytes(metricValue(kb, "total_bytes"))}
          <span className="mx-2">|</span>
          {t("kb.metricFile")}: {formatBytes(metricValue(kb, "file_bytes"))}
          <span className="mx-2">|</span>
          {t("kb.metricDatabase")}: {formatBytes(metricValue(kb, "database_bytes"))}
        </div>
      </div>

      <div className="flex w-full flex-col gap-2 md:flex-row md:items-stretch">
        {deleted ? (
          <div className="w-full rounded-lg bg-[var(--color-card-muted)] px-3 py-2 text-center text-sm font-medium text-[var(--color-muted-foreground)]">
            {t("kb.deletedNoActions")}
          </div>
        ) : null}
        {showTrainActions ? (
          <Button
            type="button"
            variant="primary"
            onClick={() => onTrain(kb)}
            disabled={actionLoading || billingRestricted}
            size="sm"
            fullWidth
            className={actionButtonClass}
            title={t("kb.actionTrain")}
            aria-label={t("kb.actionTrain")}
          >
            {t("kb.actionTrain")}
          </Button>
        ) : null}
        {showTrainActions ? (
          <Button
            type="button"
            variant="secondary"
            onClick={() => onTrainingLog(kb)}
            disabled={actionLoading}
            size="sm"
            fullWidth
            className={actionButtonClass}
            title={t("kb.actionTrainingLog")}
            aria-label={t("kb.actionTrainingLog")}
          >
            {t("kb.actionLog")}
          </Button>
        ) : null}
        {showSettings ? (
          <Button
            type="button"
            variant="secondary"
            onClick={() => onSettings(kb)}
            disabled={actionLoading}
            size="sm"
            fullWidth
            className={actionButtonClass}
          >
            {t("kb.actionSettings")}
          </Button>
        ) : null}
        {showDelete ? (
          <Button
            type="button"
            variant="danger"
            onClick={() => onDelete(kb)}
            disabled={actionLoading}
            size="sm"
            fullWidth
            className={actionButtonClass}
          >
            {t("kb.actionDelete")}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
