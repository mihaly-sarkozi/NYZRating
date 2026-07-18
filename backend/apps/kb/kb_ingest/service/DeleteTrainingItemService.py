from __future__ import annotations

# backend/apps/kb/kb_ingest/service/DeleteTrainingItemService.py
# Feladat: Egy konkrét ``training_item`` (tudástár-elem) hard törlése —
# Qdrant pontok eltávolítása, KB szerkezeti rekordok purge-ja, raw fájl
# törlése a storage-ból. KB-en belüli isolation: cross-tenant / másik KB
# id-ja "nem található" hibát ad vissza.
# Sárközi Mihály - 2026.06.20

import logging
from typing import TYPE_CHECKING

from apps.kb.kb_ingest.dto.DeleteTrainingItemResult import DeleteTrainingItemResult
from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_ingest.errors.TrainingNotFoundError import TrainingNotFoundError
from apps.kb.kb_ingest.repository.TrainingItemPurgeRepository import (
    TrainingItemPurgeRepository,
)
from apps.kb.kb_ingest.repository.TrainingRepository import TrainingRepository
from apps.kb.ports.FileStorageInterface import FileStorageInterface
from apps.kb.shared.errors import KbStorageError

if TYPE_CHECKING:
    from apps.kb.kb_indexing.service.DeleteIndexedChunksService import (
        DeleteIndexedChunksService,
    )

logger = logging.getLogger(__name__)


class DeleteTrainingItemService:
    def __init__(
        self,
        *,
        repository: TrainingRepository,
        purge_repository: TrainingItemPurgeRepository,
        delete_indexed_chunks_service: "DeleteIndexedChunksService",
        file_storage: FileStorageInterface,
        knowledge_base_collection_resolver,
    ) -> None:
        self._repository = repository
        self._purge_repository = purge_repository
        self._delete_chunks = delete_indexed_chunks_service
        self._file_storage = file_storage
        self._collection_resolver = knowledge_base_collection_resolver

    def delete(
        self,
        *,
        knowledge_base_id: str,
        item_id: str,
        tenant_slug: str | None,
        requested_by: int | None,
        reason: str | None = None,
    ) -> DeleteTrainingItemResult:
        from apps.kb.kb_ingest.enums.TrainingItemStatus import TrainingItemStatus
        from shared.utils.clock import utc_now

        item = self._repository.get_item(item_id)
        if item is None or item.knowledge_base_id != knowledge_base_id:
            raise TrainingNotFoundError(TrainingErrorCode.ITEM_NOT_FOUND)
        if (item.status or "").lower() == TrainingItemStatus.DELETED.value:
            return DeleteTrainingItemResult(
                item_id=item_id,
                knowledge_base_id=knowledge_base_id,
                qdrant_points_deleted=0,
                qdrant_partial=False,
                rows_deleted=0,
                rows_by_table={},
                raw_ref_deleted=False,
            )

        collection_name = self._collection_resolver.get_qdrant_collection_name(knowledge_base_id) or ""
        qdrant_deleted = 0
        qdrant_partial = False
        if collection_name:
            try:
                delete_result = self._delete_chunks.delete_for_training_item(
                    tenant_slug=tenant_slug,
                    knowledge_base_id=knowledge_base_id,
                    training_item_id=item_id,
                    collection_name=collection_name,
                    removed_by=requested_by,
                    reason="training_item_deleted",
                )
                qdrant_deleted = int(delete_result.qdrant_deleted or 0)
                qdrant_partial = bool(delete_result.partial)
            except Exception:
                logger.exception(
                    "Qdrant point cleanup failed during training item delete (kb=%s, item=%s)",
                    knowledge_base_id,
                    item_id,
                )
                qdrant_partial = True

        purge_report = self._purge_repository.purge(
            knowledge_base_id=knowledge_base_id,
            training_item_id=item_id,
            deleted_by=requested_by,
            deleted_at_iso=utc_now().isoformat(),
            reason=reason,
        )

        raw_ref_deleted = False
        if item.raw_ref:
            try:
                self._file_storage.delete_raw(raw_ref=item.raw_ref)
                raw_ref_deleted = True
            except KbStorageError:
                logger.exception(
                    "Raw file delete failed during training item delete (kb=%s, item=%s, raw_ref=%s)",
                    knowledge_base_id,
                    item_id,
                    item.raw_ref,
                )

        return DeleteTrainingItemResult(
            item_id=item_id,
            knowledge_base_id=knowledge_base_id,
            qdrant_points_deleted=qdrant_deleted,
            qdrant_partial=qdrant_partial,
            rows_deleted=purge_report.total,
            rows_by_table=dict(purge_report.by_table),
            raw_ref_deleted=raw_ref_deleted,
        )


__all__ = ["DeleteTrainingItemService"]
