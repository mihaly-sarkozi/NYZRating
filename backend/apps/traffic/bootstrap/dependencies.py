# backend/apps/traffic/bootstrap/dependencies.py
# Feladat: FastAPI dependency a traffic service module.* kulcson keresztüli eléréséhez.
# Sárközi Mihály - 2026.07.18

from __future__ import annotations

from fastapi import Request

from apps.traffic.bootstrap.service_keys import TRAFFIC_SERVICE
from core.kernel.http.app_dependencies import get_module_service


def get_traffic_service(request: Request):
    return get_module_service(TRAFFIC_SERVICE, request)


__all__ = ["get_traffic_service"]
