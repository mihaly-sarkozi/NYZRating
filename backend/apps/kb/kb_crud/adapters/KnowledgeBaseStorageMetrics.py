from __future__ import annotations

# backend/apps/kb/kb_crud/adapters/KnowledgeBaseStorageMetrics.py
# Feladat: Tenant sémából számolt tudástár tárhely metrikák (ingest item + chunk adatok).
# Sárközi Mihály - 2026.06.14

import logging

from sqlalchemy import text

from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase

logger = logging.getLogger(__name__)

_ITEM_METRICS_SQL = text(
    """
    SELECT
        COALESCE(SUM(size_bytes) FILTER (WHERE input_type = 'file' AND status <> 'deleted'), 0) AS file_bytes,
        COALESCE(SUM(size_bytes) FILTER (WHERE input_type <> 'file' AND status <> 'deleted'), 0) AS non_file_bytes,
        COALESCE(SUM((metadata->>'char_count')::bigint) FILTER (WHERE status <> 'deleted'), 0) AS training_char_count,
        COALESCE(SUM((metadata->>'char_count')::bigint), 0) AS lifetime_training_char_count
    FROM kb_ingest_items
    WHERE knowledge_base_id = :kb_id
    """
)

_CHUNK_BYTES_SQL = text(
    """
    SELECT COALESCE(SUM(octet_length(text)), 0)
    FROM kb_chunks
    WHERE knowledge_base_id = :kb_id
    """
)


class KnowledgeBaseStorageMetrics:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def metrics_for(self, kb: KnowledgeBase) -> dict[str, int]:
        kb_id = (kb.uuid or "").strip()
        if not kb_id:
            return {}
        try:
            with self._session_factory() as session:
                row = session.execute(_ITEM_METRICS_SQL, {"kb_id": kb_id}).mappings().first()
                file_bytes = int((row or {}).get("file_bytes") or 0)
                non_file_bytes = int((row or {}).get("non_file_bytes") or 0)
                training_char_count = int((row or {}).get("training_char_count") or 0)
                lifetime_training_char_count = max(
                    int((row or {}).get("lifetime_training_char_count") or 0),
                    training_char_count,
                )

                chunk_bytes = 0
                try:
                    chunk_bytes = int(session.execute(_CHUNK_BYTES_SQL, {"kb_id": kb_id}).scalar_one() or 0)
                except Exception:
                    logger.debug("kb_crud.chunk_bytes_query_failed", exc_info=True)

                database_bytes = max(0, non_file_bytes + chunk_bytes)
                total_bytes = max(0, file_bytes + database_bytes)
                return {
                    "file_bytes": max(0, file_bytes),
                    "database_bytes": database_bytes,
                    "qdrant_bytes": 0,
                    "total_bytes": total_bytes,
                    "training_char_count": max(0, training_char_count),
                    "lifetime_training_char_count": max(0, lifetime_training_char_count),
                }
        except Exception:
            logger.debug("kb_crud.storage_metrics_failed kb=%s", kb_id, exc_info=True)
            return {}


__all__ = ["KnowledgeBaseStorageMetrics"]
