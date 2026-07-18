from __future__ import annotations

# backend/apps/kb/kb_ingest/dto/RetrainTrainingItemResult.py
# Feladat: Egy training_item teljes pipeline újratanítás eredmény DTO-ja.
# A régi item törlődik, helyette új training_batch + training_item jön létre,
# ami a teljes Megértés → Felfedezés → Kódolás → Indexelés folyamaton átfut.
# Sárközi Mihály - 2026.06.20

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrainTrainingItemResult:
    knowledge_base_id: str
    old_item_id: str
    new_item_id: str
    new_training_batch_id: str
    qdrant_points_deleted: int
    rows_deleted: int


__all__ = ["RetrainTrainingItemResult"]
