from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apps.kb.kb_ingest.dto.IngestRunListResponse import (
    IngestItemResponse,
    IngestRunListResponse,
    IngestRunListSummaryResponse,
    IngestRunResponse,
)
from apps.kb.kb_ingest.mapper.ingest_run_mapper import (
    to_ingest_run_response,
    to_synthetic_ingest_run_from_items,
)
from apps.kb.kb_ingest.repository.TrainingRepository import TrainingRepository
from apps.kb.shared.errors import KbStorageError

if TYPE_CHECKING:
    from apps.kb.ports.FileStorageInterface import FileStorageInterface

logger = logging.getLogger(__name__)

_TEXT_PREVIEW_MAX_CHARS = 60
_TEXT_PREVIEW_MAX_ITEMS_PER_PAGE = 50


def _attach_storage_metrics(
    runs: list[IngestRunResponse],
    metrics_by_item: dict[str, dict[str, int]],
) -> list[IngestRunResponse]:
    if not metrics_by_item:
        return runs
    enriched: list[IngestRunResponse] = []
    for run in runs:
        items: list[IngestItemResponse] = []
        for item in run.items:
            metrics = metrics_by_item.get(item.id)
            if not metrics:
                items.append(item)
                continue
            metadata = dict(item.metadata or {})
            metadata["storage_metrics"] = metrics
            if metrics.get("training_char_count") and not metadata.get("char_count"):
                metadata["char_count"] = metrics["training_char_count"]
            items.append(item.model_copy(update={"metadata": metadata}))
        enriched.append(run.model_copy(update={"items": items}))
    return enriched


def _attach_text_previews(
    runs: list[IngestRunResponse],
    previews_by_item: dict[str, str],
) -> list[IngestRunResponse]:
    if not previews_by_item:
        return runs
    enriched: list[IngestRunResponse] = []
    for run in runs:
        items: list[IngestItemResponse] = []
        for item in run.items:
            preview = previews_by_item.get(item.id)
            if not preview:
                items.append(item)
                continue
            metadata = dict(item.metadata or {})
            metadata["text_preview"] = preview
            items.append(item.model_copy(update={"metadata": metadata}))
        enriched.append(run.model_copy(update={"items": items}))
    return enriched


def _build_preview_from_text(text: str) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return ""
    if len(cleaned) <= _TEXT_PREVIEW_MAX_CHARS:
        return cleaned
    return cleaned[:_TEXT_PREVIEW_MAX_CHARS].rstrip() + "…"


class ListIngestRunsService:
    def __init__(
        self,
        repository: TrainingRepository,
        *,
        file_storage: "FileStorageInterface | None" = None,
    ) -> None:
        self._repository = repository
        self._file_storage = file_storage

    def list_runs(
        self,
        knowledge_base_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> IngestRunListResponse:
        batches, total = self._repository.list_batches_for_knowledge_base(
            knowledge_base_id,
            limit=limit,
            offset=offset,
        )
        if total == 0:
            items, item_total = self._repository.list_items_for_knowledge_base(
                knowledge_base_id,
                limit=limit,
                offset=offset,
            )
            if item_total > 0:
                grouped: dict[str, list] = {}
                for item in items:
                    grouped.setdefault(item.training_batch_id, []).append(item)
                runs = [
                    to_synthetic_ingest_run_from_items(knowledge_base_id, batch_id, batch_items)
                    for batch_id, batch_items in sorted(
                        grouped.items(),
                        key=lambda pair: min(row.created_at for row in pair[1]),
                        reverse=True,
                    )
                ]
                total_item_count = sum(len(run.items) for run in runs)
                total_char_count = sum(
                    int(item.metadata.get("char_count") or 0)
                    for run in runs
                    for item in run.items
                )
                return IngestRunListResponse(
                    items=self._with_storage_metrics(knowledge_base_id, runs),
                    total_count=item_total,
                    limit=limit,
                    offset=offset,
                    has_more=(offset + len(items)) < item_total,
                    summary=IngestRunListSummaryResponse(
                        total_run_count=len(runs),
                        total_item_count=total_item_count,
                        total_char_count=total_char_count,
                        total_sentence_count=0,
                    ),
                )

        batch_ids = [batch.id for batch in batches]
        items_by_batch = self._repository.list_items_for_batches(batch_ids)
        runs = [
            to_ingest_run_response(batch, items_by_batch.get(batch.id, []))
            for batch in batches
        ]
        total_item_count = sum(len(run.items) for run in runs)
        total_char_count = sum(
            int(item.metadata.get("char_count") or 0)
            for run in runs
            for item in run.items
        )
        return IngestRunListResponse(
            items=self._with_storage_metrics(knowledge_base_id, runs),
            total_count=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(runs)) < total,
            summary=IngestRunListSummaryResponse(
                total_run_count=total,
                total_item_count=total_item_count,
                total_char_count=total_char_count,
                total_sentence_count=0,
            ),
        )

    def _with_storage_metrics(
        self,
        knowledge_base_id: str,
        runs: list[IngestRunResponse],
    ) -> list[IngestRunResponse]:
        item_ids = [item.id for run in runs for item in run.items]
        metrics = self._repository.storage_metrics_for_items(knowledge_base_id, item_ids)
        runs = _attach_storage_metrics(runs, metrics)
        previews = self._collect_text_previews(knowledge_base_id, runs)
        return _attach_text_previews(runs, previews)

    def _collect_text_previews(
        self,
        knowledge_base_id: str,
        runs: list[IngestRunResponse],
    ) -> dict[str, str]:
        if self._file_storage is None:
            return {}
        candidate_ids: list[str] = []
        for run in runs:
            for item in run.items:
                if (item.input_type or "").lower() != "text":
                    continue
                metadata = item.metadata or {}
                if metadata.get("text_preview"):
                    continue
                candidate_ids.append(item.id)
                if len(candidate_ids) >= _TEXT_PREVIEW_MAX_ITEMS_PER_PAGE:
                    break
            if len(candidate_ids) >= _TEXT_PREVIEW_MAX_ITEMS_PER_PAGE:
                break
        if not candidate_ids:
            return {}
        raw_refs = self._repository.list_raw_refs_for_items(knowledge_base_id, candidate_ids)
        previews: dict[str, str] = {}
        for item_id, raw_ref in raw_refs.items():
            preview = self._read_preview(raw_ref)
            if preview:
                previews[item_id] = preview
        return previews

    def _read_preview(self, raw_ref: str) -> str:
        try:
            data = self._file_storage.read_bytes(raw_ref=raw_ref)
        except KbStorageError:
            return ""
        except Exception:
            logger.exception("Failed to read text preview from storage (raw_ref=%s)", raw_ref)
            return ""
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
        return _build_preview_from_text(text)


__all__ = ["ListIngestRunsService"]
