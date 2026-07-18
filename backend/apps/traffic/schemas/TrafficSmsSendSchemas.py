# backend/apps/traffic/schemas/TrafficSmsSendSchemas.py
# Feladat: SMS küldés request/response DTO-k a traffic oldalhoz.
# Sárközi Mihály - 2026.07.18

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TrafficSmsSendCreateRequest(BaseModel):
    recipient_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=1, max_length=32)
    scheduled_at: datetime


class TrafficSmsSendItemResponse(BaseModel):
    id: int
    recipient_name: str
    phone: str
    scheduled_at: datetime
    status: str
    period_key: str
    created_at: datetime


class TrafficSmsSendCreateResponse(BaseModel):
    item: TrafficSmsSendItemResponse
    remaining_total: int
    available_total: int
    used_total: int


class TrafficSmsSendListResponse(BaseModel):
    items: list[TrafficSmsSendItemResponse]
    remaining_total: int
    available_total: int
    used_total: int


__all__ = [
    "TrafficSmsSendCreateRequest",
    "TrafficSmsSendCreateResponse",
    "TrafficSmsSendItemResponse",
    "TrafficSmsSendListResponse",
]
