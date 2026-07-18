from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrainingQuotaEvaluation:
    """A tanítási karakter-keret aktuális állapota egy adott igényhez képest."""

    required_chars: int
    remaining_chars: int
    available_chars: int
    would_exceed: bool
    trained_chars: int = 0
    included_chars: int = 0
    plan_code: str | None = None
    plan_name: str | None = None
    is_highest_tier: bool = False
    next_plan_code: str | None = None
    next_plan_name: str | None = None
    next_plan_included_chars: int | None = None

    @property
    def allowed(self) -> bool:
        return not self.would_exceed


class BillingReadingPolicy:
    """ReadingPolicyPort — tenant usage kvóta és rögzítés a billing service-en keresztül."""

    def check_training_quota(
        self,
        tenant: object,
        *,
        char_count: int,
        storage_bytes: int = 0,
    ) -> None:
        _ = storage_bytes
        billing = self._billing_service()
        if billing is None:
            return
        allowed, message = billing.can_consume_training_chars(tenant, int(char_count or 0))
        if not allowed:
            raise ValueError(message or "Nincs elég tanítási karakterkeret a csomagban.")

    def evaluate_training_quota(
        self,
        tenant: object,
        *,
        char_count: int,
    ) -> TrainingQuotaEvaluation:
        """A tanítási karakter-keret strukturált kiértékelése (preview-hez/blokkoláshoz)."""

        required = max(0, int(char_count or 0))
        billing = self._billing_service()
        if billing is None:
            return TrainingQuotaEvaluation(
                required_chars=required,
                remaining_chars=required,
                available_chars=required,
                would_exceed=False,
            )
        try:
            summary = self._fetch_training_usage_summary(billing, tenant)
        except Exception:
            logger.warning("billing.training_usage_summary unavailable", exc_info=True)
            return TrainingQuotaEvaluation(
                required_chars=required,
                remaining_chars=required,
                available_chars=required,
                would_exceed=False,
            )
        remaining = max(0, int(summary.get("remaining_training_chars") or 0))
        available = max(0, int(summary.get("available_training_chars") or 0))
        trained_chars = max(0, int(summary.get("trained_chars") or 0))
        included_chars = max(0, int(summary.get("included_training_chars") or 0))
        next_plan_chars = summary.get("next_plan_included_training_chars")
        return TrainingQuotaEvaluation(
            required_chars=required,
            remaining_chars=remaining,
            available_chars=available,
            would_exceed=required > remaining,
            trained_chars=trained_chars,
            included_chars=included_chars,
            plan_code=(str(summary.get("plan_code")) if summary.get("plan_code") else None),
            plan_name=(str(summary.get("plan_name")) if summary.get("plan_name") else None),
            is_highest_tier=bool(summary.get("is_highest_tier", False)),
            next_plan_code=(str(summary.get("next_plan_code")) if summary.get("next_plan_code") else None),
            next_plan_name=(str(summary.get("next_plan_name")) if summary.get("next_plan_name") else None),
            next_plan_included_chars=(
                int(next_plan_chars) if isinstance(next_plan_chars, (int, float)) else None
            ),
        )

    def record_training_usage(
        self,
        tenant: object,
        *,
        char_count: int,
        storage_bytes: int = 0,
    ) -> None:
        billing = self._billing_service()
        if billing is None:
            return
        try:
            billing.record_training_ingest(
                tenant,
                char_count=max(0, int(char_count or 0)),
                storage_bytes=max(0, int(storage_bytes or 0)),
            )
        except Exception:
            logger.warning("billing.record_training_ingest failed", exc_info=True)

    def require_training_mfa_if_needed(self, user: object) -> None:
        _ = user

    @staticmethod
    def _billing_service() -> Any | None:
        try:
            from core.kernel.deps.facade import get_service
            from core.kernel.interface.keys import PLATFORM_TENANT_USAGE_SERVICE

            return get_service(PLATFORM_TENANT_USAGE_SERVICE)
        except Exception:
            logger.debug("kb_ingest.billing_service_unavailable", exc_info=True)
            return None

    @staticmethod
    def _fetch_training_usage_summary(billing: Any, tenant: object) -> dict[str, Any]:
        public = getattr(billing, "get_training_usage_summary", None)
        if callable(public):
            return dict(public(tenant) or {})
        ensure = getattr(billing, "ensure_subscription", None)
        private = getattr(billing, "_training_usage_summary", None)
        tenant_id = getattr(tenant, "tenant_id", None)
        if callable(ensure) and callable(private) and tenant_id is not None:
            subscription = ensure(tenant)
            return dict(private(int(tenant_id), subscription) or {})
        return {}


__all__ = ["BillingReadingPolicy", "TrainingQuotaEvaluation"]
