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
    review_url = "https://g.page/r/AbCdEf123/review"

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

        def get_email_blocklist_entry(self, email: str):
            return None

        def find_latest_completed_tenant_slug_by_email(self, email: str):
            return None

        def find_active_demo_tenant_slug_by_email(self, email: str):
            return None

        def has_active_demo_for_email(self, email: str) -> bool:
            return False

        def find_latest_completed_by_google_review_url(self, google_review_url: str):
            return None

        def find_latest_pending_by_google_review_url(self, google_review_url: str):
            return {
                "session_id": "sess-1",
                "email": "owner@example.com",
                "tenant_slug": "acme",
                "google_review_url": review_url,
                "verification_expires_at": None,
            }

        def find_latest_pending_session_by_email(self, email: str):
            return {
                "session_id": "sess-1",
                "email": email,
                "tenant_slug": "acme",
                "google_review_url": review_url,
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
        google_review_url=review_url,
    )

    assert result.resent_existing is True
    assert result.awaiting_email_verification is True
    assert len(resend_calls) == 1
    assert resend_calls[0]["email"] == "owner@example.com"


def test_signup_same_email_different_business_creates_new(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    new_review = "https://g.page/r/NewStore99/review"

    class FakeSlugReserver:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def reserve(self, session_id: str, requested_name: str, email: str) -> str:
            return "uj-bolt"

    class FakeResendUseCase:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def execute(self, **kwargs):
            raise AssertionError("resend must not run for a different business")

    class FakeNewSignupUseCase:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def start_pending(self, **kwargs):
            captured.update(kwargs)
            return DemoSignupResult(
                slug="uj-bolt",
                host_hint="uj-bolt.lvh.me",
                demo_login_token="",
                created_new=True,
                resent_existing=False,
                awaiting_email_verification=True,
            )

    class FakeDemoSignupRepository:
        def is_email_blocked(self, email: str) -> bool:
            return False

        def get_email_blocklist_entry(self, email: str):
            return None

        def find_latest_completed_tenant_slug_by_email(self, email: str):
            return "regi-bolt"

        def find_active_demo_tenant_slug_by_email(self, email: str):
            return "regi-bolt"

        def find_latest_completed_by_google_review_url(self, google_review_url: str):
            return None

        def find_latest_pending_by_google_review_url(self, google_review_url: str):
            return None

        def find_latest_pending_session_by_email(self, email: str):
            return {
                "email": email,
                "tenant_slug": "regi-bolt",
                "google_review_url": "https://g.page/r/OldStore11/review",
            }

        def count_completed_signups_for_email(self, email: str) -> int:
            return 1

        def cleanup_expired_pending_sessions(self) -> int:
            return 0

        def cleanup_expired_demo_tenants(self) -> int:
            return 0

    class FakeTenantRepository:
        def get_by_slug(self, slug: str):
            return type("T", (), {"is_active": True, "slug": slug})()

    class FakeClock:
        def now(self):
            import datetime

            return datetime.datetime.now(datetime.timezone.utc)

    monkeypatch.setattr(orchestrator_module, "DemoSlugReserver", FakeSlugReserver)
    monkeypatch.setattr(orchestrator_module, "DemoSignupResendUseCase", FakeResendUseCase)
    monkeypatch.setattr(orchestrator_module, "DemoNewSignupUseCase", FakeNewSignupUseCase)
    monkeypatch.setattr(orchestrator_module, "is_test_env", lambda _env: False)
    monkeypatch.setattr(orchestrator_module, "get_app_env", lambda: "production")
    monkeypatch.setattr(orchestrator_module, "is_demo_signup_enabled", lambda **kwargs: True)
    monkeypatch.setattr(orchestrator_module, "bump_daily_counter", lambda **kwargs: 1)
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
        clock=FakeClock(),
    )

    result = orchestrator.signup(
        email="owner@example.com",
        kb_name="Új bolt",
        name="Owner",
        locale="hu",
        company_name="Új bolt",
        demo_session_id="sess-new",
        google_review_url=new_review,
    )

    assert result.created_new is True
    assert captured["google_review_url"] == new_review
    assert captured["slug"] == "uj-bolt"


def test_signup_same_business_raises_reconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.modules.tenant.signup.errors import BusinessAlreadyExistsError

    review_url = "https://g.page/r/SameStore42/review"

    class FakeSlugReserver:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeResendUseCase:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeNewSignupUseCase:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeDemoSignupRepository:
        def is_email_blocked(self, email: str) -> bool:
            return False

        def get_email_blocklist_entry(self, email: str):
            return None

        def find_latest_completed_by_google_review_url(self, google_review_url: str):
            return {
                "tenant_slug": "pelda-kft",
                "email": "other@example.com",
                "google_review_url": review_url,
            }

        def find_latest_pending_by_google_review_url(self, google_review_url: str):
            return None

        def find_latest_pending_session_by_email(self, email: str):
            return None

        def cleanup_expired_pending_sessions(self) -> int:
            return 0

        def cleanup_expired_demo_tenants(self) -> int:
            return 0

    class FakeTenantRepository:
        def get_by_slug(self, slug: str):
            return type("T", (), {"is_active": False, "slug": slug})()

    monkeypatch.setattr(orchestrator_module, "DemoSlugReserver", FakeSlugReserver)
    monkeypatch.setattr(orchestrator_module, "DemoSignupResendUseCase", FakeResendUseCase)
    monkeypatch.setattr(orchestrator_module, "DemoNewSignupUseCase", FakeNewSignupUseCase)
    monkeypatch.setattr(
        orchestrator_module,
        "normalize_demo_locale",
        lambda locale: (locale or "hu").strip().lower()[:2] or "hu",
    )
    monkeypatch.setattr(
        orchestrator_module,
        "tenant_frontend_base_url_by_slug",
        lambda slug: f"https://{slug}.nyzrating.com",
    )

    orchestrator = orchestrator_module.TenantSignupOrchestrator(
        tenant_repository=FakeTenantRepository(),
        user_service=object(),
        provisioning_service=object(),
        demo_signup_repository=FakeDemoSignupRepository(),
        demo_login_token_service=object(),
        tenant_base_domain="nyzrating.com",
        clock=object(),
    )

    with pytest.raises(BusinessAlreadyExistsError) as exc_info:
        orchestrator.signup(
            email="new@example.com",
            kb_name="Példa",
            name="New",
            locale="hu",
            company_name="Példa Kft.",
            demo_session_id="sess-1",
            google_review_url=review_url,
        )

    err = exc_info.value
    assert err.tenant_slug == "pelda-kft"
    assert err.is_active is False
    assert "/login?" in err.login_url
    assert "redirect=%2Fadmin%2Fpricing" in err.login_url
