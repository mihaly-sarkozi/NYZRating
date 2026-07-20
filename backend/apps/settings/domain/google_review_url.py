# backend/apps/settings/domain/google_review_url.py
# Feladat: Google vélemény (g.page) link normalizálása és validálása.
# Sárközi Mihály - 2026.07.20

from __future__ import annotations

import re

_GOOGLE_REVIEW_URL_RE = re.compile(
    r"^https://g\.page/r/[A-Za-z0-9_\-]+/review/?$",
    re.IGNORECASE,
)


def normalize_google_review_url(value: str | None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return ""
    return normalized.rstrip("/")


def is_valid_google_review_url(value: str | None) -> bool:
    normalized = normalize_google_review_url(value)
    if not normalized:
        return False
    return bool(_GOOGLE_REVIEW_URL_RE.match(f"{normalized}/"))


__all__ = ["is_valid_google_review_url", "normalize_google_review_url"]
