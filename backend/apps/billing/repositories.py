# backend/apps/billing/repositories.py
# Feladat: A billing app public schema repository rétege. DML-only adat-hozzáférési adapterként seedeli a catalogot, kezeli az előfizetéseket, usage számlálókat, számlákat, debug state-et és aktív tenant listázást; a táblák/indexek létrehozása public schema migrációban történik. Program-specifikus perzisztencia adapter.
# Sárközi Mihály - 2026.05.22

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date, datetime
from typing import Any

from sqlalchemy import text

from apps.billing.models import (
    BillingCatalogEntryORM,
    BillingDebugStateORM,
    BillingInvoiceORM,
    BillingPaymentEventORM,
    BillingQuestionUsageORM,
    BillingSubscriptionORM,
    BillingTrainingUsageORM,
    TenantCancellationRequestORM,
    _utcnow,
)
from core.modules.tenant.models.tenant_orm import TenantORM


class BillingRepository:
    def __init__(self, session_factory: Callable[[], AbstractContextManager[Any]]):
        self._sf = session_factory

    def ensure_storage(self) -> None:
        # Runtime repositoryk nem végezhetnek DDL-t. A billing public táblák és indexek
        # a core.modules.tenant.schema.public migrációs/bootstrap lépésben jönnek létre.
        return None

    def seed_catalog(self, rows: list[dict[str, Any]]) -> None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            for row in rows:
                existing = (
                    db.query(BillingCatalogEntryORM)
                    .filter(
                        BillingCatalogEntryORM.entry_type == row["entry_type"],
                        BillingCatalogEntryORM.code == row["code"],
                    )
                    .first()
                )
                if existing is None:
                    db.add(BillingCatalogEntryORM(**row))
                else:
                    existing.name = row["name"]
                    existing.currency = row["currency"]
                    existing.price_cents = row["price_cents"]
                    existing.included = row.get("included") or {}
                    existing.metadata_json = row.get("metadata_json") or {}
                    existing.is_active = bool(row.get("is_active", True))
                    existing.updated_at = _utcnow()
            db.commit()

    def get_debug_simulated_date(self) -> date | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = db.query(BillingDebugStateORM).first()
            return row.simulated_date if row is not None else None

    def get_debug_payment_simulation_outcome(self) -> str:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = db.query(BillingDebugStateORM).first()
            if row is None:
                return "success"
            outcome = str(getattr(row, "payment_simulation_outcome", None) or "success").strip().lower()
            return outcome if outcome in {"success", "failed"} else "success"

    def set_debug_simulated_date(self, value: date | None) -> None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = db.query(BillingDebugStateORM).first()
            if row is None:
                db.add(BillingDebugStateORM(id=1, simulated_date=value, payment_simulation_outcome="success"))
            else:
                row.simulated_date = value
                row.updated_at = _utcnow()
            db.commit()

    def set_debug_payment_simulation_outcome(self, outcome: str) -> None:
        normalized = str(outcome or "").strip().lower()
        if normalized not in {"success", "failed"}:
            raise ValueError("payment_simulation_outcome must be success or failed")
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = db.query(BillingDebugStateORM).first()
            if row is None:
                db.add(BillingDebugStateORM(id=1, simulated_date=None, payment_simulation_outcome=normalized))
            else:
                row.payment_simulation_outcome = normalized
                row.updated_at = _utcnow()
            db.commit()

    def list_catalog(self) -> list[BillingCatalogEntryORM]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(BillingCatalogEntryORM)
                .filter(BillingCatalogEntryORM.is_active.is_(True))
                .order_by(BillingCatalogEntryORM.entry_type.asc(), BillingCatalogEntryORM.price_cents.asc())
                .all()
            )

    def get_subscription(self, tenant_id: int) -> BillingSubscriptionORM | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return db.query(BillingSubscriptionORM).filter(BillingSubscriptionORM.tenant_id == tenant_id).first()

    def create_cancellation_request(
        self,
        *,
        tenant_id: int,
        tenant_slug: str,
        requested_by_user_id: int | None,
        reason_code: str,
        reason_text: str,
        active_kb_count: int,
        status: str,
        effective_at: datetime | None,
        deactivated_at: datetime | None,
    ) -> TenantCancellationRequestORM:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = TenantCancellationRequestORM(
                tenant_id=tenant_id,
                tenant_slug=tenant_slug,
                requested_by_user_id=requested_by_user_id,
                reason_code=reason_code,
                reason_text=reason_text,
                active_kb_count=max(0, int(active_kb_count or 0)),
                status=status,
                effective_at=effective_at,
                deactivated_at=deactivated_at,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row

    def get_latest_cancellation_request(self, tenant_id: int) -> TenantCancellationRequestORM | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(TenantCancellationRequestORM)
                .filter(TenantCancellationRequestORM.tenant_id == tenant_id)
                .order_by(TenantCancellationRequestORM.requested_at.desc(), TenantCancellationRequestORM.id.desc())
                .first()
            )

    def list_cancellation_requests_for_lifecycle(self) -> list[TenantCancellationRequestORM]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(TenantCancellationRequestORM)
                .filter(
                    TenantCancellationRequestORM.status == "deactivation_requested",
                    TenantCancellationRequestORM.cleanup_completed_at.is_(None),
                )
                .order_by(TenantCancellationRequestORM.requested_at.asc(), TenantCancellationRequestORM.id.asc())
                .all()
            )

    def mark_cancellation_notice_two_days_sent(self, request_id: int, sent_at: datetime) -> bool:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            result = db.execute(
                text(
                    """
                    UPDATE public.tenant_cancellation_requests
                    SET notice_two_days_sent_at = :sent_at,
                        updated_at = NOW()
                    WHERE id = :request_id
                      AND notice_two_days_sent_at IS NULL
                    """
                ),
                {"request_id": int(request_id), "sent_at": sent_at},
            )
            db.commit()
            return int(result.rowcount or 0) > 0

    def mark_cancellation_notice_one_day_sent(self, request_id: int, sent_at: datetime) -> bool:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            result = db.execute(
                text(
                    """
                    UPDATE public.tenant_cancellation_requests
                    SET notice_one_day_sent_at = :sent_at,
                        updated_at = NOW()
                    WHERE id = :request_id
                      AND notice_one_day_sent_at IS NULL
                    """
                ),
                {"request_id": int(request_id), "sent_at": sent_at},
            )
            db.commit()
            return int(result.rowcount or 0) > 0

    def mark_cancellation_notice_expired_sent(self, request_id: int, sent_at: datetime) -> bool:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            result = db.execute(
                text(
                    """
                    UPDATE public.tenant_cancellation_requests
                    SET notice_expired_sent_at = :sent_at,
                        updated_at = NOW()
                    WHERE id = :request_id
                      AND notice_expired_sent_at IS NULL
                    """
                ),
                {"request_id": int(request_id), "sent_at": sent_at},
            )
            db.commit()
            return int(result.rowcount or 0) > 0

    def mark_cancellation_deactivated(self, request_id: int, deactivated_at: datetime) -> bool:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            result = db.execute(
                text(
                    """
                    UPDATE public.tenant_cancellation_requests
                    SET deactivated_at = :deactivated_at,
                        updated_at = NOW()
                    WHERE id = :request_id
                      AND deactivated_at IS NULL
                    """
                ),
                {"request_id": int(request_id), "deactivated_at": deactivated_at},
            )
            db.commit()
            return int(result.rowcount or 0) > 0

    def mark_cancellation_cleanup_completed(self, request_id: int, completed_at: datetime) -> bool:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            result = db.execute(
                text(
                    """
                    UPDATE public.tenant_cancellation_requests
                    SET cleanup_completed_at = :completed_at,
                        updated_at = NOW()
                    WHERE id = :request_id
                      AND cleanup_completed_at IS NULL
                    """
                ),
                {"request_id": int(request_id), "completed_at": completed_at},
            )
            db.commit()
            return int(result.rowcount or 0) > 0

    def restore_latest_cancellation_request(self, tenant_id: int, restored_at: datetime) -> bool:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            latest_id = db.execute(
                text(
                    """
                    SELECT id
                    FROM public.tenant_cancellation_requests
                    WHERE tenant_id = :tenant_id
                      AND status = 'deactivation_requested'
                    ORDER BY requested_at DESC, id DESC
                    LIMIT 1
                    """
                ),
                {"tenant_id": int(tenant_id)},
            ).scalar_one_or_none()
            if latest_id is None:
                return False
            result = db.execute(
                text(
                    """
                    UPDATE public.tenant_cancellation_requests
                    SET status = 'renewal_restored',
                        cleanup_completed_at = :restored_at,
                        updated_at = NOW()
                    WHERE id = :request_id
                      AND deactivated_at IS NULL
                    """
                ),
                {"request_id": int(latest_id), "restored_at": restored_at},
            )
            db.commit()
            return int(result.rowcount or 0) > 0

    def hard_delete_tenant(self, tenant_id: int) -> bool:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            result = db.execute(text("DELETE FROM public.tenants WHERE id = :tenant_id"), {"tenant_id": int(tenant_id)})
            db.commit()
            return int(result.rowcount or 0) > 0

    def upsert_subscription(
        self,
        tenant_id: int,
        *,
        plan_code: str,
        billing_period: str,
        status: str,
        trial_started_at: datetime | None,
        trial_ends_at: datetime | None,
        extra_kb_count: int = 0,
        extra_storage_gb: int = 0,
        carryover_addon_questions: int = 0,
        carryover_training_chars: int = 0,
        scheduled_plan_code: str | None = None,
        scheduled_billing_period: str | None = None,
        scheduled_change_effective_period: str | None = None,
        question_warning_period_key: str | None = None,
        question_warning_level: int = 0,
    ) -> BillingSubscriptionORM:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = db.query(BillingSubscriptionORM).filter(BillingSubscriptionORM.tenant_id == tenant_id).first()
            if row is None:
                row = BillingSubscriptionORM(
                    tenant_id=tenant_id,
                    plan_code=plan_code,
                    billing_period=billing_period,
                    status=status,
                    trial_started_at=trial_started_at,
                    trial_ends_at=trial_ends_at,
                    extra_kb_count=extra_kb_count,
                    extra_storage_gb=extra_storage_gb,
                    carryover_addon_questions=carryover_addon_questions,
                    carryover_training_chars=carryover_training_chars,
                    scheduled_plan_code=scheduled_plan_code,
                    scheduled_billing_period=scheduled_billing_period,
                    scheduled_change_effective_period=scheduled_change_effective_period,
                    question_warning_period_key=question_warning_period_key,
                    question_warning_level=question_warning_level,
                )
                db.add(row)
            else:
                row.plan_code = plan_code
                row.billing_period = billing_period
                row.status = status
                row.trial_started_at = trial_started_at
                row.trial_ends_at = trial_ends_at
                row.extra_kb_count = extra_kb_count
                row.extra_storage_gb = extra_storage_gb
                row.carryover_addon_questions = carryover_addon_questions
                row.carryover_training_chars = carryover_training_chars
                row.scheduled_plan_code = scheduled_plan_code
                row.scheduled_billing_period = scheduled_billing_period
                row.scheduled_change_effective_period = scheduled_change_effective_period
                row.question_warning_period_key = question_warning_period_key
                row.question_warning_level = question_warning_level
                row.updated_at = _utcnow()
            db.commit()
            db.refresh(row)
            return row

    def upsert_question_usage(self, tenant_id: int, user_id: int, period_key: str, increment: int = 1) -> BillingQuestionUsageORM:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = (
                db.query(BillingQuestionUsageORM)
                .filter(
                    BillingQuestionUsageORM.tenant_id == tenant_id,
                    BillingQuestionUsageORM.user_id == user_id,
                    BillingQuestionUsageORM.period_key == period_key,
                )
                .first()
            )
            if row is None:
                row = BillingQuestionUsageORM(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    period_key=period_key,
                    question_count=max(0, int(increment)),
                    last_question_at=_utcnow(),
                )
                db.add(row)
            else:
                row.question_count = int(row.question_count or 0) + max(0, int(increment))
                row.last_question_at = _utcnow()
                row.updated_at = _utcnow()
            db.commit()
            db.refresh(row)
            return row

    def list_question_usage(self, tenant_id: int, period_key: str) -> list[BillingQuestionUsageORM]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(BillingQuestionUsageORM)
                .filter(
                    BillingQuestionUsageORM.tenant_id == tenant_id,
                    BillingQuestionUsageORM.period_key == period_key,
                )
                .order_by(BillingQuestionUsageORM.question_count.desc(), BillingQuestionUsageORM.user_id.asc())
                .all()
            )

    def get_training_usage(self, tenant_id: int, period_key: str) -> BillingTrainingUsageORM | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(BillingTrainingUsageORM)
                .filter(
                    BillingTrainingUsageORM.tenant_id == tenant_id,
                    BillingTrainingUsageORM.period_key == period_key,
                )
                .first()
            )

    def increment_training_usage(
        self,
        tenant_id: int,
        period_key: str,
        *,
        trained_chars: int = 0,
        storage_bytes: int = 0,
    ) -> BillingTrainingUsageORM:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = (
                db.query(BillingTrainingUsageORM)
                .filter(
                    BillingTrainingUsageORM.tenant_id == tenant_id,
                    BillingTrainingUsageORM.period_key == period_key,
                )
                .first()
            )
            d_chars = max(0, int(trained_chars))
            d_bytes = max(0, int(storage_bytes))
            if row is None:
                row = BillingTrainingUsageORM(
                    tenant_id=tenant_id,
                    period_key=period_key,
                    trained_chars=d_chars,
                    storage_bytes=d_bytes,
                )
                db.add(row)
            else:
                row.trained_chars = int(row.trained_chars or 0) + d_chars
                row.storage_bytes = int(row.storage_bytes or 0) + d_bytes
            db.commit()
            db.refresh(row)
            return row

    def create_invoice(
        self,
        tenant_id: int,
        *,
        invoice_type: str,
        period_key: str,
        currency: str,
        total_cents: int,
        description: str,
        lines: list[dict[str, Any]],
        due_at: datetime,
        status: str = "simulated_paid",
        payment_method: str = "simulated_card",
        issued_at: datetime | None = None,
    ) -> BillingInvoiceORM:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = BillingInvoiceORM(
                tenant_id=tenant_id,
                invoice_type=invoice_type,
                period_key=period_key,
                currency=currency,
                total_cents=total_cents,
                description=description,
                lines=lines,
                due_at=due_at,
                status=status,
                payment_method=payment_method,
                issued_at=issued_at or _utcnow(),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row

    def get_invoice(self, tenant_id: int, invoice_type: str, period_key: str) -> BillingInvoiceORM | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(BillingInvoiceORM)
                .filter(
                    BillingInvoiceORM.tenant_id == tenant_id,
                    BillingInvoiceORM.invoice_type == invoice_type,
                    BillingInvoiceORM.period_key == period_key,
                )
                .first()
            )

    def get_invoice_by_id(self, tenant_id: int, invoice_id: int) -> BillingInvoiceORM | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(BillingInvoiceORM)
                .filter(BillingInvoiceORM.tenant_id == tenant_id, BillingInvoiceORM.id == int(invoice_id))
                .first()
            )

    def list_recent_invoices(self, tenant_id: int, limit: int = 500) -> list[BillingInvoiceORM]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(BillingInvoiceORM)
                .filter(BillingInvoiceORM.tenant_id == tenant_id)
                .order_by(BillingInvoiceORM.issued_at.desc())
                .limit(limit)
                .all()
            )

    def list_training_addon_invoices(self, tenant_id: int) -> list[BillingInvoiceORM]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(BillingInvoiceORM)
                .filter(
                    BillingInvoiceORM.tenant_id == tenant_id,
                    BillingInvoiceORM.invoice_type.in_(
                        ("addon:training_initial_500k", "addon:training_extra_500k")
                    ),
                    BillingInvoiceORM.status.in_(("simulated_paid", "paid")),
                )
                .all()
            )

    def get_latest_invoice_for_type(self, tenant_id: int, invoice_type: str) -> BillingInvoiceORM | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(BillingInvoiceORM)
                .filter(
                    BillingInvoiceORM.tenant_id == tenant_id,
                    BillingInvoiceORM.invoice_type == invoice_type,
                )
                .order_by(BillingInvoiceORM.issued_at.desc())
                .first()
            )

    def get_latest_open_subscription_invoice(self, tenant_id: int) -> BillingInvoiceORM | None:
        """Legutóbbi kiegyenlítetlen havi díjbekérő (status=issued)."""
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return (
                db.query(BillingInvoiceORM)
                .filter(
                    BillingInvoiceORM.tenant_id == tenant_id,
                    BillingInvoiceORM.invoice_type == "monthly_subscription",
                    BillingInvoiceORM.status == "issued",
                )
                .order_by(BillingInvoiceORM.issued_at.desc())
                .first()
            )

    def update_invoice_payment_status(
        self,
        invoice_id: int,
        *,
        status: str,
        payment_method: str | None = None,
        invoice_type: str | None = None,
        lines: list[dict[str, Any]] | None = None,
    ) -> BillingInvoiceORM | None:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = db.query(BillingInvoiceORM).filter(BillingInvoiceORM.id == int(invoice_id)).first()
            if row is None:
                return None
            row.status = status
            if payment_method is not None:
                row.payment_method = payment_method
            if invoice_type is not None:
                row.invoice_type = invoice_type
            if lines is not None:
                row.lines = lines
            db.commit()
            db.refresh(row)
            return row

    def get_latest_unpaid_debt_invoice(self, tenant_id: int) -> BillingInvoiceORM | None:
        """Legutóbbi kiegyenlítetlen tartozás: issued díjbekérő vagy payment_failed."""
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            open_issued = (
                db.query(BillingInvoiceORM)
                .filter(
                    BillingInvoiceORM.tenant_id == tenant_id,
                    BillingInvoiceORM.invoice_type == "monthly_subscription",
                    BillingInvoiceORM.status == "issued",
                )
                .order_by(BillingInvoiceORM.issued_at.desc())
                .first()
            )
            failed = (
                db.query(BillingInvoiceORM)
                .filter(
                    BillingInvoiceORM.tenant_id == tenant_id,
                    BillingInvoiceORM.status == "payment_failed",
                    BillingInvoiceORM.invoice_type.in_(("monthly_subscription", "monthly_subscription_failed")),
                )
                .order_by(BillingInvoiceORM.issued_at.desc())
                .first()
            )
            if open_issued is None:
                return failed
            if failed is None:
                return open_issued
            try:
                return open_issued if open_issued.issued_at >= failed.issued_at else failed
            except TypeError:
                a = open_issued.issued_at.replace(tzinfo=None) if open_issued.issued_at else None
                b = failed.issued_at.replace(tzinfo=None) if failed.issued_at else None
                if a is None:
                    return failed
                if b is None:
                    return open_issued
                return open_issued if a >= b else failed

    def record_payment_event_once(
        self,
        *,
        provider: str,
        event_id: str,
        event_type: str,
        tenant_id: int | None,
        payload: dict[str, Any],
    ) -> tuple[BillingPaymentEventORM, bool]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            row = (
                db.query(BillingPaymentEventORM)
                .filter(
                    BillingPaymentEventORM.provider == provider,
                    BillingPaymentEventORM.event_id == event_id,
                )
                .first()
            )
            if row is not None:
                return row, False
            row = BillingPaymentEventORM(
                provider=provider,
                event_id=event_id,
                event_type=event_type,
                tenant_id=tenant_id,
                payload=payload,
                status="processed",
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row, True

    def list_active_tenants(self) -> list[TenantORM]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return db.query(TenantORM).filter(TenantORM.is_active.is_(True)).all()

    def list_all_tenants(self) -> list[TenantORM]:
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            return db.query(TenantORM).all()
