# backend/tests/unit/traffic/test_traffic_service.py
# Feladat: A TrafficService read modell és DB-atomikus kérdésfoglalás integrációs pontjainak unit tesztjei.

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from apps.traffic.schemas.TrafficQuestionReservationResult import TrafficQuestionReservationResult
from apps.traffic.service.TrafficService import TrafficService


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 6, 6, tzinfo=UTC)


class FakeTrafficRepository:
    def list_catalog(self):
        return [
            {
                "entry_type": "plan",
                "code": "free",
                "name": "Free",
                "currency": "EUR",
                "price_cents": 0,
                "included": {
                    "knowledge_bases": 1,
                    "storage_gb": 1,
                    "questions_monthly": 3,
                    "training_chars": 1000,
                    "max_users": 5,
                    "trial_days": 7,
                },
                "metadata": {},
            }
        ]

    def get_subscription(self, tenant_id: int):
        return {
            "plan_code": "free",
            "billing_period": "monthly",
            "status": "trial",
            "extra_kb_count": 0,
            "extra_storage_gb": 0,
            "carryover_addon_questions": 2,
            "carryover_training_chars": 1000,
        }

    def list_question_usage(self, tenant_id: int, period_key: str):
        return [{"user_id": 12, "question_count": 2}]

    def get_training_usage(self, tenant_id: int, period_key: str):
        return {"trained_chars": 100, "storage_bytes": 0}

    def load_user_map(self):
        return {12: SimpleNamespace(name="Admin", email="admin@example.test")}

    def load_resource_counts(self):
        return {"users": 1, "knowledge_bases": 1, "storage_bytes": 0}

    def load_ingest_usage(self):
        return {"trained_chars": 0, "storage_bytes": 0}

    def list_training_addon_invoice_lines(self, tenant_id: int):
        return []


class FakeQuestionUsageRepository:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def ensure_addon_carryover_for_period(self, tenant_id: int, period_key: str) -> int:
        return 0

    def reserve_question(self, **kwargs):
        self.calls.append(kwargs)
        return TrafficQuestionReservationResult(
            allowed=True,
            reason=None,
            period_key=kwargs["period_key"],
            used_total=1,
            available_total=5,
            remaining_total=4,
        )


class FakeSmsSendRepository:
    def list_for_tenant(self, *, tenant_id: int, limit: int = 100):
        return []

    def create(self, **kwargs):
        return {
            "id": 1,
            "recipient_name": kwargs["recipient_name"],
            "phone": kwargs["phone"],
            "scheduled_at": kwargs["scheduled_at"],
            "status": kwargs["status"],
            "period_key": kwargs["period_key"],
            "created_at": datetime(2026, 6, 6, tzinfo=UTC),
        }


def test_reserve_question_delegates_to_atomic_repository():
    question_repo = FakeQuestionUsageRepository()
    service = TrafficService(
        FakeTrafficRepository(),
        question_usage_repository=question_repo,
        sms_send_repository=FakeSmsSendRepository(),
        clock=FixedClock(),
    )

    result = service.reserve_question(
        SimpleNamespace(tenant_id=7),
        12,
        request_context={"source": "test"},
    )

    assert result.allowed is True
    assert question_repo.calls == [
        {
            "tenant_id": 7,
            "user_id": 12,
            "period_key": "2026-06",
            "request_context": {"source": "test"},
        }
    ]


def test_overview_uses_traffic_usage_rows():
    service = TrafficService(
        FakeTrafficRepository(),
        question_usage_repository=FakeQuestionUsageRepository(),
        sms_send_repository=FakeSmsSendRepository(),
        clock=FixedClock(),
    )

    overview = service.get_overview(SimpleNamespace(tenant_id=7))

    assert overview.usage["questions"]["used_total"] == 2
    assert overview.usage["questions"]["available_total"] == 5
    assert overview.usage["questions_by_user"][0]["email"] == "admin@example.test"


def test_overview_allows_negative_question_carryover():
    class RepoWithNegativeCarryover(FakeTrafficRepository):
        def get_subscription(self, tenant_id: int):
            data = super().get_subscription(tenant_id)
            data["carryover_addon_questions"] = -1
            return data

    service = TrafficService(
        RepoWithNegativeCarryover(),
        question_usage_repository=FakeQuestionUsageRepository(),
        sms_send_repository=FakeSmsSendRepository(),
        clock=FixedClock(),
    )

    overview = service.get_overview(SimpleNamespace(tenant_id=7))
    questions = overview.usage["questions"]

    # plan 3 + carryover -1 = available 2; used 2 → remaining 0
    assert questions["addon_carryover"] == -1
    assert questions["available_total"] == 2
    assert questions["remaining_total"] == 0
    assert overview.limits["addon_questions_carryover"] == -1

