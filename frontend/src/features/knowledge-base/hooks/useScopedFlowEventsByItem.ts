import { useQueries, type UseQueryOptions } from "@tanstack/react-query";
import { useMemo } from "react";

import { listProcessingEvents, type ProcessingEventSummary, type ProcessingEventsPage } from "../../../api/services/kb/kbProcessingApi";
import type { IngestRun } from "../../../api/services/kb/types";
import { queryKeys } from "../../../queryKeys";
import { SCOPED_MONITOR_EVENTS_LIMIT } from "../utils/processingMonitorPolling";
import { resolveFlowItemId } from "../utils/processingMonitorUtils";

export function collectTrainingItemIds(runs: IngestRun[] | undefined): string[] {
  const ids = new Set<string>();
  for (const run of runs ?? []) {
    for (const item of run.items ?? []) {
      if (item.id) ids.add(item.id);
    }
  }
  return [...ids];
}

export function collectMonitorFlowItemIds(
  runs: IngestRun[] | undefined,
  events: ProcessingEventSummary[] | undefined,
): string[] {
  const ids = new Set(collectTrainingItemIds(runs));
  for (const event of events ?? []) {
    const itemId = resolveFlowItemId(event);
    if (itemId) ids.add(itemId);
  }
  return [...ids];
}

type ScopedFlowPollOptions = Pick<
  UseQueryOptions<ProcessingEventsPage>,
  "refetchInterval" | "refetchIntervalInBackground" | "staleTime" | "refetchOnMount" | "refetchOnWindowFocus" | "refetchOnReconnect"
>;

export function useScopedFlowEventsByItem(
  kbUuid: string | undefined,
  itemIds: string[],
  pollOptions: ScopedFlowPollOptions = {},
) {
  const queries = useQueries({
    queries: itemIds.map((itemId) => ({
      queryKey: [
        ...queryKeys.kbProcessingMonitor(kbUuid ?? ""),
        "events",
        { training_item_id: itemId, timeline: true, limit: SCOPED_MONITOR_EVENTS_LIMIT },
      ],
      queryFn: () =>
        listProcessingEvents(kbUuid!, {
          training_item_id: itemId,
          timeline: true,
          limit: SCOPED_MONITOR_EVENTS_LIMIT,
          offset: 0,
        }),
      enabled: Boolean(kbUuid && itemId),
      staleTime: 0,
      refetchOnMount: "always" as const,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      ...pollOptions,
    })),
  });

  const querySnapshot = queries.map((query) => query.dataUpdatedAt).join("|");

  return useMemo(() => {
    const map = new Map<string, ProcessingEventSummary[]>();
    itemIds.forEach((itemId, index) => {
      const data = queries[index]?.data;
      if (data !== undefined) {
        map.set(itemId, data.items ?? []);
      }
    });
    return map;
  }, [itemIds, querySnapshot, queries]);
}
