from __future__ import annotations

# backend/apps/kb/kb_ingest/dto/RetrainPreviewResult.py
# Feladat: Egy adott training_item újratanításának kvóta-előnézete.
# Sárközi Mihály - 2026.06.20

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrainPreviewResult:
    knowledge_base_id: str
    item_id: str
    required_chars: int
    remaining_chars: int
    available_chars: int
    would_exceed: bool
    can_retrain: bool


__all__ = ["RetrainPreviewResult"]
