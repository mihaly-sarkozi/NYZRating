# backend/apps/settings/service/tenant_reset_service.py
# Feladat: Tenant teljes adattisztítása — schema újraépítés, owner belépés megőrzése.
# Megjegyzés: a billing/kb-specifikus lépések eltávolítva, mert azok az app modulok
# (apps.billing, apps.kb) nem részei az alaprendszernek. Ha egy konkrét app ezekre
# épít, a saját reset-hook-ját a kernel lifecycle/event rendszerén keresztül kell
# bekötnie, nem itt.
# Sárközi Mihály - 2026.06.12

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from core.kernel.runtime.clock import utc_now
from core.modules.auth.models.user_authenticator_orm import UserAuthenticatorORM
from core.modules.tenant.cache import invalidate_tenant_cache
from core.modules.tenant.context.tenant_context import current_tenant_schema
from core.modules.tenant.repositories.tenant_repository import TenantRepository
from core.modules.tenant.schema.service import drop_tenant_schema, upgrade_tenant_schema
from core.modules.users.models.user_orm import UserORM
from shared.object_storage.service import get_object_storage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TenantResetResult:
    status: str
    message: str
    tenant_slug: str
    owner_user_id: int


class TenantResetService:
    def __init__(self, session_factory: Callable[[], AbstractContextManager[Any]]) -> None:
        self._sf = session_factory
        self._tenant_repo = TenantRepository(session_factory)

    def _get_engine(self) -> Engine:
        engine = getattr(self._sf, "engine", None)
        if engine is None:
            raise RuntimeError("tenant_reset_engine_unavailable")
        return engine

    def reset_tenant(
        self,
        *,
        tenant_id: int,
        tenant_slug: str,
        owner_user_id: int,
        confirm_slug: str,
    ) -> TenantResetResult:
        normalized_slug = (tenant_slug or "").strip().lower()
        normalized_confirm = (confirm_slug or "").strip().lower()
        if not normalized_slug or normalized_confirm != normalized_slug:
            raise ValueError("A megerősítő slug nem egyezik a tenant azonosítóval.")

        owner_snapshot, authenticator_snapshot = self._snapshot_owner_auth(
            slug=normalized_slug,
            owner_user_id=owner_user_id,
        )
        self._purge_public_tenant_data(tenant_id)
        self._purge_object_storage(normalized_slug)

        engine = self._get_engine()
        drop_tenant_schema(engine, normalized_slug)
        upgrade_tenant_schema(engine, normalized_slug)

        self._restore_owner(
            slug=normalized_slug,
            owner=owner_snapshot,
            authenticator=authenticator_snapshot,
        )
        self._reset_config(tenant_id=tenant_id, slug=normalized_slug, owner_user_id=owner_user_id)
        invalidate_tenant_cache(normalized_slug)

        return TenantResetResult(
            status="reset",
            message="A tenant adatai alaphelyzetbe álltak. A tulajdonos belépési adatai változatlanok.",
            tenant_slug=normalized_slug,
            owner_user_id=owner_user_id,
        )

    def _snapshot_owner_auth(
        self,
        *,
        slug: str,
        owner_user_id: int,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        token = current_tenant_schema.set(slug)
        try:
            with self._sf() as db:
                owner = (
                    db.query(UserORM)
                    .filter(UserORM.id == owner_user_id, UserORM.role == "owner", UserORM.deleted_at.is_(None))
                    .first()
                )
                if owner is None:
                    raise ValueError("Csak a tenant tulajdonosa indíthat resetet.")
                owner_snapshot = {
                    column.name: getattr(owner, column.name)
                    for column in UserORM.__table__.columns
                }
                authenticator = (
                    db.query(UserAuthenticatorORM)
                    .filter(UserAuthenticatorORM.user_id == owner_user_id, UserAuthenticatorORM.is_enabled.is_(True))
                    .first()
                )
                authenticator_snapshot = None
                if authenticator is not None and authenticator.secret_base32:
                    authenticator_snapshot = {
                        column.name: getattr(authenticator, column.name)
                        for column in UserAuthenticatorORM.__table__.columns
                    }
                return owner_snapshot, authenticator_snapshot
        finally:
            current_tenant_schema.reset(token)

    def _restore_owner(
        self,
        *,
        slug: str,
        owner: dict[str, Any],
        authenticator: dict[str, Any] | None,
    ) -> None:
        token = current_tenant_schema.set(slug)
        try:
            with self._sf() as db:
                restored = UserORM(**owner)
                db.add(restored)
                db.flush()
                if authenticator is not None:
                    auth_row = UserAuthenticatorORM(**{**authenticator, "user_id": restored.id})
                    db.add(auth_row)
                db.commit()
        finally:
            current_tenant_schema.reset(token)

    def _purge_public_tenant_data(self, tenant_id: int) -> None:
        statements = [
            "DELETE FROM public.tenant_cancellation_requests WHERE tenant_id = :tenant_id",
            "DELETE FROM public.tenant_domains WHERE tenant_id = :tenant_id",
            """
            DELETE FROM public.platform_event_outbox
            WHERE COALESCE(payload->'_meta'->>'tenant_id', payload->>'tenant_id', '') = :tenant_id_text
               OR COALESCE(payload->'_meta'->>'tenant_slug', payload->>'tenant_slug', '') = :tenant_slug
            """,
        ]
        with self._sf() as db:
            db.execute(text("SET search_path TO public"))
            tenant = self._tenant_repo.get_by_id(tenant_id)
            tenant_slug = getattr(tenant, "slug", "") if tenant is not None else ""
            for stmt in statements:
                try:
                    db.execute(
                        text(stmt),
                        {
                            "tenant_id": tenant_id,
                            "tenant_id_text": str(tenant_id),
                            "tenant_slug": tenant_slug,
                        },
                    )
                except Exception:
                    logger.exception("tenant_reset_public_purge_failed", extra={"tenant_id": tenant_id, "stmt": stmt[:80]})
            db.commit()

    def _reset_config(self, *, tenant_id: int, slug: str, owner_user_id: int) -> None:
        utc_now()  # helyben tartva, ha egy konkrét app időbélyeget akar a confighoz kötni
        self._tenant_repo.create_config(
            tenant_id,
            slug=slug,
            package="free",
            feature_flags={},
            limits={},
            created_by=owner_user_id,
        )

    def _purge_object_storage(self, tenant_slug: str) -> None:
        prefix = f"tenants/{tenant_slug}/"
        try:
            storage = get_object_storage()
            client = getattr(storage, "_client", None)
            bucket = getattr(getattr(storage, "_config", None), "bucket", None)
            if client is None or not bucket:
                return
            continuation: str | None = None
            while True:
                kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
                if continuation:
                    kwargs["ContinuationToken"] = continuation
                response = client.list_objects_v2(**kwargs)
                contents = response.get("Contents") or []
                if not contents:
                    break
                delete_keys = [{"Key": item["Key"]} for item in contents if item.get("Key")]
                if delete_keys:
                    client.delete_objects(Bucket=bucket, Delete={"Objects": delete_keys, "Quiet": True})
                if not response.get("IsTruncated"):
                    break
                continuation = response.get("NextContinuationToken")
        except Exception:
            logger.exception("tenant_reset_object_storage_purge_failed", extra={"tenant_slug": tenant_slug})


__all__ = ["TenantResetResult", "TenantResetService"]
