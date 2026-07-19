from __future__ import annotations

import pytest

from core.modules.tenant.signup import orchestrator as orchestrator_module
from core.modules.tenant.signup.errors import DemoSessionRequiredError
from core.modules.tenant.signup.orchestrator_result import DemoSignupResult

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_orchestrator_does_not_pass_extra_kwargs_to_resend_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_resend_kwargs: dict[str, object] = {}
    captured_new_signup_kwargs: dict[str, object] = {}

    class FakeSlugReserver:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeResendUseCase:
        def __init__(self, **kwargs) -> None:
            captured_resend_kwargs.update(kwargs)

    class FakeNewSignupUseCase:
        def __init__(self, **kwargs) -> None:
            captured_new_signup_kwargs.update(kwargs)

    monkeypatch.setattr(orchestrator_module, "DemoSlugReserver", FakeSlugReserver)
    monkeypatch.setattr(orchestrator_module, "DemoSignupResendUseCase", FakeResendUseCase)
    monkeypatch.setattr(orchestrator_module, "DemoNewSignupUseCase", FakeNewSignupUseCase)

    hooks_provider = lambda: ()
    audit_service = object()

    orchestrator_module.TenantSignupOrchestrator(
        tenant_repository=object(),
        user_service=object(),
        provisioning_service=object(),
        demo_signup_repository=object(),
        demo_login_token_service=object(),
        tenant_base_domain="lvh.me",
        clock=object(),
        tenant_signup_hooks_provider=hooks_provider,
        audit_service=audit_service,
    )

    assert "tenant_signup_hooks_provider" not in captured_resend_kwargs
    assert "audit_service" not in captured_resend_kwargs
    assert "tenant_signup_hooks_provider" not in captured_new_signup_kwargs
    assert "audit_service" not in captured_new_signup_kwargs


def test_signup_requires_demo_session_id_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeSlugReserver:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def reserve(self, session_id: str, requested_name: str, email: str) -> str:
            captured["reserved_session_id"] = session_id
            captured["requested_name"] = requested_name
            captured["email"] = email
            return "demo"

    class FakeResendUseCase:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeNewSignupUseCase:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def execute(self, **kwargs):
            captured["new_signup_session_id"] = kwargs["demo_session_id"]
            return DemoSignupResult(
                slug="demo",
                host_hint="demo.lvh.me",
                demo_login_token="token",
                created_new=True,
                resent_existing=False,
            )

    class FakeDemoSignupRepository:
        def is_email_blocked(self, email: str) -> bool:
            return False

        def find_latest_completed_tenant_slug_by_email(self, email: str):
            return None

        def has_active_demo_for_email(self, email: str) -> bool:
            return False

        def find_latest_pending_session_by_email(self, email: str):
            return None

        def cleanup_expired_pending_sessions(self) -> int:
            return 0

        def cleanup_expired_demo_tenants(self) -> int:
            return 0

        def is_slug_reserved(self, slug: str) -> bool:
            return False

    class FakeTenantRepository:
        def get_by_slug(self, slug: str):
            return None

    monkeypatch.setattr(orchestrator_module, "DemoSlugReserver", FakeSlugReserver)
    monkeypatch.setattr(orchestrator_module, "DemoSignupResendUseCase", FakeResendUseCase)
    monkeypatch.setattr(orchestrator_module, "DemoNewSignupUseCase", FakeNewSignupUseCase)

    orchestrator = orchestrator_module.TenantSignupOrchestrator(
        tenant_repository=FakeTenantRepository(),
        user_service=object(),
        provisioning_service=object(),
        demo_signup_repository=FakeDemoSignupRepository(),
        demo_login_token_service=object(),
        tenant_base_domain="lvh.me",
        clock=object(),
    )

    with pytest.raises(DemoSessionRequiredError):
        orchestrator.signup(
            email="demo@example.com",
            kb_name="Demo KB",
            name="Demo User",
            locale="hu",
            resend_existing_access=False,
            demo_session_id=None,
        )


def test_signup_pending_email_auto_resends_without_demo_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    resend_calls: list[dict[str, object]] = []

    class FakeSlugReserver:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeResendUseCase:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeNewSignupUseCase:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def resend_pending_verification(self, **kwargs):
            resend_calls.append(kwargs)
            return DemoSignupResult(
                slug="acme",
                host_hint="acme.lvh.me",
                demo_login_token="",
                created_new=False,
                resent_existing=True,
                awaiting_email_verification=True,
            )

    class FakeDemoSignupRepository:
        def is_email_blocked(self, email: str) -> bool:
            return False

        def find_latest_completed_tenant_slug_by_email(self, email: str):
            return None

        def find_active_demo_tenant_slug_by_email(self, email: str):
            return None

        def has_active_demo_for_email(self, email: str) -> bool:
            return False

        def find_latest_pending_session_by_email(self, email: str):
            return {
                "session_id": "sess-1",
                "email": email,
                "tenant_slug": "acme",
                "verification_expires_at": None,
            }

        def cleanup_expired_pending_sessions(self) -> int:
            return 0

        def cleanup_expired_demo_tenants(self) -> int:
            return 0

    class FakeTenantRepository:
        def get_by_slug(self, slug: str):
            return None

    monkeypatch.setattr(orchestrator_module, "DemoSlugReserver", FakeSlugReserver)
    monkeypatch.setattr(orchestrator_module, "DemoSignupResendUseCase", FakeResendUseCase)
    monkeypatch.setattr(orchestrator_module, "DemoNewSignupUseCase", FakeNewSignupUseCase)
    monkeypatch.setattr(orchestrator_module, "is_test_env", lambda _env: False)
    monkeypatch.setattr(orchestrator_module, "get_app_env", lambda: "production")
    monkeypatch.setattr(
        orchestrator_module,
        "normalize_demo_locale",
        lambda locale: (locale or "hu").strip().lower()[:2] or "hu",
    )

    orchestrator = orchestrator_module.TenantSignupOrchestrator(
        tenant_repository=FakeTenantRepository(),
        user_service=object(),
        provisioning_service=object(),
        demo_signup_repository=FakeDemoSignupRepository(),
        demo_login_token_service=object(),
        tenant_base_domain="lvh.me",
        clock=object(),
    )

    result = orchestrator.signup(
        email="owner@example.com",
        kb_name="Acme",
        name="Owner",
        locale="hu",
        resend_existing_access=False,
        company_name="Acme",
        demo_session_id="sess-new",
    )

    assert result.resent_existing is True
    assert result.awaiting_email_verification is True
    assert len(resend_calls) == 1
    assert resend_calls[0]["email"] == "owner@example.com"
