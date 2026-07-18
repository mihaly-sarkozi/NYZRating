from __future__ import annotations

# backend/apps/kb/kb_ingest/adapters/NoOpReadingPolicy.py
# Feladat: Ideiglenes ReadingPolicyPort implementáció fejlesztéshez.
# (Átemelve a megszüntetett kb_reading modulból.)
# Sárközi Mihály - 2026.06.11


from apps.kb.kb_ingest.adapters.BillingReadingPolicy import TrainingQuotaEvaluation


class NoOpReadingPolicy:
    """Kvóta és hitelesítés ellenőrzés nélküli szabályzat."""

    def check_training_quota(
        self,
        tenant: object,
        *,
        char_count: int,
        storage_bytes: int = 0,
    ) -> None:
        _ = (tenant, char_count, storage_bytes)

    def evaluate_training_quota(
        self,
        tenant: object,
        *,
        char_count: int,
    ) -> TrainingQuotaEvaluation:
        _ = tenant
        required = max(0, int(char_count or 0))
        return TrainingQuotaEvaluation(
            required_chars=required,
            remaining_chars=required,
            available_chars=required,
            would_exceed=False,
        )

    def record_training_usage(
        self,
        tenant: object,
        *,
        char_count: int,
        storage_bytes: int = 0,
    ) -> None:
        _ = (tenant, char_count, storage_bytes)

    def require_training_mfa_if_needed(self, user: object) -> None:
        _ = user


__all__ = ["NoOpReadingPolicy"]
