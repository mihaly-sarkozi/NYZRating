# backend/core/modules/tenant/signup/new_demo_signup.py
# Feladat: Új demo tenant signup use case. Email megerősítésig csak pending sessiont tart, a séma/táblák provision a confirm után történik. Tenant onboarding application service.
# Sárközi Mihály - 2026.05.21

"""New-demo-tenant creation use case.

Flow A:
1. ``start_pending`` – slug foglalás után verification emailt küld (nincs provision)
2. ``confirm_and_provision`` – token után provision + set-password link
"""
from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Callable

from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.modules.users.service._user_service_helpers import build_set_password_link, new_invite_token_payload
from core.modules.tenant.context.tenant_context import current_tenant_schema
from core.modules.tenant.slug.policy import demo_host_hint, demo_trial_expires_at
from core.modules.tenant.provisioning.models import TenantProvisioningRequest
from core.modules.tenant.signup.orchestrator_result import DemoConfirmSignupResult, DemoSignupResult
from core.modules.tenant.signup.errors import (
    DemoSignupVerificationExpiredError,
    DemoSignupVerificationInvalidError,
)
from core.kernel.config.config_loader import settings
from core.kernel.runtime.clock import utc_now
from core.modules.tenant.extensions.tenant_hooks import TenantSignupContext, TenantSignupHook, get_tenant_signup_hooks


def _verification_ttl_hours() -> int:
    return max(1, min(72, int(getattr(settings, "demo_signup_verification_ttl_hours", 24) or 24)))


def _install_frontend_base_url() -> str:
    configured = str(getattr(settings, "frontend_base_url", "") or "").strip().rstrip("/")
    if configured:
        return configured
    install_host = str(getattr(settings, "install_host", "") or "").strip().lower()
    if not install_host:
        return ""
    scheme = "https" if getattr(settings, "cookie_secure", False) else "http"
    return f"{scheme}://{install_host}"


def build_confirm_signup_link(raw_token: str) -> str:
    base = _install_frontend_base_url()
    if not base:
        return ""
    return f"{base}/confirm-signup?token={raw_token}"


class DemoNewSignupUseCase:
    """Create a brand-new demo tenant (pending verify → provision)."""

    def __init__(
        self,
        *,
        tenant_repo,
        user_service,
        provisioning_service,
        demo_signup_repository,
        demo_login_token_service,
        tenant_base_domain: str,
        clock,
        tenant_signup_hooks_provider: Callable[[], tuple[TenantSignupHook, ...]] = get_tenant_signup_hooks,
        audit_service=None,
    ) -> None:
        self._tenant_repo = tenant_repo
        self._user_service = user_service
        self._provisioning_service = provisioning_service
        self._demo_signup_repo = demo_signup_repository
        self._demo_login_tokens = demo_login_token_service
        self._tenant_base_domain = tenant_base_domain
        self._clock = clock
        self._tenant_signup_hooks_provider = tenant_signup_hooks_provider
        self._audit = audit_service

    def _tenant_frontend_base_url(self, tenant_slug: str) -> str:
        from core.modules.tenant.helpers.tenant_frontend_url_helper import tenant_frontend_base_url_by_slug

        return tenant_frontend_base_url_by_slug(tenant_slug)

    def _send_confirm_signup_email(
        self,
        *,
        email: str,
        tenant_slug: str,
        preferred_locale: str,
        raw_token: str,
    ) -> None:
        link = build_confirm_signup_link(raw_token)
        email_service = getattr(self._user_service, "email_service", None)
        if email_service and link and hasattr(email_service, "send_demo_confirm_signup"):
            email_service.send_demo_confirm_signup(
                email,
                link,
                tenant_slug=tenant_slug,
                lang=preferred_locale,
            )

    def _send_demo_set_password_email(
        self,
        *,
        tenant_slug: str,
        user_id: int,
        email: str,
        demo_expires_at,
        preferred_locale: str,
    ) -> str:
        invite_repo = self._user_service.invite_token_repo
        if invite_repo is None:
            raise RuntimeError("InviteTokenRepository is not configured")
        invite_payload = new_invite_token_payload()
        tenant_ctx = current_tenant_schema.set(tenant_slug)
        try:
            invite_repo.invalidate_all_for_user(user_id, updated_by=user_id)
            invite_repo.create(
                user_id,
                invite_payload.token_hash,
                invite_payload.expires_at,
                created_by=user_id,
                updated_by=user_id,
            )
        finally:
            current_tenant_schema.reset(tenant_ctx)

        set_password_link = build_set_password_link(self._tenant_frontend_base_url(tenant_slug), invite_payload.raw_token)
        if self._user_service.email_service and set_password_link:
            self._user_service.email_service.send_demo_set_password_invite(
                email,
                set_password_link,
                demo_expires_at=demo_expires_at,
                lang=preferred_locale,
            )
        return set_password_link or ""

    def _load_tenant_owner(self, *, tenant_slug: str, email: str, preferred_locale: str):
        tenant_ctx = current_tenant_schema.set(tenant_slug)
        try:
            tenant_owner = self._user_service.user_repository.get_by_email(email)
            if tenant_owner is not None and tenant_owner.id is not None:
                if getattr(tenant_owner, "preferred_locale", None) != preferred_locale:
                    self._user_service.user_repository.update(
                        tenant_owner.with_updates(preferred_locale=preferred_locale),
                        updated_by=tenant_owner.id,
                    )
                tenant_owner = self._user_service.user_repository.get_by_id(tenant_owner.id)
            return tenant_owner
        finally:
            current_tenant_schema.reset(tenant_ctx)

    def start_pending(
        self,
        *,
        slug: str,
        email: str,
        owner_name: str,
        tenant_name: str,
        preferred_locale: str,
        plan_code: str,
        subscription_period: str,
        demo_session_id: str,
    ) -> DemoSignupResult:
        """Slug foglalva; megerősítő email, provision nélkül."""
        primary_domain = demo_host_hint(slug, self._tenant_base_domain)
        invite_payload = new_invite_token_payload()
        # Újrahasználjuk a token generátort, de a TTL a verification setting.
        expires_at = utc_now() + timedelta(hours=_verification_ttl_hours())
        try:
            self._demo_signup_repo.save_pending_verification(
                session_id=demo_session_id,
                verification_token_hash=invite_payload.token_hash,
                verification_expires_at=expires_at,
                owner_name=owner_name,
                tenant_name=tenant_name,
                preferred_locale=preferred_locale,
                plan_code=plan_code,
                subscription_period=subscription_period,
            )
            self._send_confirm_signup_email(
                email=email,
                tenant_slug=slug,
                preferred_locale=preferred_locale,
                raw_token=invite_payload.raw_token,
            )
            return DemoSignupResult(
                slug=slug,
                host_hint=primary_domain,
                demo_login_token="",
                created_new=True,
                resent_existing=False,
                awaiting_email_verification=True,
            )
        except Exception:
            self._demo_signup_repo.delete_session(demo_session_id)
            raise

    def resend_pending_verification(self, *, email: str, preferred_locale: str | None = None) -> DemoSignupResult:
        pending = self._demo_signup_repo.find_latest_pending_session_by_email(email)
        if not pending:
            raise DemoSignupVerificationInvalidError()
        expires_at = pending.get("verification_expires_at")
        if expires_at is not None and expires_at <= utc_now():
            self._demo_signup_repo.delete_session(str(pending["session_id"]))
            raise DemoSignupVerificationExpiredError()

        slug = str(pending["tenant_slug"])
        locale = (preferred_locale or pending.get("preferred_locale") or "hu").strip().lower()[:2] or "hu"
        invite_payload = new_invite_token_payload()
        new_expires = utc_now() + timedelta(hours=_verification_ttl_hours())
        self._demo_signup_repo.save_pending_verification(
            session_id=str(pending["session_id"]),
            verification_token_hash=invite_payload.token_hash,
            verification_expires_at=new_expires,
            owner_name=str(pending.get("owner_name") or pending.get("requested_name") or slug),
            tenant_name=str(pending.get("tenant_name") or pending.get("requested_name") or slug),
            preferred_locale=locale,
            plan_code=str(pending.get("plan_code") or "free"),
            subscription_period=str(pending.get("subscription_period") or "monthly"),
        )
        self._send_confirm_signup_email(
            email=str(pending["email"]),
            tenant_slug=slug,
            preferred_locale=locale,
            raw_token=invite_payload.raw_token,
        )
        return DemoSignupResult(
            slug=slug,
            host_hint=demo_host_hint(slug, self._tenant_base_domain),
            demo_login_token="",
            created_new=False,
            resent_existing=True,
            awaiting_email_verification=True,
        )

    def confirm_and_provision(self, *, token: str) -> DemoConfirmSignupResult:
        raw = (token or "").strip()
        if not raw:
            raise DemoSignupVerificationInvalidError()
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        pending = self._demo_signup_repo.get_pending_by_verification_token_hash(token_hash)
        if not pending or pending.get("completed_at") is not None:
            raise DemoSignupVerificationInvalidError()

        expires_at = pending.get("verification_expires_at")
        if expires_at is not None and expires_at <= utc_now():
            self._demo_signup_repo.delete_session(str(pending["session_id"]))
            raise DemoSignupVerificationExpiredError()

        slug = str(pending["tenant_slug"])
        email = str(pending["email"]).strip().lower()
        owner_name = str(pending.get("owner_name") or pending.get("requested_name") or slug)
        tenant_name = str(pending.get("tenant_name") or pending.get("requested_name") or slug)
        preferred_locale = str(pending.get("preferred_locale") or "hu").strip().lower()[:2] or "hu"
        plan_code = str(pending.get("plan_code") or "free").strip().lower() or "free"
        subscription_period = str(pending.get("subscription_period") or "monthly").strip().lower() or "monthly"
        demo_session_id = str(pending["session_id"])
        primary_domain = demo_host_hint(slug, self._tenant_base_domain)

        trial_days = max(1, int(getattr(settings, "demo_trial_days", 7) or 7))
        demo_expires_at = demo_trial_expires_at(self._clock.now(), days=trial_days)

        self._demo_signup_repo.mark_session_verified(demo_session_id)

        try:
            if self._tenant_repo.get_by_slug(slug) is None:
                self._provisioning_service.provision(
                    TenantProvisioningRequest(
                        slug=slug,
                        tenant_name=tenant_name,
                        owner_email=email,
                        owner_name=owner_name or None,
                        primary_domain=primary_domain,
                        package=plan_code,
                        feature_flags={
                            "demo_mode": True,
                            "demo_expires_at": demo_expires_at.isoformat(),
                        },
                        limits={},
                        owner_send_invite_email=False,
                        owner_activate_immediately=True,
                    )
                )

            tenant = self._tenant_repo.get_by_slug(slug)
            tenant_owner = self._load_tenant_owner(
                tenant_slug=slug,
                email=email,
                preferred_locale=preferred_locale,
            )
            if tenant_owner is None or tenant_owner.id is None:
                raise RuntimeError("demo_owner_missing_after_signup")

            signup_context = TenantSignupContext(
                tenant_slug=slug,
                tenant_name=tenant_name,
                tenant_id=getattr(tenant, "id", None),
                owner_id=tenant_owner.id,
                owner_email=email,
                locale=preferred_locale,
                plan_code=plan_code,
                subscription_period=subscription_period,
                demo_session_id=demo_session_id,
                is_new_tenant=True,
            )
            tenant_ctx = current_tenant_schema.set(slug)
            try:
                for hook in self._tenant_signup_hooks_provider():
                    hook.handle(signup_context)
            finally:
                current_tenant_schema.reset(tenant_ctx)

            set_password_url = self._send_demo_set_password_email(
                tenant_slug=slug,
                user_id=tenant_owner.id,
                email=email,
                demo_expires_at=demo_expires_at,
                preferred_locale=preferred_locale,
            )
            self._demo_signup_repo.mark_session_completed(demo_session_id)
            if self._audit:
                self._audit.log(
                    AuditLogAction.TENANT_PROVISIONED,
                    user_id=tenant_owner.id,
                    details={
                        "tenant_slug": slug,
                        "tenant_name": tenant_name,
                        "plan_code": plan_code,
                        "subscription_period": subscription_period,
                    },
                    target_type="tenant",
                    target_id=slug,
                )
            return DemoConfirmSignupResult(
                slug=slug,
                host_hint=primary_domain,
                set_password_url=set_password_url,
                email=email,
            )
        except Exception:
            if self._tenant_repo.get_by_slug(slug) is None:
                # Ne töröljük a sessiont véglegesen confirm retry-hoz — csak ha nincs tenant.
                pass
            raise

    def execute(
        self,
        *,
        slug: str,
        email: str,
        owner_name: str,
        tenant_name: str,
        preferred_locale: str,
        plan_code: str,
        subscription_period: str,
        demo_session_id: str,
    ) -> DemoSignupResult:
        """Legacy azonnali provision (ha email verification ki van kapcsolva)."""
        trial_days = max(1, int(getattr(settings, "demo_trial_days", 7) or 7))
        demo_expires_at = demo_trial_expires_at(self._clock.now(), days=trial_days)
        primary_domain = demo_host_hint(slug, self._tenant_base_domain)

        try:
            if self._tenant_repo.get_by_slug(slug) is None:
                self._provisioning_service.provision(
                    TenantProvisioningRequest(
                        slug=slug,
                        tenant_name=tenant_name,
                        owner_email=email,
                        owner_name=owner_name or None,
                        primary_domain=primary_domain,
                        package=plan_code,
                        feature_flags={
                            "demo_mode": True,
                            "demo_expires_at": demo_expires_at.isoformat(),
                        },
                        limits={},
                        owner_send_invite_email=False,
                        owner_activate_immediately=True,
                    )
                )

            tenant = self._tenant_repo.get_by_slug(slug)

            tenant_owner = self._load_tenant_owner(
                tenant_slug=slug,
                email=email,
                preferred_locale=preferred_locale,
            )
            if tenant_owner is None or tenant_owner.id is None:
                raise RuntimeError("demo_owner_missing_after_signup")

            signup_context = TenantSignupContext(
                tenant_slug=slug,
                tenant_name=tenant_name,
                tenant_id=getattr(tenant, "id", None),
                owner_id=tenant_owner.id,
                owner_email=email,
                locale=preferred_locale,
                plan_code=plan_code,
                subscription_period=subscription_period,
                demo_session_id=demo_session_id,
                is_new_tenant=tenant is None,
            )
            tenant_ctx = current_tenant_schema.set(slug)
            try:
                for hook in self._tenant_signup_hooks_provider():
                    hook.handle(signup_context)
            finally:
                current_tenant_schema.reset(tenant_ctx)

            self._send_demo_set_password_email(
                tenant_slug=slug,
                user_id=tenant_owner.id,
                email=email,
                demo_expires_at=demo_expires_at,
                preferred_locale=preferred_locale,
            )
            self._demo_signup_repo.mark_session_completed(demo_session_id)
            if self._audit:
                self._audit.log(
                    AuditLogAction.TENANT_PROVISIONED,
                    user_id=tenant_owner.id,
                    details={
                        "tenant_slug": slug,
                        "tenant_name": tenant_name,
                        "plan_code": plan_code,
                        "subscription_period": subscription_period,
                    },
                    target_type="tenant",
                    target_id=slug,
                )
            return DemoSignupResult(
                slug=slug,
                host_hint=primary_domain,
                demo_login_token="",
                created_new=True,
                resent_existing=False,
                awaiting_email_verification=False,
            )
        except Exception:
            if self._tenant_repo.get_by_slug(slug) is None:
                self._demo_signup_repo.delete_session(demo_session_id)
            raise


__all__ = ["DemoNewSignupUseCase", "build_confirm_signup_link"]
