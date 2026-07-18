import { describe, expect, it } from "vitest";

import type { ProcessingEventSummary, ProcessingIssueSummary } from "../../../api/services/kb/kbProcessingApi";
import {
  buildPipelineTimeline,
  buildPipelineTimelineCompact,
  buildStepDurationProfile,
  computeWeightedProgressPercent,
  countOpenBlockingIssues,
  deriveFlowProgress,
  deriveFlowStatus,
  filterTimelineNoiseEvents,
  findFlowStartedAt,
  findLastCompletedRunItemId,
  isOpenBlockingIssue,
  mergeItemProcessingEvents,
  resolveFlowStatus,
  refineFlowStatusForProgress,
  roundDurationToMagnitude,
} from "./processingMonitorUtils";

function event(
  overrides: Partial<ProcessingEventSummary> & Pick<ProcessingEventSummary, "id" | "module" | "step" | "status">,
): ProcessingEventSummary {
  return {
    knowledge_base_id: "kb",
    stage: overrides.stage ?? overrides.step,
    event_type: overrides.event_type ?? `${overrides.step}_${overrides.status}`.toUpperCase(),
    input_summary_json: {},
    output_summary_json: {},
    metadata_json: {},
    created_at: overrides.created_at ?? "2026-06-14T10:00:00Z",
    training_item_id: overrides.training_item_id ?? "training_item_1",
    ...overrides,
  };
}

function warningIssue(): ProcessingIssueSummary {
  return {
    id: "issue-1",
    knowledge_base_id: "kb",
    module: "kb_discovery",
    stage: "LOCAL_KNOWLEDGE_ENRICHMENT",
    severity: "WARNING",
    issue_code: "NO_TOPICS_DETECTED",
    status: "OPEN",
    first_seen_at: "2026-06-14T10:00:00Z",
    last_seen_at: "2026-06-14T10:00:00Z",
    occurrence_count: 1,
    metadata_json: {},
  };
}

describe("deriveFlowStatus", () => {
  it("marks indexed flows completed even with open warnings", () => {
    expect(
      deriveFlowStatus(
        [
          event({
            id: "1",
            module: "kb_indexing",
            step: "PIPELINE",
            status: "completed",
            event_type: "INDEXING_COMPLETED",
          }),
        ],
        [warningIssue()],
      ),
    ).toBe("completed");
  });

  it("counts only blocking issues as open problems", () => {
    expect(isOpenBlockingIssue(warningIssue())).toBe(false);
    expect(countOpenBlockingIssues([warningIssue()])).toBe(0);

    const errorIssue: ProcessingIssueSummary = { ...warningIssue(), id: "issue-2", severity: "ERROR" };
    expect(countOpenBlockingIssues([warningIssue(), errorIssue])).toBe(1);
    expect(deriveFlowStatus([indexingCompletedEvent()], [errorIssue])).toBe("failed");
  });

  it("keeps mid-pipeline flows running after intermediate steps complete", () => {
    const events = [understandingExtractCompleted(), understandingNormalizeStarted()];
    expect(deriveFlowStatus(events, [])).toBe("running");
    expect(deriveFlowProgress(events, [])).not.toBeNull();
  });
});

describe("resolveFlowStatus", () => {
  it("falls back to ingest item status when processing events are not yet available", () => {
    expect(resolveFlowStatus([], [], { ingestItemStatus: "processing" })).toBe("running");
    expect(resolveFlowStatus([], [], { ingestItemStatus: "accepted" })).toBe("waiting");
    expect(resolveFlowStatus([], [], { ingestItemStatus: "pending" })).toBe("waiting");
  });

  it("refines running flows with zero completed steps to waiting", () => {
    expect(
      refineFlowStatusForProgress("running", { completedSteps: 0, hasActiveStep: false }),
    ).toBe("waiting");
    expect(
      refineFlowStatusForProgress("running", { completedSteps: 1, hasActiveStep: false }),
    ).toBe("running");
    expect(
      refineFlowStatusForProgress("running", { completedSteps: 0, hasActiveStep: true }),
    ).toBe("running");
  });

  it("prefers event-derived status over job fallback", () => {
    expect(
      resolveFlowStatus([indexingCompletedEvent()], [], { jobStatus: "extracting" }),
    ).toBe("completed");
  });

  it("uses understanding job status when events and ingest status are unknown", () => {
    expect(resolveFlowStatus([], [], { jobStatus: "chunking" })).toBe("running");
  });

  it("marks indexed flows completed even when intermediate events suggest running", () => {
    expect(
      resolveFlowStatus(
        [
          event({
            id: "idx",
            module: "kb_indexing",
            step: "PIPELINE",
            status: "completed",
            event_type: "INDEXING_COMPLETED",
          }),
          understandingExtractCompleted(),
        ],
        [],
      ),
    ).toBe("completed");
  });
});

describe("mergeItemProcessingEvents", () => {
  it("merges tenant and scoped events so indexing completion is visible", () => {
    const tenantOnly = [understandingExtractCompleted()];
    const scopedOnly = [indexingCompletedEvent()];
    const merged = mergeItemProcessingEvents(tenantOnly, scopedOnly);
    expect(resolveFlowStatus(merged, [])).toBe("completed");
  });
});

describe("filterTimelineNoiseEvents", () => {
  it("keeps discovery and embedding visible when verification floods the event list", () => {
    const discovery = event({
      id: "disc",
      module: "kb_discovery",
      step: "PIPELINE",
      status: "completed",
      event_type: "DISCOVERY_COMPLETED",
    });
    const embedding = event({
      id: "emb",
      module: "kb_embedding",
      step: "PIPELINE",
      status: "completed",
      event_type: "EMBEDDING_COMPLETED",
    });
    const noise = Array.from({ length: 250 }, (_, index) =>
      event({
        id: `pt-${index}`,
        module: "kb_indexing",
        step: "VERIFY_QDRANT",
        status: "completed",
        event_type: "QDRANT_POINT_VERIFIED",
      }),
    );
    const filtered = filterTimelineNoiseEvents([...noise, discovery, embedding, indexingCompletedEvent()]);
    const timeline = buildPipelineTimelineCompact(filtered);
    expect(timeline.some((row) => row.module === "kb_discovery")).toBe(true);
    expect(timeline.some((row) => row.module === "kb_embedding")).toBe(true);
  });
});

function indexingCompletedEvent(): ProcessingEventSummary {
  return event({
    id: "1",
    module: "kb_indexing",
    step: "PIPELINE",
    status: "completed",
    event_type: "INDEXING_COMPLETED",
  });
}

function understandingExtractCompleted(): ProcessingEventSummary {
  return event({
    id: "u1",
    module: "kb_understanding",
    stage: "EXTRACT",
    step: "EXTRACT_CONTENT",
    status: "completed",
    event_type: "EXTRACT_COMPLETED",
    duration_ms: 120,
  });
}

function understandingNormalizeStarted(): ProcessingEventSummary {
  return event({
    id: "u2",
    module: "kb_understanding",
    stage: "NORMALIZE",
    step: "NORMALIZE_PARTS",
    status: "started",
    event_type: "NORMALIZE_STARTED",
    created_at: "2026-06-14T10:01:00Z",
  });
}

describe("duration-weighted progress", () => {
  it("rounds durations to stable magnitude buckets", () => {
    expect(roundDurationToMagnitude(120)).toBe(100);
    expect(roundDurationToMagnitude(800)).toBe(1000);
    expect(roundDurationToMagnitude(4200)).toBe(5000);
    expect(roundDurationToMagnitude(18_000)).toBe(25_000);
  });

  it("finds the latest fully indexed reference run", () => {
    const reference = [
      event({
        id: "old-index",
        training_item_id: "item-old",
        module: "kb_indexing",
        step: "PIPELINE",
        status: "completed",
        created_at: "2026-06-14T09:00:00Z",
      }),
      event({
        id: "new-index",
        training_item_id: "item-new",
        module: "kb_indexing",
        step: "PIPELINE",
        status: "completed",
        created_at: "2026-06-14T11:00:00Z",
      }),
    ];
    expect(findLastCompletedRunItemId(reference)).toBe("item-new");
    expect(findLastCompletedRunItemId(reference, "item-new")).toBe("item-old");
  });

  it("allocates less progress to fast steps than slow ones", () => {
    const referenceRun = [
      event({
        id: "ref-index",
        training_item_id: "item-ref",
        module: "kb_indexing",
        step: "PIPELINE",
        status: "completed",
        created_at: "2026-06-14T08:00:00Z",
      }),
      event({
        id: "ref-extract",
        training_item_id: "item-ref",
        module: "kb_understanding",
        step: "EXTRACT_CONTENT",
        status: "completed",
        duration_ms: 150,
      }),
      event({
        id: "ref-enrich",
        training_item_id: "item-ref",
        module: "kb_discovery",
        step: "ENRICH_LOCAL",
        status: "completed",
        duration_ms: 25_000,
      }),
    ];

    const profile = buildStepDurationProfile(referenceRun);
    expect(profile.get("kb_understanding::EXTRACT_CONTENT")).toBe(100);
    expect(profile.get("kb_discovery::ENRICH_LOCAL")).toBe(25_000);
    expect(profile.get("kb_discovery::ENRICH_LOCAL")).toBeGreaterThan(
      profile.get("kb_understanding::EXTRACT_CONTENT") ?? 0,
    );

    const currentRun = [
      event({
        id: "cur-extract",
        training_item_id: "item-current",
        module: "kb_understanding",
        step: "EXTRACT_CONTENT",
        status: "completed",
        duration_ms: 180,
        created_at: "2026-06-14T12:00:00Z",
      }),
      event({
        id: "cur-normalize",
        training_item_id: "item-current",
        module: "kb_understanding",
        step: "NORMALIZE_PARTS",
        status: "started",
        created_at: "2026-06-14T12:00:00Z",
      }),
    ];

    const weightedProgress = deriveFlowProgress(currentRun, [], [], {
      referenceEvents: referenceRun,
      currentItemId: "item-current",
      nowMs: Date.parse("2026-06-14T12:00:01Z"),
    });

    const weightedProfile = buildStepDurationProfile(referenceRun, {
      excludeItemId: "item-current",
      overlayEvents: currentRun,
    });
    const timeline = buildPipelineTimeline(currentRun);
    const weights = timeline.map((row) => weightedProfile.get(row.key) ?? 1000);
    const rawPercent = computeWeightedProgressPercent(
      timeline,
      weights,
      currentRun,
      Date.parse("2026-06-14T12:00:01Z"),
    );
    const totalWeight = weights.reduce((sum, weight) => sum + weight, 0);

    expect(totalWeight).toBeLessThan(80_000);
    expect(rawPercent).toBeLessThan(15);
    expect(weightedProgress!.percent).toBe(rawPercent);
    expect(weightedProgress!.percent).toBeGreaterThan(0);
  });

  it("advances within the active step based on elapsed time", () => {
    const referenceRun = [
      event({
        id: "ref-index",
        training_item_id: "item-ref",
        module: "kb_indexing",
        step: "PIPELINE",
        status: "completed",
        created_at: "2026-06-14T08:00:00Z",
      }),
      event({
        id: "ref-extract",
        training_item_id: "item-ref",
        module: "kb_understanding",
        step: "EXTRACT_CONTENT",
        status: "completed",
        duration_ms: 50_000,
      }),
      event({
        id: "ref-generate",
        training_item_id: "item-ref",
        module: "kb_embedding",
        step: "GENERATE",
        status: "completed",
        duration_ms: 200_000,
      }),
    ];

    const profile = buildStepDurationProfile(referenceRun);
    const totalWeight = [...profile.values()].reduce((sum, weight) => sum + weight, 0);
    const extractWeight = profile.get("kb_understanding::EXTRACT_CONTENT") ?? 50_000;

    const flowStart = Date.parse("2026-06-14T12:00:00Z");
    const runningEvents = [
      event({
        id: "run-start",
        training_item_id: "item-live",
        module: "kb_understanding",
        step: "EXTRACT_CONTENT",
        status: "started",
        created_at: "2026-06-14T12:00:00Z",
      }),
    ];
    const timeline = buildPipelineTimeline(runningEvents);
    const weights = timeline.map((row) => profile.get(row.key) ?? 1000);

    const at30s = computeWeightedProgressPercent(
      timeline,
      weights,
      runningEvents,
      flowStart + 30_000,
    );
    const at60s = computeWeightedProgressPercent(
      timeline,
      weights,
      runningEvents,
      flowStart + 60_000,
    );

    expect(at30s).toBeGreaterThan(0);
    expect(at30s).toBeLessThan(Math.round(((30_000 / extractWeight) * extractWeight) / totalWeight * 100) + 3);
    expect(at60s).toBeGreaterThan(at30s);
    expect(at60s).toBeLessThanOrEqual(99);
  });

  it("uses flow start timestamp for time-based interpolation", () => {
    const events = [
      event({
        id: "e1",
        training_item_id: "item-1",
        module: "kb_understanding",
        step: "EXTRACT_CONTENT",
        status: "started",
        created_at: "2026-06-14T12:00:00Z",
      }),
    ];
    expect(findFlowStartedAt(events)).toBe(Date.parse("2026-06-14T12:00:00Z"));
  });
});
