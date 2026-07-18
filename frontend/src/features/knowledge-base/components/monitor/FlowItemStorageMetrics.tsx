import type { ItemStorageMetrics } from "../../utils/itemStorageMetrics";
import { formatItemStorageMetricsLine, hasItemStorageMetrics } from "../../utils/itemStorageMetrics";

type FlowItemStorageMetricsProps = {
  metrics: ItemStorageMetrics | null | undefined;
  t: (key: string) => string;
  className?: string;
};

export default function FlowItemStorageMetrics({ metrics, t, className = "" }: FlowItemStorageMetricsProps) {
  const line = formatItemStorageMetricsLine(metrics, t);
  if (!line || !hasItemStorageMetrics(metrics)) return null;

  return (
    <p className={`text-xs leading-5 text-[var(--color-muted-foreground)] ${className}`.trim()}>
      {line}
    </p>
  );
}
