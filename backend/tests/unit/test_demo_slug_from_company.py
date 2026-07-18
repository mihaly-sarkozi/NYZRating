from __future__ import annotations

import pytest

from core.modules.tenant.slug.policy import candidate_demo_slug, demo_slug_base, slug_matches_demo_base
from core.modules.tenant.slug.reservation import DemoSlugReserver

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_demo_slug_base_from_company_name() -> None:
    assert demo_slug_base("Példa Szalon Kft.") == "pelda-szalon-kft"
    assert demo_slug_base("Acme 2024!") == "acme-2024"
    assert demo_slug_base("") == "demo"


def test_slug_matches_demo_base() -> None:
    assert slug_matches_demo_base("pelda-kft", "pelda-kft")
    assert slug_matches_demo_base("pelda-kft2", "pelda-kft")
    assert not slug_matches_demo_base("misi", "pelda-kft")
    assert not slug_matches_demo_base("misiszalon", "misi")


def test_candidate_demo_slug_suffix() -> None:
    assert candidate_demo_slug("pelda", 1) == "pelda"
    assert candidate_demo_slug("pelda", 2) == "pelda2"


def test_reserver_replaces_slug_when_company_name_changes() -> None:
    sessions: dict[str, str] = {}

    class FakeTenantRepo:
        def get_by_slug(self, slug: str):
            return None

    class FakeDemoRepo:
        def get_reserved_slug(self, session_id: str) -> str | None:
            return sessions.get(session_id)

        def reserve_slug(self, *, session_id: str, requested_name: str, email: str, tenant_slug: str) -> bool:
            if session_id in sessions:
                return False
            sessions[session_id] = tenant_slug
            return True

        def delete_session(self, session_id: str) -> None:
            sessions.pop(session_id, None)

    reserver = DemoSlugReserver(tenant_repo=FakeTenantRepo(), demo_signup_repository=FakeDemoRepo())
    first = reserver.reserve("s1", "Misi", "a@b.hu")
    assert first == "misi"
    second = reserver.reserve("s1", "Példa Szalon Kft.", "a@b.hu")
    assert second == "pelda-szalon-kft"
