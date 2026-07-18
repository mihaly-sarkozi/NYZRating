from __future__ import annotations

# backend/apps/kb/kb_ingest/errors/TrainingQuotaExceededError.py
# Feladat: A tanítási karakter-keret túllépése esetén dobott hiba.
# Tartalmazza a kvóta részleteit, hogy a UI pontos üzenetet és csomagbővítő
# gombot tudjon megjeleníteni.
# Sárközi Mihály - 2026.06.20

from typing import Any

from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.shared.errors import KbProcessingError


class TrainingQuotaExceededError(KbProcessingError):
    def __init__(
        self,
        *,
        required_chars: int,
        remaining_chars: int,
        available_chars: int,
        message: str | None = None,
        trained_chars: int = 0,
        included_chars: int = 0,
        plan_code: str | None = None,
        plan_name: str | None = None,
        is_highest_tier: bool = False,
        next_plan_code: str | None = None,
        next_plan_name: str | None = None,
        next_plan_included_chars: int | None = None,
    ) -> None:
        self.code = TrainingErrorCode.QUOTA_EXCEEDED.value
        self.required_chars = max(0, int(required_chars or 0))
        self.remaining_chars = max(0, int(remaining_chars or 0))
        self.available_chars = max(0, int(available_chars or 0))
        self.trained_chars = max(0, int(trained_chars or 0))
        self.included_chars = max(0, int(included_chars or 0))
        self.plan_code = plan_code
        self.plan_name = plan_name
        self.is_highest_tier = bool(is_highest_tier)
        self.next_plan_code = next_plan_code
        self.next_plan_name = next_plan_name
        self.next_plan_included_chars = (
            int(next_plan_included_chars) if isinstance(next_plan_included_chars, int) else None
        )
        self.message_text = message or "Nincs elég tanítási karakterkeret a csomagban."
        super().__init__(self.code)

    @classmethod
    def from_evaluation(
        cls,
        evaluation: Any,
        *,
        message: str | None = None,
    ) -> "TrainingQuotaExceededError":
        """A BillingReadingPolicy.evaluate_training_quota visszatérési értékéből építjük fel."""

        return cls(
            required_chars=int(getattr(evaluation, "required_chars", 0) or 0),
            remaining_chars=int(getattr(evaluation, "remaining_chars", 0) or 0),
            available_chars=int(getattr(evaluation, "available_chars", 0) or 0),
            trained_chars=int(getattr(evaluation, "trained_chars", 0) or 0),
            included_chars=int(getattr(evaluation, "included_chars", 0) or 0),
            plan_code=getattr(evaluation, "plan_code", None),
            plan_name=getattr(evaluation, "plan_name", None),
            is_highest_tier=bool(getattr(evaluation, "is_highest_tier", False)),
            next_plan_code=getattr(evaluation, "next_plan_code", None),
            next_plan_name=getattr(evaluation, "next_plan_name", None),
            next_plan_included_chars=getattr(evaluation, "next_plan_included_chars", None),
            message=message,
        )


__all__ = ["TrainingQuotaExceededError"]
