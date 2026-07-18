# backend/tests/unit/test_subscription_proration.py
# Feladat: Upgrade/downgrade proration és SMS carryover szabályok unit tesztjei.
# Sárközi Mihály - 2026.07.18

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from apps.billing.domain import BillingPlan
from apps.billing.subscription_proration import (
    compute_upgrade_proration,
    is_downgrade,
    is_scheduled_change,
    questions_carryover_from_started_month,
)


def _plan(*, code: str, price_cents: int, questions: int = 100) -> BillingPlan:
    return BillingPlan(
        code=code,
        name=code,
        price_cents=price_cents,
        included_kbs=1,
        included_storage_gb=1,
        included_questions_monthly=questions,
        included_training_chars=0,
        max_users=None,
        trial_days=0,
    )


def test_questions_carryover_from_started_month() -> None:
    assert questions_carryover_from_started_month(old_plan_questions_monthly=100, used_total=30) == 70
    assert questions_carryover_from_started_month(old_plan_questions_monthly=100, used_total=0) == 100
    assert questions_carryover_from_started_month(old_plan_questions_monthly=100, used_total=100) == 0
    assert questions_carryover_from_started_month(old_plan_questions_monthly=100, used_total=150) == 0


def test_is_downgrade_by_price() -> None:
    plans = {
        "free": _plan(code="free", price_cents=0, questions=3),
        "starter": _plan(code="starter", price_cents=10000, questions=100),
        "pro": _plan(code="pro", price_cents=30000, questions=500),
    }
    current = SimpleNamespace(plan_code="pro", billing_period="monthly")
    assert is_downgrade(current=current, next_plan_code="starter", plans=plans) is True
    assert is_downgrade(current=current, next_plan_code="pro", plans=plans) is False


def test_downgrade_is_scheduled_change() -> None:
    plans = {
        "free": _plan(code="free", price_cents=0),
        "starter": _plan(code="starter", price_cents=10000),
        "pro": _plan(code="pro", price_cents=30000),
    }
    current = SimpleNamespace(plan_code="pro", billing_period="yearly")
    assert (
        is_scheduled_change(
            current=current,
            next_plan_code="starter",
            next_period="monthly",
            plans=plans,
        )
        is True
    )


def test_compute_upgrade_proration_credits_full_prepaid_months() -> None:
    plans = {
        "free": _plan(code="free", price_cents=0),
        "starter": _plan(code="starter", price_cents=10000),
        "pro": _plan(code="pro", price_cents=30000),
    }
    subscription = SimpleNamespace(
        plan_code="starter",
        billing_period="monthly",
        trial_ends_at=None,
    )
    preview = compute_upgrade_proration(
        subscription=subscription,
        normalized_plan="pro",
        normalized_period="monthly",
        plans=plans,
        period_end=date(2026, 7, 31),
        today=date(2026, 7, 16),
    )
    assert preview is not None
    assert preview["next_period_charge_cents"] == 30000
    # Az aktuális (megkezdett) hónap nem jár jóváírással — helyette az SMS-maradék jön át.
    assert preview["remaining_prepaid_months"] == 0
    assert preview["old_remaining_credit_cents"] == 0
    assert preview["total_charge_cents"] == 30000
    assert preview["immediate_use"] is True
    assert preview["paid_until_iso"] == "2026-08-16"


def test_compute_upgrade_proration_credits_multiple_prepaid_months() -> None:
    plans = {
        "free": _plan(code="free", price_cents=0),
        "starter": _plan(code="starter", price_cents=12000),
        "pro": _plan(code="pro", price_cents=30000),
    }
    subscription = SimpleNamespace(
        plan_code="starter",
        billing_period="quarterly",
        trial_ends_at=SimpleNamespace(date=lambda: date(2026, 9, 30)),
    )
    preview = compute_upgrade_proration(
        subscription=subscription,
        normalized_plan="pro",
        normalized_period="monthly",
        plans=plans,
        period_end=date(2026, 7, 31),
        today=date(2026, 7, 16),
    )
    assert preview is not None
    # Negyedéves (3) − megkezdett aktuális egység (1) = 2 hónap jóváírás
    assert preview["total_prepaid_months"] == 3
    assert preview["remaining_prepaid_months"] == 2
    assert preview["old_remaining_credit_cents"] == 2 * preview["old_monthly_cents"]
    assert preview["old_remaining_credit_cents"] % preview["old_monthly_cents"] == 0


def test_compute_upgrade_proration_quarterly_started_today_credits_two_months() -> None:
    """Ma indult negyedéves csomag: 3 hónapból az aktuális nem jár, 2 hónap jóváírás."""

    plans = {
        "free": _plan(code="free", price_cents=0),
        "starter": _plan(code="starter", price_cents=12000),
        "pro": _plan(code="pro", price_cents=30000),
    }
    today = date(2026, 7, 18)
    subscription = SimpleNamespace(
        plan_code="starter",
        billing_period="quarterly",
        trial_ends_at=SimpleNamespace(date=lambda: date(2026, 10, 18)),
    )
    preview = compute_upgrade_proration(
        subscription=subscription,
        normalized_plan="pro",
        normalized_period="quarterly",
        plans=plans,
        period_end=date(2026, 7, 31),
        today=today,
    )
    assert preview is not None
    assert preview["total_prepaid_months"] == 3
    assert preview["remaining_prepaid_months"] == 2
    assert preview["old_remaining_credit_cents"] == 2 * preview["old_monthly_cents"]
    assert preview["paid_until_iso"] == "2026-10-18"

def test_compute_upgrade_proration_paid_until_follows_cycle_from_switch_date() -> None:
    plans = {
        "free": _plan(code="free", price_cents=0),
        "starter": _plan(code="starter", price_cents=10000),
        "pro": _plan(code="pro", price_cents=30000),
    }
    subscription = SimpleNamespace(
        plan_code="starter",
        billing_period="monthly",
        trial_ends_at=None,
    )
    preview = compute_upgrade_proration(
        subscription=subscription,
        normalized_plan="pro",
        normalized_period="quarterly",
        plans=plans,
        period_end=date(2026, 7, 31),
        today=date(2026, 7, 18),
    )
    assert preview is not None
    assert preview["immediate_use"] is True
    assert preview["paid_until_iso"] == "2026-10-18"