# backend/apps/billing/workflows.py
# Feladat: A billing előfizetés lifecycle use case-eit és state machine-jét tartalmazza. Renewal, restriction, invoicing és due cycle feldolgozást választ le a nagy BillingService-ről, hogy a számlázási ciklus döntései tesztelhetőbbek legyenek. Program-specifikus workflow réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from apps.billing.constants import PAYMENT_FAILURE_DEACTIVATION_DAYS
from core.kernel.runtime.clock import Clock

logger = logging.getLogger(__name__)


class SubscriptionStatus(StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    RESTRICTED = "restricted"


@dataclass(frozen=True)
class SubscriptionStateMachine:
    clock: Clock

    def resolve(self, subscription: Any, *, overdue_invoice: Any | None = None, now: datetime | None = None) -> str:
        current = now or self.clock.now()
        if overdue_invoice is not None and getattr(overdue_invoice, "status", None) in {"issued", "payment_failed"}:
            due_at = getattr(overdue_invoice, "due_at", None)
            if due_at is not None and due_at.date() < current.date():
                return SubscriptionStatus.RESTRICTED.value

        if getattr(subscription, "plan_code", None) == "free":
            trial_ends_at = getattr(subscription, "trial_ends_at", None)
            if trial_ends_at is not None and trial_ends_at <= current:
                return SubscriptionStatus.RESTRICTED.value
            return SubscriptionStatus.TRIAL.value

        return SubscriptionStatus.ACTIVE.value


@dataclass
class RenewalUseCase:
    service: Any
    state_machine: SubscriptionStateMachine
    clock: Clock

    def execute(self, tenant: Any, subscription: Any, *, period_key: str, due_this_month) -> Any:
        # period_key / due_this_month: legacy calendar cycle; a váltás a subscription
        # fizetett periódusának végén (billing due) lép életbe, a számla előtt.
        _ = period_key, due_this_month
        return self.service.apply_due_scheduled_plan_change(tenant, subscription)


@dataclass
class RestrictionUseCase:
    service: Any
    state_machine: SubscriptionStateMachine
    clock: Clock

    def sync_status(self, tenant: Any, subscription: Any) -> Any:
        current = self.clock.now()
        cancellation = self.service._repo.get_latest_cancellation_request(tenant.tenant_id)
        cancellation_effective_at = None
        cancellation_requires_restriction = False
        if cancellation is not None and str(getattr(cancellation, "status", "") or "").lower() == "deactivation_requested":
            cancellation_effective_at = getattr(cancellation, "effective_at", None)
            cancellation_deactivated_at = getattr(cancellation, "deactivated_at", None)
            if cancellation_effective_at is not None and cancellation_deactivated_at is None and cancellation_effective_at <= current:
                cancellation_requires_restriction = True
                if current.date() >= (cancellation_effective_at.date() + timedelta(days=7)):
                    self.service._tenant_repo.deactivate(int(tenant.tenant_id), updated_by=None)
                    self.service._repo.mark_cancellation_deactivated(int(cancellation.id), current)

        failed_invoice = self.service._repo.get_latest_invoice_for_type(tenant.tenant_id, "monthly_subscription_failed")
        open_failed = None
        latest_monthly = self.service._repo.get_latest_invoice_for_type(tenant.tenant_id, "monthly_subscription")
        if latest_monthly is not None and getattr(latest_monthly, "status", None) == "payment_failed":
            open_failed = latest_monthly
        if failed_invoice is not None and getattr(failed_invoice, "status", None) == "payment_failed":
            if open_failed is None or (
                getattr(failed_invoice, "issued_at", None) is not None
                and getattr(open_failed, "issued_at", None) is not None
                and failed_invoice.issued_at > open_failed.issued_at
            ):
                open_failed = failed_invoice
        paid_invoice = self.service._repo.get_latest_invoice_for_type(tenant.tenant_id, "monthly_subscription")
        overdue_invoice = None
        if open_failed is not None and getattr(open_failed, "status", None) == "payment_failed":
            failed_due_at = getattr(open_failed, "due_at", None)
            paid_issued_at = (
                getattr(paid_invoice, "issued_at", None)
                if paid_invoice is not None and getattr(paid_invoice, "status", None) in {"paid", "simulated_paid", "manual_paid"}
                else None
            )
            failed_issued_at = getattr(open_failed, "issued_at", None)
            paid_after_failed = False
            if paid_issued_at is not None and failed_issued_at is not None:
                try:
                    paid_after_failed = paid_issued_at > failed_issued_at
                except TypeError:
                    paid_after_failed = paid_issued_at.replace(tzinfo=None) > failed_issued_at.replace(tzinfo=None)
            if not paid_after_failed and failed_due_at is not None and failed_due_at.date() < current.date():
                overdue_invoice = open_failed
        if overdue_invoice is not None:
            invoice_issued_at = getattr(overdue_invoice, "issued_at", None)
            subscription_updated_at = getattr(subscription, "updated_at", None)
            if invoice_issued_at is not None and subscription_updated_at is not None:
                try:
                    invoice_is_older_than_subscription = invoice_issued_at < subscription_updated_at
                except TypeError:
                    invoice_is_older_than_subscription = invoice_issued_at.replace(tzinfo=None) < subscription_updated_at.replace(tzinfo=None)
                if invoice_is_older_than_subscription:
                    overdue_invoice = None
        next_status = self.state_machine.resolve(subscription, overdue_invoice=overdue_invoice, now=self.clock.now())
        if cancellation_requires_restriction:
            next_status = SubscriptionStatus.RESTRICTED.value
        if overdue_invoice is not None:
            failed_due_at = getattr(overdue_invoice, "due_at", None)
            if failed_due_at is not None and current.date() >= (failed_due_at.date() + timedelta(days=PAYMENT_FAILURE_DEACTIVATION_DAYS)):
                self.service._tenant_repo.deactivate(int(tenant.tenant_id), updated_by=None)
        if next_status == subscription.status:
            return subscription
        return self.service._upsert_subscription_from_existing(
            tenant.tenant_id,
            subscription,
            status=next_status,
        )

    def assert_not_restricted(self, tenant: Any, subscription: Any) -> tuple[bool, str | None]:
        current = self.sync_status(tenant, subscription)
        if current.status != SubscriptionStatus.RESTRICTED.value:
            return True, None
        return False, "Az előfizetés korlátozott állapotban van. Rendezd a számlázást vagy válassz új csomagot."


@dataclass
class InvoicingUseCase:
    service: Any
    clock: Clock

    def execute(
        self,
        tenant: Any,
        subscription: Any,
        *,
        next_period_key: str,
        next_charge_date,
        plan_map: dict[str, Any],
    ) -> None:
        now = self.clock.now()
        if subscription.plan_code == "free":
            return
        if subscription.status == SubscriptionStatus.RESTRICTED.value:
            return
        cancellation = self.service._repo.get_latest_cancellation_request(tenant.tenant_id)
        if cancellation is not None and str(getattr(cancellation, "status", "") or "").lower() == "deactivation_requested":
            return
        billing_date = self.service._billing_due_date(subscription, next_charge_date)
        if now.date() < billing_date:
            return
        period_key = self.service._subscription_period_key(billing_date)
        invoice_exists = self.service._repo.get_invoice(tenant.tenant_id, "monthly_subscription", period_key)
        if invoice_exists is not None:
            return
        failed_exists = self.service._repo.get_invoice(tenant.tenant_id, "monthly_subscription_failed", period_key)
        if failed_exists is not None:
            return
        self.service.issue_subscription_payment_request(tenant, subscription, billing_date=billing_date, period_key=period_key)


@dataclass
class BillingCycleProcessor:
    service: Any
    renewal_use_case: RenewalUseCase
    restriction_use_case: RestrictionUseCase
    invoicing_use_case: InvoicingUseCase
    clock: Clock

    def process(self) -> None:
        period_key, _, period_end_dt, due_this_month = self.service._current_period()
        plan_map = self.service._plan_map()
        next_period_key = f"{period_end_dt.year:04d}-{period_end_dt.month:02d}"
        next_charge_date = self.service._charge_date_before_expiry(period_end_dt.date())

        for tenant_row in self.service._repo.list_active_tenants():
            try:
                tenant = self.service._tenant_repo.get_snapshot_by_slug(tenant_row.slug)
                if tenant is None:
                    continue
                subscription = self.service.ensure_subscription(tenant)
                subscription = self.renewal_use_case.execute(
                    tenant,
                    subscription,
                    period_key=period_key,
                    due_this_month=due_this_month,
                )
                subscription = self.restriction_use_case.sync_status(tenant, subscription)
                self.invoicing_use_case.execute(
                    tenant,
                    subscription,
                    next_period_key=next_period_key,
                    next_charge_date=next_charge_date,
                    plan_map=plan_map,
                )
                self.service._sync_tenant_config(tenant, subscription)
            except Exception:
                logger.exception(
                    "Billing due cycle failed for tenant slug=%s", getattr(tenant_row, "slug", None)
                )
