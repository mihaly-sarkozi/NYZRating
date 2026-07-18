from __future__ import annotations

# backend/apps/kb/kb_crud/adapters/KnowledgeBaseTrainingSummary.py
# Feladat: Tanítási összegzés kb_ingest_items alapján (legacy facade helyett).
# Sárközi Mihály - 2026.06.14

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)

_HAS_TRAINING_SQL = text(
    """
    SELECT EXISTS(
        SELECT 1 FROM kb_ingest_items
        WHERE knowledge_base_id = :kb_id
          AND status <> 'deleted'
        LIMIT 1
    )
    """
)

# A "lifetime" összesítés: a soft-deleted (DELETED státuszú) elemek
# karakterszámát is beleszámolja, így az újratanítások / törlések után is
# halmozódik. Az "élő" verzió csak a nem törölt elemek karaktereit adja össze.
_LIFETIME_TRAINING_CHAR_COUNT_SQL = text(
    """
    SELECT COALESCE(SUM((metadata->>'char_count')::bigint), 0)
    FROM kb_ingest_items
    WHERE knowledge_base_id = :kb_id
    """
)

_LIVE_TRAINING_CHAR_COUNT_SQL = text(
    """
    SELECT COALESCE(SUM((metadata->>'char_count')::bigint), 0)
    FROM kb_ingest_items
    WHERE knowledge_base_id = :kb_id
      AND status <> 'deleted'
    """
)


class KnowledgeBaseTrainingSummary:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def has_training(self, kb_uuid: str) -> bool:
        kb_id = (kb_uuid or "").strip()
        if not kb_id:
            return False
        try:
            with self._session_factory() as session:
                return bool(session.execute(_HAS_TRAINING_SQL, {"kb_id": kb_id}).scalar_one())
        except Exception:
            logger.debug("kb_crud.has_training_failed kb=%s", kb_id, exc_info=True)
            return False

    def training_char_count(self, kb_uuid: str) -> int:
        """Az élő (nem törölt) tanítási elemek karakterszámának összege."""
        return self._sum_training_chars(kb_uuid, _LIVE_TRAINING_CHAR_COUNT_SQL)

    def lifetime_training_char_count(self, kb_uuid: str) -> int:
        """A teljes élettartam alatt felhasznált tanítási karakterek (törölt és
        újratanított elemekkel együtt). Ez a számláló sosem csökken."""
        return self._sum_training_chars(kb_uuid, _LIFETIME_TRAINING_CHAR_COUNT_SQL)

    def _sum_training_chars(self, kb_uuid: str, sql) -> int:
        kb_id = (kb_uuid or "").strip()
        if not kb_id:
            return 0
        try:
            with self._session_factory() as session:
                total = session.execute(sql, {"kb_id": kb_id}).scalar_one()
                return max(0, int(total or 0))
        except Exception:
            logger.debug("kb_crud.training_char_count_failed kb=%s", kb_id, exc_info=True)
            return 0


__all__ = ["KnowledgeBaseTrainingSummary"]
