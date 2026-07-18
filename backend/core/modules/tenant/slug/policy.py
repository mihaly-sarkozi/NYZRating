# backend/core/modules/tenant/slug/policy.py
# Feladat: Demo tenant slug és locale policy helper függvények. Normalizálja és validálja a slugot, locale-t és domain formátumot a demo signup folyamat előtt. Tenant slug policy réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta

SUPPORTED_DEMO_LOCALES = {"hu", "en", "es"}


def demo_slug_base(raw_name: str) -> str:
    """Cégnévből tenant slug alap: ékezetmentes, kisbetűs, szóhatárok kötőjellel."""
    normalized = unicodedata.normalize("NFKD", raw_name or "")
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    hyphenated = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
    hyphenated = re.sub(r"-{2,}", "-", hyphenated)
    return (hyphenated or "demo")[:48]


def slug_matches_demo_base(slug: str, base: str) -> bool:
    """True, ha a slug a base vagy base+szám (pl. pelda-kft, pelda-kft2)."""
    normalized_slug = (slug or "").strip().lower()
    normalized_base = (base or "").strip().lower()
    if not normalized_slug or not normalized_base:
        return False
    if normalized_slug == normalized_base:
        return True
    if not normalized_slug.startswith(normalized_base):
        return False
    suffix = normalized_slug[len(normalized_base) :]
    return bool(suffix) and suffix.isdigit()


def candidate_demo_slug(base: str, suffix: int) -> str:
    if suffix <= 1:
        return base[:64]
    suffix_text = str(suffix)
    return f"{base[:64 - len(suffix_text)]}{suffix_text}"


def normalize_demo_locale(locale: str | None) -> str:
    normalized = (locale or "").strip().lower()
    return normalized if normalized in SUPPORTED_DEMO_LOCALES else "hu"


def initial_demo_knowledge_base_name(locale: str) -> str:
    names = {
        "hu": "Teszt NYZRating",
        "en": "Test knowledge base",
        "es": "Base de conocimiento de prueba",
    }
    return names.get(locale, names["hu"])


def demo_trial_expires_at(now: datetime, *, days: int) -> datetime:
    return now + timedelta(days=days)


def demo_host_hint(slug: str, tenant_base_domain: str) -> str:
    return f"{slug}.{tenant_base_domain}"
