# backend/tests/unit/test_platform_admin_tenant_lifecycle.py
# Feladat: Platform admin tenant inaktiválás / végleges törlés confirm flow unit tesztek.

from __future__ import annotations

import pytest

from admin.service.platform_admin_service import PlatformAdminService

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _Repo:
    def __init__(self) -> None:
        self.deactivated: list[int] = []
        self.deleted: list[int] = []
        self.tenants = {
            1: {"id": 1, "slug": "acme", "name": "Acme Kft.", "is_active": True},
            2: {"id": 2, "slug": "beta", "name": "Beta Bt.", "is_active": False},
        }

    def platform_tenant_statistics_detail(self, tenant_id: int):
        tenant = self.tenants.get(int(tenant_id))
        if tenant is None:
            return None
        return {"tenant": dict(tenant)}

    def deactivate_active_tenant(self, tenant_id: int, *, updated_by: int | None = None):
        tenant = self.tenants.get(int(tenant_id))
        if tenant is None:
            return None
        if not tenant["is_active"]:
            raise ValueError("tenant_already_inactive")
        tenant["is_active"] = False
        self.deactivated.append(int(tenant_id))
        return dict(tenant)

    def permanently_delete_cancelled_tenant(self, tenant_id: int, *, deleted_by: int | None = None):
        tenant = self.tenants.get(int(tenant_id))
        if tenant is None:
            return None
        if tenant["is_active"]:
            raise ValueError("tenant_must_be_inactive")
        self.deleted.append(int(tenant_id))
        deleted = dict(tenant)
        del self.tenants[int(tenant_id)]
        return deleted


def test_deactivate_requires_exact_name_confirmation() -> None:
    service = PlatformAdminService.__new__(PlatformAdminService)
    service.repository = _Repo()  # type: ignore[attr-defined]

    with pytest.raises(ValueError, match="tenant_confirmation_mismatch"):
        service.deactivate_active_tenant(1, confirm_name="Rossz név", admin_user_id=9)


def test_deactivate_active_tenant_with_matching_name() -> None:
    repo = _Repo()
    service = PlatformAdminService.__new__(PlatformAdminService)
    service.repository = repo  # type: ignore[attr-defined]

    result = service.deactivate_active_tenant(1, confirm_name="Acme Kft.", admin_user_id=9)

    assert result["is_active"] is False
    assert repo.deactivated == [1]


def test_permanent_delete_inactive_tenant_with_matching_name() -> None:
    repo = _Repo()
    service = PlatformAdminService.__new__(PlatformAdminService)
    service.repository = repo  # type: ignore[attr-defined]

    result = service.permanently_delete_cancelled_tenant(2, confirm_name="Beta Bt.", admin_user_id=9)

    assert result["slug"] == "beta"
    assert repo.deleted == [2]
    assert 2 not in repo.tenants
