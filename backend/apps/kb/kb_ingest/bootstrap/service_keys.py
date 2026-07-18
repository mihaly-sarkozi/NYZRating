from __future__ import annotations

# backend/apps/kb/kb_ingest/bootstrap/service_keys.py
# Feladat: Tanítási modul DI service kulcsok.
# Sárközi Mihály - 2026.06.07

from core.kernel.interface.app_keys import module_service_key

KB_INGEST_REPOSITORY = module_service_key("kb", "ingest.repository")
KB_INGEST_POLICY = module_service_key("kb", "ingest.policy")
KB_INGEST_PURGE_REPOSITORY = module_service_key("kb", "ingest.purge_repository")
KB_INGEST_KB_COLLECTION_RESOLVER = module_service_key("kb", "ingest.kb_collection_resolver")

__all__ = [
    "KB_INGEST_KB_COLLECTION_RESOLVER",
    "KB_INGEST_POLICY",
    "KB_INGEST_PURGE_REPOSITORY",
    "KB_INGEST_REPOSITORY",
]
