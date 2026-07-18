from __future__ import annotations

# backend/apps/kb/kb_ingest/repository/TrainingRepository.py
# Feladat: Training batch / item / event SQLAlchemy perzisztencia (közvetlenül hívható).
# Sárközi Mihály - 2026.06.07

from sqlalchemy import func, select, text

from shared.utils.clock import utc_now

from apps.kb.kb_ingest.config import MetricsConf
from apps.kb.kb_ingest.dto.TrainingFileItemSave import TrainingFileItemSave
from apps.kb.kb_ingest.dto.TrainingFilesBatchSave import TrainingFilesBatchSave
from apps.kb.kb_ingest.dto.TrainingTextBatchSave import TrainingTextBatchSave
from apps.kb.kb_ingest.dto.TrainingTextSavedBatch import TrainingTextSavedBatch
from apps.kb.kb_ingest.enums.TrainingBatchStatus import TrainingBatchStatus
from apps.kb.kb_ingest.enums.TrainingMetric import TrainingMetric
from apps.kb.kb_ingest.enums.TrainingItemStatus import TrainingItemStatus
from apps.kb.kb_ingest.orm.TrainingBatch import TrainingBatch
from apps.kb.kb_ingest.orm.TrainingEvent import TrainingEvent
from apps.kb.kb_ingest.orm.TrainingItem import TrainingItem
from apps.kb.kb_ingest.enums.TrainingAuditEventType import TrainingAuditEventType
from apps.kb.shared.ids import new_id

_ITEM_STORAGE_METRICS_SQL = text(
    """
    SELECT
        i.id AS training_item_id,
        CASE WHEN i.input_type = 'file' THEN COALESCE(i.size_bytes, 0) ELSE 0 END AS file_bytes,
        CASE WHEN i.input_type <> 'file' THEN COALESCE(i.size_bytes, 0) ELSE 0 END AS non_file_bytes,
        COALESCE((i.metadata->>'char_count')::bigint, 0) AS training_char_count,
        COALESCE(chunk_sizes.chunk_bytes, 0) AS chunk_bytes
    FROM kb_ingest_items i
    LEFT JOIN (
        SELECT document_id, SUM(octet_length(text)) AS chunk_bytes
        FROM kb_chunks
        WHERE knowledge_base_id = :kb_id
          AND document_id = ANY(:item_ids)
        GROUP BY document_id
    ) chunk_sizes ON chunk_sizes.document_id = i.id
    WHERE i.knowledge_base_id = :kb_id
      AND i.id = ANY(:item_ids)
    """
)


class TrainingRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def ensure_active_knowledge_base(self, knowledge_base_id: str) -> None:
        from apps.kb.kb_ingest.validation.knowledge_base_guard import require_active_knowledge_base

        require_active_knowledge_base(self._session_factory, knowledge_base_id)

    def get_batch(self, batch_id: str, *, tenant: str | None = None) -> TrainingBatch | None:
        with self._session_factory() as session:
            batch = session.get(TrainingBatch, batch_id)
            if batch is None:
                return None
            if tenant is not None and batch.tenant != tenant:
                return None
            return batch

    def get_item(self, item_id: str) -> TrainingItem | None:
        with self._session_factory() as session:
            return session.get(TrainingItem, item_id)

    def list_items_for_batch(self, training_batch_id: str) -> list[TrainingItem]:
        with self._session_factory() as session:
            return list(
                session.execute(
                    select(TrainingItem)
                    .where(TrainingItem.training_batch_id == training_batch_id)
                    .order_by(TrainingItem.created_at.asc(), TrainingItem.id.asc())
                ).scalars().all()
            )

    def list_batches_for_knowledge_base(
        self,
        knowledge_base_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[TrainingBatch], int]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        with self._session_factory() as session:
            total = int(
                session.execute(
                    select(func.count(TrainingBatch.id)).where(
                        TrainingBatch.knowledge_base_id == knowledge_base_id
                    )
                ).scalar_one()
                or 0
            )
            batches = list(
                session.execute(
                    select(TrainingBatch)
                    .where(TrainingBatch.knowledge_base_id == knowledge_base_id)
                    .order_by(TrainingBatch.created_at.desc(), TrainingBatch.id.desc())
                    .offset(offset)
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return batches, total

    def list_items_for_knowledge_base(
        self,
        knowledge_base_id: str,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> tuple[list[TrainingItem], int]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        with self._session_factory() as session:
            total = int(
                session.execute(
                    select(func.count(TrainingItem.id)).where(
                        TrainingItem.knowledge_base_id == knowledge_base_id
                    )
                ).scalar_one()
                or 0
            )
            items = list(
                session.execute(
                    select(TrainingItem)
                    .where(TrainingItem.knowledge_base_id == knowledge_base_id)
                    .order_by(TrainingItem.created_at.desc(), TrainingItem.id.desc())
                    .offset(offset)
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return items, total

    def list_items_for_batches(self, batch_ids: list[str]) -> dict[str, list[TrainingItem]]:
        if not batch_ids:
            return {}
        with self._session_factory() as session:
            rows = list(
                session.execute(
                    select(TrainingItem)
                    .where(TrainingItem.training_batch_id.in_(batch_ids))
                    .order_by(TrainingItem.created_at.asc(), TrainingItem.id.asc())
                )
                .scalars()
                .all()
            )
        grouped: dict[str, list[TrainingItem]] = {batch_id: [] for batch_id in batch_ids}
        for row in rows:
            grouped.setdefault(row.training_batch_id, []).append(row)
        return grouped

    def list_events_for_batch(self, training_batch_id: str) -> list[TrainingEvent]:
        with self._session_factory() as session:
            return list(
                session.execute(
                    select(TrainingEvent)
                    .where(TrainingEvent.training_batch_id == training_batch_id)
                    .order_by(TrainingEvent.created_at.asc(), TrainingEvent.id.asc())
                ).scalars().all()
            )

    def save_training_text_batch(self, save: TrainingTextBatchSave) -> TrainingTextSavedBatch:
        now = utc_now()
        batch = TrainingBatch(
            id=save.batch_id,
            tenant=save.tenant,
            knowledge_base_id=save.knowledge_base_id,
            input_channel="text",
            status=TrainingBatchStatus.COMPLETED.value,
            batch_size=1,
            queued_count=1,
            failed_count=0,
            rejected_count=0,
            duplicate_count=0,
            created_by=save.created_by,
            created_at=now,
            completed_at=now,
            metadata_json={"input_types": ["text"]},
        )
        MetricsConf.increment(TrainingMetric.BATCH_CREATED, input_channel=batch.input_channel)
        
        item = TrainingItem(
            id=save.item_id,
            training_batch_id=save.batch_id,
            knowledge_base_id=save.knowledge_base_id,
            input_type="text",
            title=save.title,
            status=TrainingItemStatus.ACCEPTED.value,
            raw_ref=save.raw_ref,
            content_hash=save.content_hash,
            error_code=None,
            error_message=None,
            retryable=False,
            retry_count=0,
            duplicate_of_item_id=None,
            mime_type=save.mime_type,
            size_bytes=save.size_bytes,
            metadata_json=dict(save.metadata),
            created_at=now,
            updated_at=now,
        )
        MetricsConf.increment(TrainingMetric.ITEM_ACCEPTED, input_type=item.input_type)
    
        events = [
            TrainingEvent(
                id=new_id("training_event"),
                training_batch_id=save.batch_id,
                training_item_id=None,
                event_type=TrainingAuditEventType.TRAINING_BATCH_CREATED.value,
                message="",
                details_json={"batch_size": 1, "input_channel": "text"},
                created_at=now,
            ),
            TrainingEvent(
                id=new_id("training_event"),
                training_batch_id=save.batch_id,
                training_item_id=save.item_id,
                event_type=TrainingAuditEventType.TRAINING_ITEM_ACCEPTED.value,
                message="",
                details_json={"raw_ref": save.raw_ref},
                created_at=now,
            ),
            TrainingEvent(
                id=new_id("training_event"),
                training_batch_id=save.batch_id,
                training_item_id=None,
                event_type=TrainingAuditEventType.TRAINING_BATCH_COMPLETED.value,
                message="",
                details_json={
                    "status": TrainingBatchStatus.COMPLETED.value,
                    "accepted_count": 1,
                },
                created_at=now,
            ),
        ]
        with self._session_factory() as session:
            session.add(batch)
            session.add(item)
            for event in events:
                session.add(event)
            session.commit()

        MetricsConf.increment(
            TrainingMetric.BATCH_COMPLETED,
            status=TrainingBatchStatus.COMPLETED.value,
        )
        return TrainingTextSavedBatch(
            batch_id=save.batch_id,
            item_id=save.item_id,
            created_at=now,
            completed_at=batch.completed_at,
        )

    def save_training_files_batch(self, save: TrainingFilesBatchSave) -> TrainingTextSavedBatch:
        if not save.items:
            raise ValueError("Training files batch requires at least one item.")
        now = utc_now()
        batch_size = len(save.items)
        batch = TrainingBatch(
            id=save.batch_id,
            tenant=save.tenant,
            knowledge_base_id=save.knowledge_base_id,
            input_channel="file",
            status=TrainingBatchStatus.COMPLETED.value,
            batch_size=batch_size,
            queued_count=batch_size,
            failed_count=0,
            rejected_count=0,
            duplicate_count=0,
            created_by=save.created_by,
            created_at=now,
            completed_at=now,
            metadata_json={"input_types": ["file"]},
        )
        MetricsConf.increment(TrainingMetric.BATCH_CREATED, input_channel=batch.input_channel)

        orm_items: list[TrainingItem] = []
        for item_save in save.items:
            orm_items.append(self._build_training_item(item_save, batch_id=save.batch_id, kb_id=save.knowledge_base_id, now=now))
            MetricsConf.increment(TrainingMetric.ITEM_ACCEPTED, input_type="file")

        events = [
            TrainingEvent(
                id=new_id("training_event"),
                training_batch_id=save.batch_id,
                training_item_id=None,
                event_type=TrainingAuditEventType.TRAINING_BATCH_CREATED.value,
                message="",
                details_json={"batch_size": batch_size, "input_channel": "file"},
                created_at=now,
            ),
            *[
                TrainingEvent(
                    id=new_id("training_event"),
                    training_batch_id=save.batch_id,
                    training_item_id=item.id,
                    event_type=TrainingAuditEventType.TRAINING_ITEM_ACCEPTED.value,
                    message="",
                    details_json={"raw_ref": item.raw_ref},
                    created_at=now,
                )
                for item in orm_items
            ],
            TrainingEvent(
                id=new_id("training_event"),
                training_batch_id=save.batch_id,
                training_item_id=None,
                event_type=TrainingAuditEventType.TRAINING_BATCH_COMPLETED.value,
                message="",
                details_json={
                    "status": TrainingBatchStatus.COMPLETED.value,
                    "accepted_count": batch_size,
                },
                created_at=now,
            ),
        ]
        with self._session_factory() as session:
            session.add(batch)
            for item in orm_items:
                session.add(item)
            for event in events:
                session.add(event)
            session.commit()

        MetricsConf.increment(TrainingMetric.BATCH_COMPLETED, status=TrainingBatchStatus.COMPLETED.value)
        first_item = save.items[0]
        return TrainingTextSavedBatch(
            batch_id=save.batch_id,
            item_id=first_item.item_id,
            created_at=now,
            completed_at=batch.completed_at,
        )

    @staticmethod
    def _build_training_item(
        item_save: TrainingFileItemSave,
        *,
        batch_id: str,
        kb_id: str,
        now,
        input_type: str = "file",
    ) -> TrainingItem:
        return TrainingItem(
            id=item_save.item_id,
            training_batch_id=batch_id,
            knowledge_base_id=kb_id,
            input_type=input_type,
            title=item_save.title,
            status=TrainingItemStatus.ACCEPTED.value,
            raw_ref=item_save.raw_ref,
            content_hash=item_save.content_hash,
            error_code=None,
            error_message=None,
            retryable=False,
            retry_count=0,
            duplicate_of_item_id=None,
            mime_type=item_save.mime_type,
            size_bytes=item_save.size_bytes,
            metadata_json=dict(item_save.metadata),
            created_at=now,
            updated_at=now,
        )

    def create_retrain_batch_and_item(
        self,
        *,
        original: TrainingItem,
        new_batch_id: str,
        new_item_id: str,
        new_raw_ref: str,
        requested_by: int | None,
    ) -> tuple[str, str]:
        """A megadott eredeti elem alapján új batch + item rekordot ír be.

        Az új rekordok azonnal ``ACCEPTED`` státuszúak, és a régi raw_ref
        helyett az új (storage-ban frissen eltárolt) hivatkozást kapják meg.
        Az úgynevezett "újratanítás" innen onnan ezzel az új ``training_item_id``
        azonosítóval indul, így a régi és az új feldolgozás eseményei nem
        keverednek össze, és az understanding job idempotency kulcsa is más
        lesz.
        """

        now = utc_now()
        input_type = (original.input_type or "text").lower()
        input_channel = "text" if input_type == "text" else "file"

        batch = TrainingBatch(
            id=new_batch_id,
            tenant=getattr(original, "tenant", None) or "",
            knowledge_base_id=original.knowledge_base_id,
            input_channel=input_channel,
            status=TrainingBatchStatus.COMPLETED.value,
            batch_size=1,
            queued_count=1,
            failed_count=0,
            rejected_count=0,
            duplicate_count=0,
            created_by=requested_by if requested_by is not None else original.created_by,
            created_at=now,
            completed_at=now,
            metadata_json={
                "input_types": [input_type],
                "retrain_of_item_id": original.id,
            },
        )
        MetricsConf.increment(TrainingMetric.BATCH_CREATED, input_channel=input_channel)

        item = TrainingItem(
            id=new_item_id,
            training_batch_id=new_batch_id,
            knowledge_base_id=original.knowledge_base_id,
            input_type=input_type,
            title=original.title,
            status=TrainingItemStatus.ACCEPTED.value,
            raw_ref=new_raw_ref,
            content_hash=original.content_hash,
            error_code=None,
            error_message=None,
            retryable=False,
            retry_count=0,
            duplicate_of_item_id=None,
            original_filename=original.original_filename,
            mime_type=original.mime_type,
            size_bytes=original.size_bytes,
            origin_url=original.origin_url,
            final_url=original.final_url,
            status_code=original.status_code,
            metadata_json={
                **(dict(original.metadata_json or {})),
                "retrain_of_item_id": original.id,
            },
            created_at=now,
            updated_at=now,
        )
        MetricsConf.increment(TrainingMetric.ITEM_ACCEPTED, input_type=input_type)

        events = [
            TrainingEvent(
                id=new_id("training_event"),
                training_batch_id=new_batch_id,
                training_item_id=None,
                event_type=TrainingAuditEventType.TRAINING_BATCH_CREATED.value,
                message="",
                details_json={"batch_size": 1, "input_channel": input_channel, "retrain_of_item_id": original.id},
                created_at=now,
            ),
            TrainingEvent(
                id=new_id("training_event"),
                training_batch_id=new_batch_id,
                training_item_id=new_item_id,
                event_type=TrainingAuditEventType.TRAINING_ITEM_ACCEPTED.value,
                message="",
                details_json={"raw_ref": new_raw_ref, "retrain_of_item_id": original.id},
                created_at=now,
            ),
            TrainingEvent(
                id=new_id("training_event"),
                training_batch_id=new_batch_id,
                training_item_id=None,
                event_type=TrainingAuditEventType.TRAINING_BATCH_COMPLETED.value,
                message="",
                details_json={
                    "status": TrainingBatchStatus.COMPLETED.value,
                    "accepted_count": 1,
                    "retrain_of_item_id": original.id,
                },
                created_at=now,
            ),
        ]

        with self._session_factory() as session:
            session.add(batch)
            session.add(item)
            for event in events:
                session.add(event)
            session.commit()

        MetricsConf.increment(
            TrainingMetric.BATCH_COMPLETED,
            status=TrainingBatchStatus.COMPLETED.value,
        )
        return new_batch_id, new_item_id

    def find_duplicate_by_content_hash(
        self,
        knowledge_base_id: str,
        content_hash: str,
    ) -> TrainingItem | None:
        digest = str(content_hash or "").strip()
        if not digest:
            return None
        with self._session_factory() as session:
            return session.execute(
                select(TrainingItem)
                .where(
                    TrainingItem.knowledge_base_id == knowledge_base_id,
                    TrainingItem.content_hash == digest,
                    TrainingItem.status == TrainingItemStatus.ACCEPTED.value,
                )
                .order_by(TrainingItem.created_at.desc(), TrainingItem.id.desc())
                .limit(1)
            ).scalar_one_or_none()

    def list_raw_refs_for_items(
        self,
        knowledge_base_id: str,
        item_ids: list[str],
    ) -> dict[str, str]:
        ids = [str(item_id).strip() for item_id in item_ids if str(item_id or "").strip()]
        if not ids:
            return {}
        with self._session_factory() as session:
            rows = session.execute(
                select(TrainingItem.id, TrainingItem.raw_ref).where(
                    TrainingItem.knowledge_base_id == knowledge_base_id,
                    TrainingItem.id.in_(ids),
                )
            ).all()
        return {str(row[0]): str(row[1]) for row in rows if row[1]}

    def storage_metrics_for_items(
        self,
        knowledge_base_id: str,
        item_ids: list[str],
    ) -> dict[str, dict[str, int]]:
        ids = [str(item_id).strip() for item_id in item_ids if str(item_id or "").strip()]
        if not ids:
            return {}
        with self._session_factory() as session:
            rows = session.execute(
                _ITEM_STORAGE_METRICS_SQL,
                {"kb_id": knowledge_base_id, "item_ids": ids},
            ).mappings().all()
        metrics: dict[str, dict[str, int]] = {}
        for row in rows:
            item_id = str(row["training_item_id"])
            file_bytes = int(row["file_bytes"] or 0)
            non_file_bytes = int(row["non_file_bytes"] or 0)
            chunk_bytes = int(row["chunk_bytes"] or 0)
            training_char_count = int(row["training_char_count"] or 0)
            database_bytes = max(0, non_file_bytes + chunk_bytes)
            metrics[item_id] = {
                "file_bytes": max(0, file_bytes),
                "database_bytes": database_bytes,
                "total_bytes": max(0, file_bytes + database_bytes),
                "training_char_count": max(0, training_char_count),
            }
        return metrics


__all__ = ["TrainingRepository"]
