import { describe, expect, it } from "vitest";

import {
  buildPipelineTimeline,
  buildPipelineTimelineCompact,
  buildStepDurationProfile,
  computeModuleWallTimes,
  computeWeightedProgressPercent,
  extractRawStepDurationsMs,
  findFlowStartedAt,
} from "./processingMonitorUtils";
import {
  buildRealCompletedRunEvents,
  REAL_COMPLETED_RUN_CHAR_COUNT,
  REAL_COMPLETED_RUN_ITEM_ID,
  REAL_COMPLETED_RUN_TIMESTAMPS,
} from "./processingMonitorScale.fixture";

function wallPercentAt(timestamp: string): number {
  const start = Date.parse(REAL_COMPLETED_RUN_TIMESTAMPS.start);
  const end = Date.parse(REAL_COMPLETED_RUN_TIMESTAMPS.indexing_done);
  const point = Date.parse(timestamp);
  return Math.round(((point - start) / (end - start)) * 100);
}

function cumulativePercent(
  profile: Map<string, number>,
  timeline: ReturnType<typeof buildPipelineTimelineCompact>,
  activePartialRatio = 0,
): number {
  const weights = timeline.map((row) => profile.get(row.key) ?? 100);
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  if (total <= 0) return 0;

  let earned = 0;
  let activeApplied = false;
  for (let index = 0; index < timeline.length; index += 1) {
    const row = timeline[index];
    if (row.status === "completed") {
      earned += weights[index];
      continue;
    }
    if (!activeApplied && activePartialRatio > 0) {
      earned += weights[index] * activePartialRatio;
      activeApplied = true;
    }
    break;
  }
  return Math.round((earned / total) * 100);
}

describe("real run progress scale", () => {
  const referenceEvents = buildRealCompletedRunEvents();

  it("matches module wall times from the completed run", () => {
    const raw = extractRawStepDurationsMs(referenceEvents);
    const walls = computeModuleWallTimes(referenceEvents, raw);
    expect(walls.get("kb_understanding")).toBeGreaterThan(50_000);
    expect(walls.get("kb_understanding")).toBeLessThan(56_000);
    expect(walls.get("kb_discovery")).toBeGreaterThan(1_500);
    expect(walls.get("kb_discovery")).toBeLessThan(3_500);
    expect(walls.get("kb_embedding")).toBeGreaterThan(200_000);
    expect(walls.get("kb_indexing")).toBeGreaterThan(2_000);
  });

  it("does not double-count embedding PIPELINE weight", () => {
    const profile = buildStepDurationProfile(referenceEvents);
    expect(profile.get("kb_embedding::GENERATE")).toBeGreaterThan(100_000);
    expect(profile.get("kb_embedding::PIPELINE")).toBeLessThanOrEqual(100);
  });

  it("tracks wall-clock milestones within tolerance", () => {
    const profile = buildStepDurationProfile(referenceEvents);
    const fullTimeline = buildPipelineTimelineCompact(referenceEvents);

    const milestones = [
      { at: REAL_COMPLETED_RUN_TIMESTAMPS.understanding_done, completedUntil: "kb_discovery::DETECT_LANGUAGE" },
      { at: REAL_COMPLETED_RUN_TIMESTAMPS.discovery_done, completedUntil: "kb_embedding::BUILD_INPUT" },
      { at: REAL_COMPLETED_RUN_TIMESTAMPS.embedding_mid, completedUntil: "kb_embedding::GENERATE", partial: 0.45 },
      { at: REAL_COMPLETED_RUN_TIMESTAMPS.embedding_done, completedUntil: "kb_indexing::ENSURE_COLLECTION" },
    ];

    for (const milestone of milestones) {
      const wall = wallPercentAt(milestone.at);
      const cutoff = fullTimeline.findIndex((row) => row.key === milestone.completedUntil);
      const timeline = fullTimeline.map((row, index) => ({
        ...row,
        status: index < cutoff ? "completed" : index === cutoff ? "started" : "pending",
        isPending: index > cutoff,
      }));
      const weighted = cumulativePercent(profile, timeline, milestone.partial ?? 0.04);
      const equalSteps = Math.round((cutoff / fullTimeline.length) * 100);

      expect(Math.abs(weighted - wall)).toBeLessThanOrEqual(20);
      if (milestone.completedUntil !== "kb_discovery::DETECT_LANGUAGE") {
        expect(Math.abs(equalSteps - wall)).toBeGreaterThan(8);
      }
    }
  });

  it("debug cumulative weights", () => {
    const profile = buildStepDurationProfile(referenceEvents);
    const timeline = buildPipelineTimelineCompact(referenceEvents);
    const total = timeline.reduce((sum, row) => sum + (profile.get(row.key) ?? 0), 0);
    const afterDiscovery = referenceEvents.filter(
      (event) => event.module !== "kb_embedding" && event.module !== "kb_indexing",
    );
    const compact = buildPipelineTimelineCompact(afterDiscovery);
    const completedWeight = compact
      .filter((row) => row.status === "completed")
      .reduce((sum, row) => sum + (profile.get(row.key) ?? 0), 0);
    expect(total).toBeGreaterThan(250_000);
    expect(completedWeight).toBeLessThan(60_000);
    expect(Math.round((completedWeight / total) * 100)).toBeLessThan(30);
    expect(profile.get("kb_embedding::PIPELINE")).toBeLessThanOrEqual(100);
  });

  it("keeps discovery completion below 30% (embedding dominates)", () => {
    const profile = buildStepDurationProfile(referenceEvents);
    const timeline = buildPipelineTimeline(referenceEvents);
    const discoveryDoneIndex = timeline.findIndex((row) => row.key === "kb_embedding::BUILD_INPUT");
    const partialTimeline = timeline.map((row, index) => ({
      ...row,
      status:
        index < discoveryDoneIndex ? "completed" : index === discoveryDoneIndex ? "started" : "pending",
      isPending: index > discoveryDoneIndex,
    }));
    const weights = partialTimeline.map((row) => profile.get(row.key) ?? 1000);
    const flowStart = findFlowStartedAt(referenceEvents) ?? Date.parse(REAL_COMPLETED_RUN_TIMESTAMPS.start);
    const elapsedMs = Date.parse(REAL_COMPLETED_RUN_TIMESTAMPS.discovery_done) - flowStart;
    const percent = computeWeightedProgressPercent(
      partialTimeline,
      weights,
      referenceEvents,
      flowStart + elapsedMs,
    );
    expect(percent).toBeGreaterThan(12);
    expect(percent).toBeLessThan(30);
  });

  it("ticks smoothly during embedding instead of stalling at ~4%", () => {
    const profile = buildStepDurationProfile(referenceEvents);
    const fullTimeline = buildPipelineTimelineCompact(referenceEvents);
    const weights = fullTimeline.map((row) => profile.get(row.key) ?? 1000);
    const flowStart = Date.parse(REAL_COMPLETED_RUN_TIMESTAMPS.start);

    const embeddingStartIndex = fullTimeline.findIndex((row) => row.key === "kb_embedding::GENERATE");
    const midEmbeddingMs = Date.parse(REAL_COMPLETED_RUN_TIMESTAMPS.embedding_mid) - flowStart;

    const midTimeline = fullTimeline.map((row, index) => ({
      ...row,
      status:
        index < embeddingStartIndex
          ? "completed"
          : index === embeddingStartIndex
            ? "started"
            : "pending",
      isPending: index > embeddingStartIndex,
    }));

    const midEvents = referenceEvents.filter(
      (event) =>
        event.created_at <= REAL_COMPLETED_RUN_TIMESTAMPS.embedding_mid ||
        (event.module === "kb_embedding" && event.step === "GENERATE" && event.status === "started"),
    );

    const percent = computeWeightedProgressPercent(
      midTimeline,
      weights,
      midEvents.length ? midEvents : referenceEvents,
      flowStart + midEmbeddingMs,
    );

    expect(percent).toBeGreaterThan(35);
    expect(percent).toBeLessThan(65);
  });

  it("scales expected total duration by target char count", () => {
    const referenceEvents = buildRealCompletedRunEvents();
    const refProfile = buildStepDurationProfile(referenceEvents);
    const refTotal = [...refProfile.values()].reduce((sum, weight) => sum + weight, 0);
    const charIndex = new Map([[REAL_COMPLETED_RUN_ITEM_ID, REAL_COMPLETED_RUN_CHAR_COUNT]]);

    const doubledProfile = buildStepDurationProfile(referenceEvents, {
      excludeItemId: "other-item",
      targetCharCount: REAL_COMPLETED_RUN_CHAR_COUNT * 2,
      charCountByItemId: charIndex,
    });
    const doubledTotal = [...doubledProfile.values()].reduce((sum, weight) => sum + weight, 0);

    expect(doubledTotal).toBeGreaterThan(refTotal * 1.9);
    expect(doubledTotal).toBeLessThan(refTotal * 2.1);
  });

  it("stays well below 99% during the first seconds of extract", () => {
    const referenceEvents = buildRealCompletedRunEvents();
    const charIndex = new Map([[REAL_COMPLETED_RUN_ITEM_ID, REAL_COMPLETED_RUN_CHAR_COUNT]]);
    const profile = buildStepDurationProfile(referenceEvents, {
      excludeItemId: "new-item",
      targetCharCount: REAL_COMPLETED_RUN_CHAR_COUNT,
      charCountByItemId: charIndex,
    });
    const weights = buildPipelineTimelineCompact(referenceEvents).map(
      (row) => profile.get(row.key) ?? 1000,
    );
    const flowStart = Date.parse(REAL_COMPLETED_RUN_TIMESTAMPS.start);
    const runningEvents = referenceEvents
      .filter((event) => event.training_item_id === REAL_COMPLETED_RUN_ITEM_ID)
      .slice(0, 1)
      .map((event) => ({
        ...event,
        training_item_id: "new-item",
        status: "started" as const,
        created_at: REAL_COMPLETED_RUN_TIMESTAMPS.start,
      }));
    const timeline = buildPipelineTimelineCompact(runningEvents).map((row, index) => ({
      ...row,
      status: index === 0 ? "started" : "pending",
      isPending: index > 0,
    }));

    const percentAt5s = computeWeightedProgressPercent(
      timeline,
      weights,
      runningEvents,
      flowStart + 5_000,
    );

    expect(percentAt5s).toBeGreaterThan(0);
    expect(percentAt5s).toBeLessThan(5);
  });
});
