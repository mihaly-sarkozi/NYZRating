import type { IngestItem } from "../../../api/services/kb/types";
import { formatBytes, formatThousands } from "../components/list/kbListUtils";

export type ItemStorageMetrics = {
  file_bytes?: number;
  database_bytes?: number;
  total_bytes?: number;
  training_char_count?: number;
};

function readNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value);
  return null;
}

export function readItemStorageMetrics(metadata: Record<string, unknown> | null | undefined): ItemStorageMetrics | null {
  const raw = metadata?.storage_metrics;
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const metrics = raw as Record<string, unknown>;
    return {
      file_bytes: readNumber(metrics.file_bytes) ?? undefined,
      database_bytes: readNumber(metrics.database_bytes) ?? undefined,
      total_bytes: readNumber(metrics.total_bytes) ?? undefined,
      training_char_count: readNumber(metrics.training_char_count) ?? undefined,
    };
  }
  const charCount = readNumber(metadata?.char_count);
  return charCount != null ? { training_char_count: charCount } : null;
}

export function readItemStorageMetricsFromIngestItem(item: IngestItem | null | undefined): ItemStorageMetrics | null {
  if (!item) return null;
  return readItemStorageMetrics(item.metadata);
}

export function itemMetricValue(
  metrics: ItemStorageMetrics | null | undefined,
  key: keyof ItemStorageMetrics,
): number {
  const value = metrics?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

export function hasItemStorageMetrics(metrics: ItemStorageMetrics | null | undefined): boolean {
  if (!metrics) return false;
  return (
    itemMetricValue(metrics, "training_char_count") > 0 ||
    itemMetricValue(metrics, "total_bytes") > 0 ||
    itemMetricValue(metrics, "file_bytes") > 0 ||
    itemMetricValue(metrics, "database_bytes") > 0
  );
}

export function formatItemStorageMetricsLine(
  metrics: ItemStorageMetrics | null | undefined,
  t: (key: string) => string,
): string | null {
  if (!hasItemStorageMetrics(metrics)) return null;
  const parts = [
    `${t("kb.metricCharacters")}: ${formatThousands(itemMetricValue(metrics, "training_char_count"))}`,
    `${t("kb.metricSize")}: ${formatBytes(itemMetricValue(metrics, "total_bytes"))}`,
    `${t("kb.metricFile")}: ${formatBytes(itemMetricValue(metrics, "file_bytes"))}`,
    `${t("kb.metricDatabase")}: ${formatBytes(itemMetricValue(metrics, "database_bytes"))}`,
  ];
  return parts.join(" | ");
}

export function formatItemCharacterCount(metrics: ItemStorageMetrics | null | undefined): string {
  const value = itemMetricValue(metrics, "training_char_count");
  return value > 0 ? formatThousands(value) : "—";
}

export type ItemSizeMetricLine = {
  labelKey: "kb.metricSize" | "kb.metricFile" | "kb.metricDatabase";
  value: string;
};

export function buildItemSizeMetricLines(
  metrics: ItemStorageMetrics | null | undefined,
): ItemSizeMetricLine[] {
  if (!hasItemStorageMetrics(metrics)) return [];
  return [
    { labelKey: "kb.metricSize", value: formatBytes(itemMetricValue(metrics, "total_bytes")) },
    { labelKey: "kb.metricFile", value: formatBytes(itemMetricValue(metrics, "file_bytes")) },
    { labelKey: "kb.metricDatabase", value: formatBytes(itemMetricValue(metrics, "database_bytes")) },
  ];
}

export function formatFlowStepCountLabel(
  completedSteps: number,
  progressTotalSteps: number | null,
  failedSteps: number,
  t: (key: string) => string,
): string {
  const total = progressTotalSteps ?? Math.max(completedSteps + failedSteps, completedSteps, 1);
  return t("kb.processingMonitor.flowStepCount")
    .replace("{{completed}}", String(completedSteps))
    .replace("{{total}}", String(total));
}
