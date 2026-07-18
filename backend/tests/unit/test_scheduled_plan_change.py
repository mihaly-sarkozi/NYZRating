# backend/tests/unit/test_scheduled_plan_change.py
# Feladat: Ütemezett csomagváltás esedékességkori alkalmazásának unit tesztjei.
# Sárközi Mihály - 2026.07.18

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from apps.billing.workflows import RenewalUseCase, SubscriptionStatus


class _FakeClock:
    def __init__(self, day: date):
        self._day = day

    def now(self) -> datetime:
        return datetime.combine(self._day, datetime.min.time(), tzinfo=UTC)


def test_renewal_applies_scheduled_plan_before_billing_day() -> None:
    applied: list[dict] = []

    class FakeService:
        def __init__(self):
            self.clock = _FakeClock(date(2028, 4, 18))

        def _current_period(self):
            return ("2028-04", None, datetime(2028, 4, 18, tzinfo=UTC), date(2028, 4, 7))

        def _billing_due_date(self, subscription, fallback):
            return subscription.trial_ends_at.date()

        def _upsert_subscription_from_existing(self, tenant_id, subscription, **overrides):
            applied.append(overrides)
            return SimpleNamespace(**{**subscription.__dict__, **overrides})

        def apply_due_scheduled_plan_change(self, tenant, subscription):
            from apps.billing.service import BillingService

            return BillingService.apply_due_scheduled_plan_change(self, tenant, subscription)

    subscription = SimpleNamespace(
        plan_code="pro",
        billing_period="quarterly",
        status="active",
        trial_started_at=None,
        trial_ends_at=datetime(2028, 4, 18, tzinfo=UTC),
        scheduled_plan_code="starter",
        scheduled_billing_period="quarterly",
        scheduled_change_effective_period="2028-04-18",
    )
    service = FakeService()
    renewal = RenewalUseCase(service=service, state_machine=None, clock=service.clock)
    updated = renewal.execute(SimpleNamespace(tenant_id=1), subscription, period_key="2028-04", due_this_month=date(2028, 4, 7))

    assert applied and applied[0]["plan_code"] == "starter"
    assert applied[0]["trial_ends_at"] == subscription.trial_ends_at
    assert updated.plan_code == "starter"
    assert updated.scheduled_plan_code is None


def test_renewal_keeps_schedule_before_paid_until() -> None:
    class FakeService:
        def __init__(self):
            self.clock = _FakeClock(date(2028, 4, 10))

        def _current_period(self):
            return ("2028-04", None, datetime(2028, 4, 10, tzinfo=UTC), date(2028, 4, 7))

        def _billing_due_date(self, subscription, fallback):
            return subscription.trial_ends_at.date()

        def _upsert_subscription_from_existing(self, *args, **kwargs):
            raise AssertionError("scheduled change must not apply before paid-until")

        def apply_due_scheduled_plan_change(self, tenant, subscription):
            from apps.billing.service import BillingService

            return BillingService.apply_due_scheduled_plan_change(self, tenant, subscription)

    subscription = SimpleNamespace(
        plan_code="pro",
        billing_period="quarterly",
        status=SubscriptionStatus.ACTIVE.value,
        trial_started_at=None,
        trial_ends_at=datetime(2028, 4, 18, tzinfo=UTC),
        scheduled_plan_code="starter",
        scheduled_billing_period="quarterly",
        scheduled_change_effective_period="2028-04-18",
    )
    service = FakeService()
    renewal = RenewalUseCase(
        service=service,
        state_machine=None,
        clock=service.clock,
    )
    updated = renewal.execute(SimpleNamespace(tenant_id=1), subscription, period_key="2028-04", due_this_month=date(2028, 4, 7))
    assert updated.plan_code == "pro"
    assert updated.scheduled_plan_code == "starter"
