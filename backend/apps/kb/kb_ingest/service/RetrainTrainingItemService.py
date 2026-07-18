from __future__ import annotations

# backend/apps/kb/kb_ingest/service/RetrainTrainingItemService.py
# Feladat: Egy meglévő ``training_item`` teljes újratanítása.
#
# Folyamat:
#   1. Eredeti tartalom karakterszámának ellenőrzése a billing kvótával
#      szemben — nincs elég keret esetén ``TrainingQuotaExceededError``.
#   2. Eredeti raw tartalom beolvasása a storage-ból.
#   3. Új ``training_batch`` + ``training_item`` rekord létrehozása ugyanazokkal
#      a metaadatokkal, friss raw_ref-fel (új storage objektum).
#   4. Régi ``training_item`` SOFT delete-je (DELETED státusz, derived adatok
#      hard törlése a ``DeleteTrainingItemService``-en keresztül).
#   5. Tanítási karakter felhasználás rögzítése a billingen.
#   6. ``UNDERSTANDING_REQUESTED`` esemény kibocsátása az új item-re.
# Sárközi Mihály - 2026.06.20

import logging

from apps.kb.kb_ingest.adapters.BillingReadingPolicy import (
    BillingReadingPolicy,
    TrainingQuotaEvaluation,
)
from apps.kb.kb_ingest.dto.RetrainPreviewResult import RetrainPreviewResult
from apps.kb.kb_ingest.dto.RetrainTrainingItemResult import RetrainTrainingItemResult
from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_ingest.errors.TrainingNotFoundError import TrainingNotFoundError
from apps.kb.kb_ingest.errors.TrainingProcessingError import TrainingProcessingError
from apps.kb.kb_ingest.errors.TrainingQueueUnavailableError import TrainingQueueUnavailableError
from apps.kb.kb_ingest.errors.TrainingQuotaExceededError import TrainingQuotaExceededError
from apps.kb.kb_ingest.events.understanding_requested_event import (
    add_understanding_requested_event,
)
from apps.kb.kb_ingest.repository.TrainingRepository import TrainingRepository
from apps.kb.kb_ingest.service.DeleteTrainingItemService import DeleteTrainingItemService
from apps.kb.ports.FileStorageInterface import FileStorageInterface
from apps.kb.shared.errors import KbStorageError
from apps.kb.shared.ids import new_id
from core.kernel.jobs.errors import JobQueueUnavailableError

logger = logging.getLogger(__name__)


class RetrainTrainingItemService:
    def __init__(
        self,
        *,
        repository: TrainingRepository,
        delete_service: DeleteTrainingItemService,
        file_storage: FileStorageInterface,
        billing_policy: BillingReadingPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._delete_service = delete_service
        self._file_storage = file_storage
        self._billing_policy = billing_policy

    def preview(
        self,
        *,
        knowledge_base_id: str,
        item_id: str,
        usage_tenant: object | None,
    ) -> RetrainPreviewResult:
        original = self._repository.get_item(item_id)
        if original is None or original.knowledge_base_id != knowledge_base_id:
            raise TrainingNotFoundError(TrainingErrorCode.ITEM_NOT_FOUND)
        required = self._required_chars_for(original)
        evaluation = self._evaluate_quota(usage_tenant, required)
        return RetrainPreviewResult(
            knowledge_base_id=knowledge_base_id,
            item_id=item_id,
            required_chars=evaluation.required_chars,
            remaining_chars=evaluation.remaining_chars,
            available_chars=evaluation.available_chars,
            would_exceed=evaluation.would_exceed,
            can_retrain=evaluation.allowed,
        )

    def retrain(
        self,
        *,
        knowledge_base_id: str,
        item_id: str,
        tenant_slug: str | None,
        requested_by: int | None,
        usage_tenant: object | None = None,
    ) -> RetrainTrainingItemResult:
        original = self._repository.get_item(item_id)
        if original is None or original.knowledge_base_id != knowledge_base_id:
            raise TrainingNotFoundError(TrainingErrorCode.ITEM_NOT_FOUND)
        if not original.raw_ref:
            raise TrainingNotFoundError(TrainingErrorCode.ITEM_NOT_FOUND)

        required = self._required_chars_for(original)
        evaluation = self._evaluate_quota(usage_tenant, required)
        if evaluation.would_exceed:
            raise TrainingQuotaExceededError.from_evaluation(evaluation)

        try:
            raw_data = self._file_storage.read_bytes(raw_ref=original.raw_ref)
        except KbStorageError as exc:
            raise TrainingProcessingError(TrainingErrorCode.STORAGE_ERROR) from exc

        new_batch_id = new_id("training_batch")
        new_item_id = new_id("training_item")

        try:
            new_raw_ref = self._store_raw_for_new_item(
                tenant_slug=tenant_slug,
                knowledge_base_id=knowledge_base_id,
                new_batch_id=new_batch_id,
                new_item_id=new_item_id,
                raw_data=raw_data,
                original=original,
            )
        except KbStorageError as exc:
            raise TrainingProcessingError(TrainingErrorCode.STORAGE_ERROR) from exc

        try:
            self._repository.create_retrain_batch_and_item(
                original=original,
                new_batch_id=new_batch_id,
                new_item_id=new_item_id,
                new_raw_ref=new_raw_ref,
                requested_by=requested_by,
            )
        except Exception:
            logger.exception(
                "Failed to persist retrain training item (kb=%s, old_item=%s, new_item=%s)",
                knowledge_base_id,
                item_id,
                new_item_id,
            )
            self._safe_delete_raw(new_raw_ref)
            raise

        delete_result = self._delete_service.delete(
            knowledge_base_id=knowledge_base_id,
            item_id=item_id,
            tenant_slug=tenant_slug,
            requested_by=requested_by,
            reason="retrain",
        )

        if self._billing_policy is not None and usage_tenant is not None and required > 0:
            storage_bytes = max(0, int(getattr(original, "size_bytes", 0) or len(raw_data)))
            self._billing_policy.record_training_usage(
                usage_tenant,
                char_count=required,
                storage_bytes=storage_bytes,
            )

        try:
            add_understanding_requested_event(
                tenant_slug=tenant_slug,
                training_batch_id=new_batch_id,
                training_item_id=new_item_id,
                knowledge_base_id=knowledge_base_id,
                created_by=requested_by,
                input_type=(original.input_type or "text"),
            )
        except (JobQueueUnavailableError, RuntimeError) as exc:
            raise TrainingQueueUnavailableError() from exc

        return RetrainTrainingItemResult(
            knowledge_base_id=knowledge_base_id,
            old_item_id=item_id,
            new_item_id=new_item_id,
            new_training_batch_id=new_batch_id,
            qdrant_points_deleted=delete_result.qdrant_points_deleted,
            rows_deleted=delete_result.rows_deleted,
        )

    def _required_chars_for(self, original) -> int:
        metadata = dict(getattr(original, "metadata_json", {}) or {})
        raw = metadata.get("char_count")
        if isinstance(raw, bool):
            return 0
        try:
            value = int(raw or 0)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
        size_bytes = getattr(original, "size_bytes", 0) or 0
        return max(0, int(size_bytes))

    def _evaluate_quota(
        self,
        usage_tenant: object | None,
        required_chars: int,
    ) -> TrainingQuotaEvaluation:
        if self._billing_policy is None or usage_tenant is None:
            return TrainingQuotaEvaluation(
                required_chars=required_chars,
                remaining_chars=required_chars,
                available_chars=required_chars,
                would_exceed=False,
            )
        return self._billing_policy.evaluate_training_quota(
            usage_tenant,
            char_count=required_chars,
        )

    def _store_raw_for_new_item(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        new_batch_id: str,
        new_item_id: str,
        raw_data: bytes,
        original,
    ) -> str:
        input_type = (original.input_type or "text").lower()
        tenant = tenant_slug or "default"
        if input_type == "text":
            try:
                content = raw_data.decode("utf-8")
            except UnicodeDecodeError:
                content = raw_data.decode("utf-8", errors="replace")
            return self._file_storage.store_text(
                tenant=tenant,
                knowledge_base_id=knowledge_base_id,
                training_batch_id=new_batch_id,
                training_item_id=new_item_id,
                content=content,
                content_type=original.mime_type or "text/plain",
            )
        filename = original.original_filename or f"{new_item_id}.bin"
        return self._file_storage.store_file(
            tenant=tenant,
            knowledge_base_id=knowledge_base_id,
            training_batch_id=new_batch_id,
            training_item_id=new_item_id,
            data=raw_data,
            filename=filename,
            content_type=original.mime_type,
        )

    def _safe_delete_raw(self, raw_ref: str) -> None:
        try:
            self._file_storage.delete_raw(raw_ref=raw_ref)
        except KbStorageError:
            logger.exception(
                "Failed to clean up retrain raw_ref after rollback (raw_ref=%s)",
                raw_ref,
            )


__all__ = ["RetrainTrainingItemService"]
