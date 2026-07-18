import api from "../../axiosClient";
import {
  estimateFileTraining,
  getTrainingBatch,
  submitFileTraining,
  submitTextTraining,
  trainingFileResponseToIngestRun,
  trainingTextResponseToIngestRun,
} from "./kbTrainingApi";
import type { FileIngestEstimate, IngestRun, IngestRunListResponse, TrainingTextResponse } from "./types";

/** @deprecated Használd a `submitTextTraining` függvényt a `kbTrainingApi`-ból. */
export async function createTextIngestRun(
  kbUuid: string,
  body: { content: string; title?: string | null }
): Promise<IngestRun> {
  const res = await api.post(`/kb/${kbUuid}/training/text`, body);
  return trainingTextResponseToIngestRun(res.data as TrainingTextResponse, kbUuid);
}

export { estimateFileTraining, getTrainingBatch, submitFileTraining, submitTextTraining };

/** @deprecated Használd a `submitFileTraining` függvényt a `kbTrainingApi`-ból. */
export async function createFileIngestRun(
  kbUuid: string,
  files: File[],
  _characterCounts?: number[]
): Promise<IngestRun> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  const res = await api.post(`/kb/${kbUuid}/training/files`, form);
  return trainingFileResponseToIngestRun(res.data as TrainingTextResponse, kbUuid);
}

/** @deprecated Használd az `estimateFileTraining` függvényt a `kbTrainingApi`-ból. */
export async function estimateFileIngestRun(kbUuid: string, files: File[]): Promise<FileIngestEstimate> {
  return estimateFileTraining(kbUuid, files);
}

export async function createUrlIngestRun(
  kbUuid: string,
  items: Array<{ url: string; title?: string }>
): Promise<IngestRun> {
  const res = await api.post(`/kb/${kbUuid}/ingest/urls`, { items });
  return res.data as IngestRun;
}

export async function listIngestRuns(
  kbUuid: string,
  params?: { limit?: number; offset?: number }
): Promise<IngestRunListResponse> {
  try {
    const res = await api.get(`/kb/${kbUuid}/ingest/runs`, { params });
    return res.data as IngestRunListResponse;
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status;
    if (status === 404) {
      return {
        items: [],
        total_count: 0,
        limit: params?.limit ?? 100,
        offset: params?.offset ?? 0,
        has_more: false,
        summary: {
          total_run_count: 0,
          total_item_count: 0,
          total_char_count: 0,
          total_sentence_count: 0,
        },
      };
    }
    throw error;
  }
}

function isTrainingBatchRunId(runId: string): boolean {
  return runId.startsWith("training_batch_");
}

export async function getIngestRun(runId: string): Promise<IngestRun> {
  if (isTrainingBatchRunId(runId)) {
    return getTrainingBatch(runId);
  }
  try {
    const res = await api.get(`/kb/ingest/runs/${runId}`);
    return res.data as IngestRun;
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status;
    if (status === 404) {
      return getTrainingBatch(runId);
    }
    throw error;
  }
}

export async function reprocessIngestItem(itemId: string): Promise<IngestRun> {
  const res = await api.post(`/knowledge/ingest/items/${itemId}/reprocess`);
  return res.data as IngestRun;
}

export type TrainingItemRawDownload = {
  blob: Blob;
  filename: string;
  contentType: string;
};

function parseFilenameFromContentDisposition(header: string | undefined | null): string | null {
  if (!header) return null;
  const utf8Match = header.match(/filename\*\s*=\s*UTF-8''([^;\n]+)/i);
  if (utf8Match) {
    try {
      return decodeURIComponent(utf8Match[1].trim());
    } catch {
      return utf8Match[1].trim();
    }
  }
  const quoted = header.match(/filename\s*=\s*"([^"]+)"/i);
  if (quoted) return quoted[1].trim();
  const bare = header.match(/filename\s*=\s*([^;]+)/i);
  if (bare) return bare[1].trim();
  return null;
}

function isTextLikeContentType(contentType: string): boolean {
  const lower = contentType.toLowerCase();
  return (
    lower.startsWith("text/") ||
    lower.startsWith("application/json") ||
    lower.startsWith("application/xml") ||
    lower.startsWith("application/javascript")
  );
}

async function ensureUtf8TextBlob(blob: Blob, contentType: string): Promise<Blob> {
  if (!isTextLikeContentType(contentType)) return blob;
  const buffer = new Uint8Array(await blob.arrayBuffer());
  const hasBom =
    buffer.length >= 3 &&
    buffer[0] === 0xef &&
    buffer[1] === 0xbb &&
    buffer[2] === 0xbf;
  const baseType = contentType.split(";")[0].trim() || "text/plain";
  const targetType = `${baseType}; charset=utf-8`;
  if (hasBom) {
    return new Blob([buffer], { type: targetType });
  }
  const withBom = new Uint8Array(buffer.length + 3);
  withBom[0] = 0xef;
  withBom[1] = 0xbb;
  withBom[2] = 0xbf;
  withBom.set(buffer, 3);
  return new Blob([withBom], { type: targetType });
}

export async function downloadTrainingItemRaw(
  kbUuid: string,
  itemId: string,
): Promise<TrainingItemRawDownload> {
  const res = await api.get(`/kb/${kbUuid}/training/items/${itemId}/raw`, {
    responseType: "blob",
  });
  const headerFilename = parseFilenameFromContentDisposition(
    (res.headers as Record<string, string | undefined>)?.["content-disposition"] ??
      (res.headers as Record<string, string | undefined>)?.["Content-Disposition"],
  );
  const rawContentType =
    (res.headers as Record<string, string | undefined>)?.["content-type"] ??
    (res.headers as Record<string, string | undefined>)?.["Content-Type"] ??
    (res.data as Blob)?.type ??
    "application/octet-stream";
  const blob = await ensureUtf8TextBlob(res.data as Blob, rawContentType);
  return {
    blob,
    filename: headerFilename || itemId,
    contentType: blob.type || rawContentType,
  };
}

export type DeleteTrainingItemResponse = {
  item_id: string;
  knowledge_base_id: string;
  qdrant_points_deleted: number;
  qdrant_partial: boolean;
  rows_deleted: number;
  rows_by_table: Record<string, number>;
  raw_ref_deleted: boolean;
};

export async function deleteTrainingItem(
  kbUuid: string,
  itemId: string,
): Promise<DeleteTrainingItemResponse> {
  const res = await api.delete(`/kb/${kbUuid}/training/items/${itemId}`);
  return res.data as DeleteTrainingItemResponse;
}

export type RetrainTrainingItemResponse = {
  knowledge_base_id: string;
  old_item_id: string;
  new_item_id: string;
  new_training_batch_id: string;
  qdrant_points_deleted: number;
  rows_deleted: number;
};

export async function retrainTrainingItem(
  kbUuid: string,
  itemId: string,
): Promise<RetrainTrainingItemResponse> {
  const res = await api.post(`/kb/${kbUuid}/training/items/${itemId}/retrain`);
  return res.data as RetrainTrainingItemResponse;
}

export type RetrainPreviewResponse = {
  knowledge_base_id: string;
  item_id: string;
  required_chars: number;
  remaining_chars: number;
  available_chars: number;
  would_exceed: boolean;
  can_retrain: boolean;
};

export async function fetchRetrainTrainingItemPreview(
  kbUuid: string,
  itemId: string,
): Promise<RetrainPreviewResponse> {
  const res = await api.get(`/kb/${kbUuid}/training/items/${itemId}/retrain/preview`);
  return res.data as RetrainPreviewResponse;
}

export type TrainingQuotaErrorDetail = {
  code: string;
  message?: string;
  required_chars?: number;
  remaining_chars?: number;
  available_chars?: number;
  trained_chars?: number;
  included_chars?: number;
  plan_code?: string;
  plan_name?: string;
  is_highest_tier?: boolean;
  next_plan_code?: string;
  next_plan_name?: string;
  next_plan_included_chars?: number;
};

export function parseTrainingQuotaError(error: unknown): TrainingQuotaErrorDetail | null {
  const response = (error as { response?: { status?: number; data?: { detail?: unknown } } })?.response;
  if (!response || response.status !== 402) return null;
  const detail = response.data?.detail;
  if (!detail || typeof detail !== "object") return null;
  const obj = detail as Record<string, unknown>;
  const code = String(obj.code ?? "");
  if (code !== "training_quota_exceeded") return null;
  return {
    code,
    message: typeof obj.message === "string" ? obj.message : undefined,
    required_chars: typeof obj.required_chars === "number" ? obj.required_chars : undefined,
    remaining_chars: typeof obj.remaining_chars === "number" ? obj.remaining_chars : undefined,
    available_chars: typeof obj.available_chars === "number" ? obj.available_chars : undefined,
    trained_chars: typeof obj.trained_chars === "number" ? obj.trained_chars : undefined,
    included_chars: typeof obj.included_chars === "number" ? obj.included_chars : undefined,
    plan_code: typeof obj.plan_code === "string" ? obj.plan_code : undefined,
    plan_name: typeof obj.plan_name === "string" ? obj.plan_name : undefined,
    is_highest_tier: typeof obj.is_highest_tier === "boolean" ? obj.is_highest_tier : undefined,
    next_plan_code: typeof obj.next_plan_code === "string" ? obj.next_plan_code : undefined,
    next_plan_name: typeof obj.next_plan_name === "string" ? obj.next_plan_name : undefined,
    next_plan_included_chars:
      typeof obj.next_plan_included_chars === "number" ? obj.next_plan_included_chars : undefined,
  };
}
