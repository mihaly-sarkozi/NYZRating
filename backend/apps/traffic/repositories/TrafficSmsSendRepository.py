# backend/apps/traffic/repositories/TrafficSmsSendRepository.py
# Feladat: SMS küldési napló olvasása és írása a public.traffic_sms_sends táblába.
# Sárközi Mihály - 2026.07.18

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any

from sqlalchemy import text


class TrafficSmsSendRepository:
    def __init__(self, session_factory: Callable[[], AbstractContextManager[Any]]) -> None:
        self._session_factory = session_factory

    def list_for_tenant(self, *, tenant_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with self._session_factory() as db:
            db.execute(text("SET search_path TO public"))
            rows = db.execute(
                text(
                    """
                    SELECT id, recipient_name, phone, scheduled_at, status, period_key, created_at
                    FROM public.traffic_sms_sends
                    WHERE tenant_id = :tenant_id
                    ORDER BY created_at DESC, id DESC
                    LIMIT :limit
                    """
                ),
                {"tenant_id": tenant_id, "limit": max(1, min(limit, 500))},
            ).mappings().all()
            return [dict(row) for row in rows]

    def create(
        self,
        *,
        tenant_id: int,
        created_by_user_id: int,
        recipient_name: str,
        phone: str,
        scheduled_at: datetime,
        status: str,
        period_key: str,
    ) -> dict[str, Any]:
        with self._session_factory() as db:
            try:
                db.execute(text("SET search_path TO public"))
                row = db.execute(
                    text(
                        """
                        INSERT INTO public.traffic_sms_sends (
                            tenant_id, created_by_user_id, recipient_name, phone,
                            scheduled_at, status, period_key
                        )
                        VALUES (
                            :tenant_id, :created_by_user_id, :recipient_name, :phone,
                            :scheduled_at, :status, :period_key
                        )
                        RETURNING id, recipient_name, phone, scheduled_at, status, period_key, created_at
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "created_by_user_id": created_by_user_id,
                        "recipient_name": recipient_name,
                        "phone": phone,
                        "scheduled_at": scheduled_at,
                        "status": status,
                        "period_key": period_key,
                    },
                ).mappings().one()
                db.commit()
                return dict(row)
            except Exception:
                db.rollback()
                raise


__all__ = ["TrafficSmsSendRepository"]
