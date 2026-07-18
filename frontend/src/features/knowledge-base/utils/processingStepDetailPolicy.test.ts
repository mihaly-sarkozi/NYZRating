import { describe, expect, it } from "vitest";

import { isProcessingStepDetailEnabled } from "./processingStepDetailPolicy";

describe("isProcessingStepDetailEnabled", () => {
  it("enables selected understanding and discovery steps only", () => {
    expect(isProcessingStepDetailEnabled("kb_understanding", "BUILD_CHUNKS")).toBe(true);
    expect(isProcessingStepDetailEnabled("kb_discovery", "DETECT_LANGUAGE")).toBe(true);
    expect(isProcessingStepDetailEnabled("kb_discovery", "EXTRACT_ENTITIES")).toBe(true);
    expect(isProcessingStepDetailEnabled("kb_discovery", "ENRICH_LOCAL")).toBe(true);
    expect(isProcessingStepDetailEnabled("kb_discovery", "EXTRACT_TEMPORAL")).toBe(true);
    expect(isProcessingStepDetailEnabled("kb_discovery", "EXTRACT_SPATIAL")).toBe(true);
  });

  it("disables other pipeline steps", () => {
    expect(isProcessingStepDetailEnabled("kb_understanding", "EXTRACT_CONTENT")).toBe(false);
    expect(isProcessingStepDetailEnabled("kb_understanding", "NORMALIZE_PARTS")).toBe(false);
    expect(isProcessingStepDetailEnabled("kb_understanding", "VALIDATE_RESULT")).toBe(false);
    expect(isProcessingStepDetailEnabled("kb_discovery", "EXTRACT_PROCESS")).toBe(false);
    expect(isProcessingStepDetailEnabled("kb_discovery", "BUILD_RELATIONSHIPS")).toBe(false);
    expect(isProcessingStepDetailEnabled("kb_discovery", "SCORE_KNOWLEDGE")).toBe(false);
    expect(isProcessingStepDetailEnabled("kb_discovery", "VALIDATE_DISCOVERY")).toBe(false);
    expect(isProcessingStepDetailEnabled("kb_discovery", "PIPELINE")).toBe(false);
    expect(isProcessingStepDetailEnabled("kb_embedding", "GENERATE")).toBe(false);
    expect(isProcessingStepDetailEnabled("kb_indexing", "VERIFY_QDRANT")).toBe(false);
  });
});
