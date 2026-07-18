from __future__ import annotations

from enum import Enum


class TrainingItemStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"
    DELETED = "deleted"


__all__ = ["TrainingItemStatus"]
