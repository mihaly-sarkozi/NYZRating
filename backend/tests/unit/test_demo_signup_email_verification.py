from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core.modules.tenant.signup.errors import (
    DemoSignupVerificationExpiredError,
    DemoSignupVerificationInvalidError,
)
from core.modules.tenant.signup.new_demo_signup import DemoNewSignupUseCase

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _FakeClock:
    def now(self):
        return datetime.now(timezone.utc)


class _FakeInviteRepo:
    def invalidate_all_for_user(self, user_id: int, *, updated_by=None) -> None:
        return None

    def create(self, user_id, token_hash, expires_at, *, created_by=None, updated_by=None) -> None:
        return None


class _FakeUserRepo:
    def __init__(self) -> None:
        self.user = SimpleNamespace(
            id=1,
            email="owner@example.com",
            preferred_locale="hu",
            with_updates=lambda **kwargs: SimpleNamespace(
                id=1,
                email="owner@example.com",
                preferred_locale=kwargs.get("preferred_locale", "hu"),
            ),
        )

    def get_by_email(self, email: str):
        return self.user

    def get_by_id(self, user_id: int):
        return self.user

    def update(self, user, *, updated_by=None):
        return user


class _FakeEmail:
    def __init__(self) -> None:
        self.confirm_links: list[str] = []
        self.set_password_links: list[str] = []

    def send_demo_confirm_signup(self, to_email, link, *, tenant_slug, lang=None):
        self.confirm_links.append(link)
        return True

    def send_demo_set_password_invite(self, to_email, link, *, demo_expires_at, lang=None):
        self.set_password_links.append(link)
        return True


class _FakeDemoRepo:
    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}

    def save_pending_verification(self, **kwargs):
        sid = kwargs["session_id"]
        existing = self.sessions.get(
            sid,
            {"session_id": sid, "email": "owner@example.com", "tenant_slug": "acme"},
        )
        existing.update(kwargs)
        existing["completed_at"] = None
        existing["verified_at"] = None
        self.sessions[sid] = existing

    def get_pending_by_verification_token_hash(self, token_hash: str):
        for row in self.sessions.values():
            if row.get("verification_token_hash") == token_hash:
                return dict(row)
        return None

    def mark_session_verified(self, session_id: str) -> None:
        self.sessions[session_id]["verified_at"] = datetime.now(timezone.utc)

    def mark_session_completed(self, session_id: str) -> None:
        self.sessions[session_id]["completed_at"] = datetime.now(timezone.utc)

    def delete_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)


class _FakeTenantRepo:
    def __init__(self) -> None:
        self.tenant = None

    def get_by_slug(self, slug: str):
        return self.tenant


class _FakeProvisioning:
    def __init__(self, tenant_repo: _FakeTenantRepo) -> None:
        self.tenant_repo = tenant_repo
        self.calls = 0

    def provision(self, request) -> None:
        self.calls += 1
        self.tenant_repo.tenant = SimpleNamespace(id=9, slug=request.slug)


def _patch_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = SimpleNamespace(
        demo_trial_days=7,
        demo_signup_verification_ttl_hours=24,
        frontend_base_url="https://www.example.com",
        install_host="www.example.com",
        cookie_secure=True,
        frontend_set_password_path="/set-password",
        tenant_base_domain="example.com",
        invite_ttl_hours=4,
        frontend_set_password_port=None,
    )
    monkeypatch.setattr("core.modules.tenant.signup.new_demo_signup.settings", cfg, raising=False)
    monkeypatch.setattr("core.kernel.config.config_loader.settings", cfg, raising=False)
    monkeypatch.setattr("core.modules.users.service._user_service_helpers.settings", cfg, raising=False)
    monkeypatch.setattr("core.modules.tenant.helpers.tenant_frontend_url_helper.settings", cfg, raising=False)


def test_start_pending_does_not_provision(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch)
    tenant_repo = _FakeTenantRepo()
    provisioning = _FakeProvisioning(tenant_repo)
    demo_repo = _FakeDemoRepo()
    email = _FakeEmail()
    user_service = SimpleNamespace(
        email_service=email,
        invite_token_repo=_FakeInviteRepo(),
        user_repository=_FakeUserRepo(),
    )
    uc = DemoNewSignupUseCase(
        tenant_repo=tenant_repo,
        user_service=user_service,
        provisioning_service=provisioning,
        demo_signup_repository=demo_repo,
        demo_login_token_service=object(),
        tenant_base_domain="example.com",
        clock=_FakeClock(),
        tenant_signup_hooks_provider=lambda: (),
    )
    result = uc.start_pending(
        slug="acme",
        email="owner@example.com",
        owner_name="Owner",
        tenant_name="Acme",
        preferred_locale="hu",
        plan_code="free",
        subscription_period="monthly",
        demo_session_id="sess-1",
    )
    assert result.awaiting_email_verification is True
    assert provisioning.calls == 0
    assert email.confirm_links
    assert "confirm-signup?token=" in email.confirm_links[-1]


def test_confirm_and_provision_creates_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch)
    tenant_repo = _FakeTenantRepo()
    provisioning = _FakeProvisioning(tenant_repo)
    demo_repo = _FakeDemoRepo()
    email = _FakeEmail()
    user_service = SimpleNamespace(
        email_service=email,
        invite_token_repo=_FakeInviteRepo(),
        user_repository=_FakeUserRepo(),
    )
    uc = DemoNewSignupUseCase(
        tenant_repo=tenant_repo,
        user_service=user_service,
        provisioning_service=provisioning,
        demo_signup_repository=demo_repo,
        demo_login_token_service=object(),
        tenant_base_domain="example.com",
        clock=_FakeClock(),
        tenant_signup_hooks_provider=lambda: (),
    )
    pending = uc.start_pending(
        slug="acme",
        email="owner@example.com",
        owner_name="Owner",
        tenant_name="Acme",
        preferred_locale="hu",
        plan_code="free",
        subscription_period="monthly",
        demo_session_id="sess-1",
    )
    assert pending.awaiting_email_verification
    raw_token = email.confirm_links[-1].split("token=")[-1]
    confirmed = uc.confirm_and_provision(token=raw_token)
    assert provisioning.calls == 1
    assert confirmed.slug == "acme"
    assert "/set-password?token=" in confirmed.set_password_url
    assert demo_repo.sessions["sess-1"]["completed_at"] is not None


def test_confirm_idempotent_reissues_set_password(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch)
    tenant_repo = _FakeTenantRepo()
    provisioning = _FakeProvisioning(tenant_repo)
    demo_repo = _FakeDemoRepo()
    email = _FakeEmail()
    user_service = SimpleNamespace(
        email_service=email,
        invite_token_repo=_FakeInviteRepo(),
        user_repository=_FakeUserRepo(),
    )
    uc = DemoNewSignupUseCase(
        tenant_repo=tenant_repo,
        user_service=user_service,
        provisioning_service=provisioning,
        demo_signup_repository=demo_repo,
        demo_login_token_service=object(),
        tenant_base_domain="example.com",
        clock=_FakeClock(),
        tenant_signup_hooks_provider=lambda: (),
    )
    uc.start_pending(
        slug="acme",
        email="owner@example.com",
        owner_name="Owner",
        tenant_name="Acme",
        preferred_locale="hu",
        plan_code="free",
        subscription_period="monthly",
        demo_session_id="sess-1",
    )
    raw_token = email.confirm_links[-1].split("token=")[-1]
    first = uc.confirm_and_provision(token=raw_token)
    second = uc.confirm_and_provision(token=raw_token)
    assert provisioning.calls == 1
    assert "/set-password?token=" in first.set_password_url
    assert "/set-password?token=" in second.set_password_url
    assert second.set_password_url != first.set_password_url


def test_confirm_invalid_token_raises() -> None:
    uc = DemoNewSignupUseCase(
        tenant_repo=_FakeTenantRepo(),
        user_service=SimpleNamespace(
            email_service=_FakeEmail(),
            invite_token_repo=_FakeInviteRepo(),
            user_repository=_FakeUserRepo(),
        ),
        provisioning_service=_FakeProvisioning(_FakeTenantRepo()),
        demo_signup_repository=_FakeDemoRepo(),
        demo_login_token_service=object(),
        tenant_base_domain="example.com",
        clock=_FakeClock(),
        tenant_signup_hooks_provider=lambda: (),
    )
    with pytest.raises(DemoSignupVerificationInvalidError):
        uc.confirm_and_provision(token="bad-token")


def test_confirm_expired_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    demo_repo = _FakeDemoRepo()
    demo_repo.sessions["sess-1"] = {
        "session_id": "sess-1",
        "email": "owner@example.com",
        "tenant_slug": "acme",
        "owner_name": "Owner",
        "tenant_name": "Acme",
        "preferred_locale": "hu",
        "plan_code": "free",
        "subscription_period": "monthly",
        "verification_token_hash": "abc",
        "verification_expires_at": datetime.now(timezone.utc) - timedelta(hours=1),
        "completed_at": None,
        "verified_at": None,
    }
    monkeypatch.setattr(
        "core.modules.tenant.signup.new_demo_signup.hashlib.sha256",
        lambda raw: SimpleNamespace(hexdigest=lambda: "abc"),
    )
    uc = DemoNewSignupUseCase(
        tenant_repo=_FakeTenantRepo(),
        user_service=SimpleNamespace(
            email_service=_FakeEmail(),
            invite_token_repo=_FakeInviteRepo(),
            user_repository=_FakeUserRepo(),
        ),
        provisioning_service=_FakeProvisioning(_FakeTenantRepo()),
        demo_signup_repository=demo_repo,
        demo_login_token_service=object(),
        tenant_base_domain="example.com",
        clock=_FakeClock(),
        tenant_signup_hooks_provider=lambda: (),
    )
    with pytest.raises(DemoSignupVerificationExpiredError):
        uc.confirm_and_provision(token="any")
