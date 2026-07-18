from __future__ import annotations

# backend/apps/kb/kb_ingest/dto/TrainingItemContent.py
# Feladat: Tanítási elem nyers tartalmának letöltési DTO-ja.
# Sárközi Mihály - 2026.06.20

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingItemContent:
    item_id: str
    knowledge_base_id: str
    input_type: str
    data: bytes
    mime_type: str
    filename: str
    size_bytes: int


__all__ = ["TrainingItemContent"]
