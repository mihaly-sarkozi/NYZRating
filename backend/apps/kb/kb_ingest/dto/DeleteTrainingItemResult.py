from __future__ import annotations

# backend/apps/kb/kb_ingest/dto/DeleteTrainingItemResult.py
# Feladat: Egy training_item hard delete eredmény DTO.
# Sárközi Mihály - 2026.06.20

from dataclasses import dataclass


@dataclass(frozen=True)
class DeleteTrainingItemResult:
    item_id: str
    knowledge_base_id: str
    qdrant_points_deleted: int
    qdrant_partial: bool
    rows_deleted: int
    rows_by_table: dict[str, int]
    raw_ref_deleted: bool


__all__ = ["DeleteTrainingItemResult"]
