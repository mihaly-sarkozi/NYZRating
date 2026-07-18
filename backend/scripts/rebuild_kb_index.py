#!/usr/bin/env python3
"""Qdrant KB index rebuild — operátori CLI (backend containerben futtatandó)."""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild KB Qdrant index (Postgres source of truth)",
        epilog="Futtasd a backend containerben, teljes app kontextussal. Lásd docs/ops/backup-restore-qdrant.md",
    )
    parser.add_argument("tenant_slug")
    parser.add_argument("kb_uuid")
    args = parser.parse_args()

    try:
        from apps.kb.kb_indexing.dto.RebuildKnowledgeBaseIndexDtos import RebuildKnowledgeBaseIndexRequestDto
        from apps.kb.kb_indexing.bootstrap.indexing_assembly import build_indexing_services
        from apps.registry import load_app_modules
        from core.kernel.app.app_manifest import AppManifest
        from core.kernel.deps.facade import get_infrastructure_registry
    except ImportError as exc:
        print(f"App bootstrap nem elérhető: {exc}", file=sys.stderr)
        print("Használd: docker compose exec backend python3 scripts/rebuild_kb_index.py <tenant> <kb_uuid>", file=sys.stderr)
        return 2

    infra = get_infrastructure_registry()
    AppManifest.init_app().add_modules(load_app_modules())
    services = build_indexing_services(
        session_factory=infra.db_session_factory,
        chunk_reader=infra.chunk_reader,
        embedding_reader=infra.embedding_reader,
        embedding_job_reader=infra.embedding_job_reader,
        bundle_reader=infra.bundle_reader,
        knowledge_base_reader=infra.knowledge_base_reader,
    )
    result = services.rebuild_kb_index_service.rebuild(
        RebuildKnowledgeBaseIndexRequestDto(
            tenant_slug=args.tenant_slug,
            knowledge_base_id=args.kb_uuid,
        )
    )
    print(result)
    return 0 if result.status in {"COMPLETED", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
