from __future__ import annotations

# backend/apps/kb/kb_ingest/repository/TrainingItemPurgeRepository.py
# Feladat: Egy ``training_item`` származtatott (derived) KB rekordjainak hard
# törlése — chunkok, embeddingek, indexelt pontok metaadatok, mention-ek és
# job-ok. A ``kb_ingest_items`` rekord SOFT delete-tel kerül feldolgozásra
# (status=DELETED, metaadat kiegészítve), hogy a "tanított karakter" számoló
# (lifetime) megmaradjon és a flow lista is láthassa a törölt elemeket.
# Az audit táblák (kb_ingest_events, kb_processing_events, kb_processing_issues)
# szintén megőrződnek, így a flow timeline a törlés után is megnézhető.
# A Qdrant pontok kezelése külön a ``DeleteIndexedChunksService``-ben történik.
# Sárközi Mihály - 2026.06.20

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _PurgeTable:
    table: str
    column: str


# A törlés sorrendje: gyermek → szülő. A ``kb_ingest_items`` SOFT delete-tel
# kerül feldolgozásra a ``mark_item_deleted`` metódusban — itt csak az index/
# embedding/discovery/understanding pipeline derived rekordjai vannak.
_PURGE_TABLES_BY_TRAINING_ITEM_ID: tuple[_PurgeTable, ...] = (
    # Indexing — Qdrant pontok metaadatok és index futtatások
    _PurgeTable("kb_index_verification_items", "training_item_id"),
    _PurgeTable("kb_index_verifications", "training_item_id"),
    _PurgeTable("kb_indexed_chunks", "training_item_id"),
    _PurgeTable("kb_indexing_jobs", "training_item_id"),
    # Embedding
    _PurgeTable("kb_embeddings", "training_item_id"),
    _PurgeTable("kb_embedding_jobs", "training_item_id"),
    # Discovery — mention-ek és származtatott tudás
    _PurgeTable("kb_entity_mentions", "training_item_id"),
    _PurgeTable("kb_temporal_mentions", "training_item_id"),
    _PurgeTable("kb_spatial_mentions", "training_item_id"),
    _PurgeTable("kb_process_mentions", "training_item_id"),
    _PurgeTable("kb_topics", "training_item_id"),
    _PurgeTable("kb_keywords", "training_item_id"),
    _PurgeTable("kb_enrichments", "training_item_id"),
    _PurgeTable("kb_relationships", "training_item_id"),
    _PurgeTable("kb_discovery_jobs", "training_item_id"),
    # Understanding — chunkok és normalizált / kivett tartalom
    _PurgeTable("kb_normalized_content_parts", "training_item_id"),
    _PurgeTable("kb_normalized_content", "training_item_id"),
    _PurgeTable("kb_extracted_content_parts", "training_item_id"),
    _PurgeTable("kb_extracted_content", "training_item_id"),
    _PurgeTable("kb_understanding_jobs", "training_item_id"),
    # Search — citation / kontextus blokkok (history runs/results megtartva)
    _PurgeTable("kb_search_context_blocks", "training_item_id"),
    _PurgeTable("kb_search_citations", "training_item_id"),
)

# Külön: ``document_id`` alapú rekordok (a chunk és entitás ezzel kapcsolódik).
_PURGE_TABLES_BY_DOCUMENT_ID: tuple[_PurgeTable, ...] = (
    _PurgeTable("kb_chunks", "document_id"),
    _PurgeTable("kb_entities", "document_id"),
    _PurgeTable("kb_scores", "document_id"),
)

# A kb_ingest_items soft delete-jét végző UPDATE — status és metaadatok.
# (Az ORM-ben ez a "metadata_json" attribútum, de a tényleges SQL oszlopnév
# a táblában: ``metadata``. Az updated_at timezone-naive, így az UTC
# időbélyegzőt expliciten cast-eljük ``timestamp without time zone``-ra.)
_SOFT_DELETE_INGEST_ITEM_SQL = (
    "UPDATE kb_ingest_items "
    "SET status = :deleted_status, "
    "    raw_ref = NULL, "
    "    metadata = COALESCE(metadata, '{}'::jsonb) || :patch::jsonb, "
    "    updated_at = :now_naive "
    "WHERE id = :item_id AND knowledge_base_id = :kb_id"
)


@dataclass(frozen=True)
class TrainingItemPurgeReport:
    by_table: dict[str, int]
    soft_deleted: bool = False

    @property
    def total(self) -> int:
        return sum(self.by_table.values())


class TrainingItemPurgeRepository:
    """Egy ``training_item``-ből származó derived KB rekordok hard delete-je
    + a ``kb_ingest_items`` soft delete-je (status=DELETED)."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def purge(
        self,
        *,
        knowledge_base_id: str,
        training_item_id: str,
        deleted_by: int | None = None,
        deleted_at_iso: str | None = None,
        reason: str | None = None,
    ) -> TrainingItemPurgeReport:
        kb_id = str(knowledge_base_id or "").strip()
        item_id = str(training_item_id or "").strip()
        if not kb_id or not item_id:
            return TrainingItemPurgeReport(by_table={}, soft_deleted=False)

        report: dict[str, int] = {}
        soft_deleted = False
        with self._session_factory() as session:
            self._delete_set(session, _PURGE_TABLES_BY_TRAINING_ITEM_ID, item_id, report)
            self._delete_set(session, _PURGE_TABLES_BY_DOCUMENT_ID, item_id, report)
            soft_deleted = self._mark_item_deleted(
                session,
                item_id=item_id,
                kb_id=kb_id,
                deleted_by=deleted_by,
                deleted_at_iso=deleted_at_iso,
                reason=reason,
                report=report,
            )
            session.commit()
        return TrainingItemPurgeReport(by_table=report, soft_deleted=soft_deleted)

    @staticmethod
    def _execute_within_savepoint(
        session,
        sql: str,
        params: dict[str, str],
        *,
        table: str,
    ) -> int:
        """Egy DELETE-et SAVEPOINT-ban (nested transaction) hajt végre.

        Ha a tábla a tenant sémában nem létezik, vagy bármilyen más SQL hibát
        okoz, a SAVEPOINT visszagörgeti a hibát anélkül, hogy a befoglaló
        tranzakciót aborted állapotba sodorná. Így a többi DELETE továbbra is
        végrehajtódik és a végső commit életben marad.
        """

        try:
            with session.begin_nested():
                result = session.execute(text(sql), params)
            return int(result.rowcount or 0)
        except Exception:
            logger.exception(
                "Failed to purge training item rows from %s (sql=%s)",
                table,
                sql,
            )
            return 0

    @classmethod
    def _delete_set(
        cls,
        session,
        tables: Sequence[_PurgeTable],
        item_id: str,
        report: dict[str, int],
    ) -> None:
        for entry in tables:
            report[entry.table] = cls._execute_within_savepoint(
                session,
                f"DELETE FROM {entry.table} WHERE {entry.column} = :item_id",
                {"item_id": item_id},
                table=entry.table,
            )

    @classmethod
    def _mark_item_deleted(
        cls,
        session,
        *,
        item_id: str,
        kb_id: str,
        deleted_by: int | None,
        deleted_at_iso: str | None,
        reason: str | None,
        report: dict[str, int],
    ) -> bool:
        import json
        from datetime import datetime, timezone

        from apps.kb.kb_ingest.enums.TrainingItemStatus import TrainingItemStatus

        patch: dict[str, object] = {"deleted_at": deleted_at_iso}
        if deleted_by is not None:
            patch["deleted_by"] = int(deleted_by)
        if reason:
            patch["delete_reason"] = str(reason)
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            with session.begin_nested():
                result = session.execute(
                    text(_SOFT_DELETE_INGEST_ITEM_SQL),
                    {
                        "item_id": item_id,
                        "kb_id": kb_id,
                        "deleted_status": TrainingItemStatus.DELETED.value,
                        "patch": json.dumps(patch),
                        "now_naive": now_naive,
                    },
                )
            rowcount = int(result.rowcount or 0)
            report["kb_ingest_items"] = rowcount
            return rowcount > 0
        except Exception:
            logger.exception(
                "Failed to soft-delete kb_ingest_items row (kb=%s, item=%s)", kb_id, item_id,
            )
            report["kb_ingest_items"] = 0
            return False


__all__ = [
    "TrainingItemPurgeReport",
    "TrainingItemPurgeRepository",
]
