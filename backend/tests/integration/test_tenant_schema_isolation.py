"""
Tenant search_path izoláció integrációs teszt.

Bizonyítja, hogy A tenant kérése nem olvashatja B tenant tábláit,
még akkor sem, ha ugyanazt a pool-kapcsolatot kapják egymás után.

Futtatáshoz: Postgres szükséges (SQLite-on skip).
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from core.kernel.config.config_loader import settings
from core.kernel.db.session import make_session_factory
from core.modules.tenant.context.tenant_context import current_tenant_schema

pytestmark = pytest.mark.integration

TENANT_A = "tenant_isolation_test_a"
TENANT_B = "tenant_isolation_test_b"


@pytest.fixture(scope="module")
def pg_factory():
    dsn = getattr(settings, "database_url", "") or ""
    if "sqlite" in dsn or not dsn or "postgresql" not in dsn.split(":")[0].lower():
        pytest.skip("Postgres szükséges a search_path izolációs teszthez")
    return make_session_factory(dsn, pool_pre_ping=False)


@pytest.fixture(scope="module", autouse=True)
def setup_schemas(pg_factory):
    with pg_factory.transaction() as db:
        for slug in (TENANT_A, TENANT_B):
            db.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{slug}"'))
            db.execute(
                text(
                    f'CREATE TABLE IF NOT EXISTS "{slug}".sentinel '
                    f"(owner TEXT NOT NULL)"
                )
            )
            db.execute(text(f'DELETE FROM "{slug}".sentinel'))
            db.execute(text(f"INSERT INTO \"{slug}\".sentinel VALUES ('{slug}')"))
    yield
    with pg_factory.transaction() as db:
        for slug in (TENANT_A, TENANT_B):
            db.execute(text(f'DROP SCHEMA IF EXISTS "{slug}" CASCADE'))


def _read_sentinel(factory, schema: str) -> str:
    token = current_tenant_schema.set(schema)
    try:
        with factory.transaction() as db:
            row = db.execute(text("SELECT owner FROM sentinel LIMIT 1")).fetchone()
            return row[0] if row else ""
    finally:
        current_tenant_schema.reset(token)


def test_tenant_a_reads_own_data(pg_factory):
    assert _read_sentinel(pg_factory, TENANT_A) == TENANT_A


def test_tenant_b_reads_own_data(pg_factory):
    assert _read_sentinel(pg_factory, TENANT_B) == TENANT_B


def test_a_cannot_read_b_after_sequential_requests(pg_factory):
    result_a = _read_sentinel(pg_factory, TENANT_A)
    assert result_a == TENANT_A

    result_b = _read_sentinel(pg_factory, TENANT_B)
    assert result_b == TENANT_B, (
        f"Tenant izoláció megtört: B tenant '{result_b}'-t olvasott "
        f"'{TENANT_B}' helyett. Ez search_path pool-szivárgás."
    )


def test_no_cross_tenant_table_visibility(pg_factory):
    token = current_tenant_schema.set(TENANT_B)
    try:
        with pg_factory.transaction() as db:
            rows = db.execute(
                text(f"SELECT owner FROM sentinel WHERE owner = '{TENANT_A}'")
            ).fetchall()
            assert len(rows) == 0, (
                "B tenant látja A tenant sentinel sorát – cross-tenant szivárgás."
            )
    finally:
        current_tenant_schema.reset(token)
