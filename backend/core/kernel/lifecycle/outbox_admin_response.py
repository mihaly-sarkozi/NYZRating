from __future__ import annotations

from pydantic import BaseModel, Field


class OutboxJobItemResponse(BaseModel):
    id: int
    event_type: str
    status: str
    attempts: int = 0
    last_error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    next_retry_at: str | None = None
    finished_at: str | None = None
    idempotency_key: str | None = None


class OutboxJobListResponse(BaseModel):
    items: list[OutboxJobItemResponse] = Field(default_factory=list)
    status_filter: str | None = None


class OutboxRequeueResponse(BaseModel):
    event_id: int
    requeued: bool
