#!/usr/bin/env python3
# backend/scripts/reset_dev_database.py
# Feladat: Fejlesztői DB reset — minden tenant séma törlése, public táblák ürítése, public séma újrainicializálása.
# Sárközi Mihály - 2026.07.18

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
os.chdir(_project_root)

from dotenv import load_dotenv

for candidate in (_project_root / ".env", _project_root.parent / ".env"):
    if candidate.exists():
        load_dotenv(candidate)
        break

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from apps.billing.catalog import default_catalog_rows
from apps.registry import load_app_modules
from core.kernel.app.app_manifest import AppManifest
from core.kernel.config.config_loader import settings
from core.modules.tenant.schema.service import (
    register_manifest_tenant_schema_hooks,
    upgrade_public_schema,
)

PROTECTED_SCHEMAS = {
    "public",
    "information_schema",
    "pg_catalog",
    "pg_toast",
}


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _list_droppable_schemas(conn) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT nspname
            FROM pg_namespace
            WHERE nspname NOT LIKE 'pg_%'
              AND nspname <> ALL(:protected)
            ORDER BY nspname
            """
        ),
        {"protected": list(PROTECTED_SCHEMAS)},
    ).fetchall()
    return [str(row[0]) for row in rows]


def _list_public_tables(conn) -> list[str]:
    rows = conn.execute(
        text(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
            """
        )
    ).fetchall()
    return [str(row[0]) for row in rows]


def _seed_billing_catalog(conn) -> int:
    exists = conn.execute(text("SELECT to_regclass('public.billing_catalog_entries')")).scalar()
    if not exists:
        return 0
    inserted = 0
    for row in default_catalog_rows():
        conn.execute(
            text(
                """
                INSERT INTO public.billing_catalog_entries
                    (entry_type, code, name, currency, price_cents, included, metadata, is_active)
                VALUES
                    (:entry_type, :code, :name, :currency, :price_cents,
                     CAST(:included AS jsonb), CAST(:metadata_json AS jsonb), :is_active)
                ON CONFLICT (entry_type, code) DO UPDATE SET
                    name = EXCLUDED.name,
                    currency = EXCLUDED.currency,
                    price_cents = EXCLUDED.price_cents,
                    included = EXCLUDED.included,
                    metadata = EXCLUDED.metadata,
                    is_active = EXCLUDED.is_active,
                    updated_at = NOW()
                """
            ),
            {
                "entry_type": row["entry_type"],
                "code": row["code"],
                "name": row["name"],
                "currency": row.get("currency") or "HUF",
                "price_cents": int(row.get("price_cents") or 0),
                "included": json.dumps(row.get("included") or {}),
                "metadata_json": json.dumps(row.get("metadata_json") or {}),
                "is_active": bool(row.get("is_active", True)),
            },
        )
        inserted += 1
    return inserted


def main() -> None:
    url = settings.database_url
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql":
        raise SystemExit(f"Csak PostgreSQL támogatott (kapott: {parsed.get_backend_name()})")

    print(f"DB: {parsed.host}:{parsed.port}/{parsed.database}")
    engine = create_engine(url, future=True)

    with engine.begin() as conn:
        tenants_table = conn.execute(text("SELECT to_regclass('public.tenants')")).scalar()
        tenant_slugs: list[str] = []
        if tenants_table:
            tenant_slugs = [str(r[0]) for r in conn.execute(text("SELECT slug FROM public.tenants")).fetchall()]

        schemas = set(_list_droppable_schemas(conn))
        for slug in tenant_slugs:
            if slug and slug not in PROTECTED_SCHEMAS:
                schemas.add(slug)

        ordered = sorted(schemas)
        print(f"Tenant sémák törlése ({len(ordered)}): {', '.join(ordered) or '—'}")
        for schema in ordered:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {_quote_ident(schema)} CASCADE"))
            print(f"  DROP SCHEMA {schema}")

        tables = _list_public_tables(conn)
        print(f"Public táblák ürítése ({len(tables)})")
        if tables:
            qualified = ", ".join(f"public.{_quote_ident(name)}" for name in tables)
            conn.execute(text(f"TRUNCATE TABLE {qualified} RESTART IDENTITY CASCADE"))
            print("  TRUNCATE public.* RESTART IDENTITY CASCADE")

    print("Public séma migrációk / struktúra újraalkalmazása…")
    register_manifest_tenant_schema_hooks(AppManifest.init_app().add_modules(load_app_modules()))
    upgrade_public_schema(engine)

    with engine.begin() as conn:
        seeded = _seed_billing_catalog(conn)
        print(f"Billing catalog seed: {seeded} sor")

        tenants_left = 0
        if conn.execute(text("SELECT to_regclass('public.tenants')")).scalar():
            tenants_left = int(conn.execute(text("SELECT COUNT(*) FROM public.tenants")).scalar() or 0)
        schemas_left = _list_droppable_schemas(conn)
        print(f"Kész. public.tenants={tenants_left}, extra sémák={schemas_left or []}")

    engine.dispose()


if __name__ == "__main__":
    main()
