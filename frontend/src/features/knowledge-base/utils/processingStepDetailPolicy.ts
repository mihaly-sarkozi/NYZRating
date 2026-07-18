import { catalogKey } from "./processingPipelineCatalog";

/** Lépések, amelyekhez külön részletező oldal tartozik a monitor flow nézetben. */
const PROCESSING_STEP_DETAIL_ENABLED = new Set<string>([
  catalogKey("kb_understanding", "BUILD_CHUNKS"),
  catalogKey("kb_discovery", "DETECT_LANGUAGE"),
  catalogKey("kb_discovery", "EXTRACT_ENTITIES"),
  catalogKey("kb_discovery", "ENRICH_LOCAL"),
  catalogKey("kb_discovery", "EXTRACT_TEMPORAL"),
  catalogKey("kb_discovery", "EXTRACT_SPATIAL"),
]);

export function isProcessingStepDetailEnabled(module: string, step: string): boolean {
  return PROCESSING_STEP_DETAIL_ENABLED.has(catalogKey(module, step));
}
