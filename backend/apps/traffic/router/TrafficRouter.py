# backend/apps/traffic/router/TrafficRouter.py
# Feladat: Traffic overview és SMS küldési napló FastAPI route-jai.
# Sárközi Mihály - 2026.05.24

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from apps.traffic.bootstrap.dependencies import get_traffic_service
from apps.traffic.schemas.TrafficOverviewResponse import TrafficOverviewResponse
from apps.traffic.schemas.TrafficSmsSendSchemas import (
    TrafficSmsSendCreateRequest,
    TrafficSmsSendCreateResponse,
    TrafficSmsSendListResponse,
)
from core.kernel.http.tenant_dependencies import RequestTenantContext, require_tenant_context
from core.kernel.security.rate_limit import limiter
from core.modules.auth.web.dependencies.auth_dependencies import require_permission
from core.modules.users.domain.dto import User


router = APIRouter()


def _require_owner_or_admin(user: User) -> None:
    """A forgalom oldal csak owner/admin szerepkörnek látható, user szerepkörnek nem."""

    if str(user.role or "").strip().lower() not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Traffic overview requires owner or admin role")


@router.get("/traffic/overview", response_model=TrafficOverviewResponse)
@limiter.limit("30/minute")
def get_traffic_overview(
    request: Request,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    svc: Any = Depends(get_traffic_service),
    current_user: User = Depends(require_permission("traffic.read")),
) -> TrafficOverviewResponse:
    """Visszaadja a tenant aktuális forgalmi overview-ját frontend kirajzoláshoz."""

    _require_owner_or_admin(current_user)
    return svc.get_overview(tenant)


@router.get("/traffic/sms-sends", response_model=TrafficSmsSendListResponse)
@limiter.limit("30/minute")
def list_traffic_sms_sends(
    request: Request,
    tenant: RequestTenantContext = Depends(require_tenant_context),
    svc: Any = Depends(get_traffic_service),
    current_user: User = Depends(require_permission("traffic.read")),
) -> TrafficSmsSendListResponse:
    _require_owner_or_admin(current_user)
    return svc.list_sms_sends(tenant)


@router.post("/traffic/sms-sends", response_model=TrafficSmsSendCreateResponse)
@limiter.limit("20/minute")
def create_traffic_sms_send(
    request: Request,
    body: TrafficSmsSendCreateRequest = Body(...),
    tenant: RequestTenantContext = Depends(require_tenant_context),
    svc: Any = Depends(get_traffic_service),
    current_user: User = Depends(require_permission("traffic.write")),
) -> TrafficSmsSendCreateResponse:
    _require_owner_or_admin(current_user)
    return svc.create_sms_send(tenant, user_id=int(current_user.id), payload=body)


__all__ = ["router"]
