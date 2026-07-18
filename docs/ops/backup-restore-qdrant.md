# Backup, restore és Qdrant rebuild

## Postgres

### Backup
```bash
./scripts/ops/backup_postgres.sh /var/backups/aiplaza
```
Kimenet: `aiplaza_YYYYMMDD_HHMMSS.dump` (custom format, `pg_dump -Fc`).

### Restore (teljes felülírás — csak maintenance ablakban)
```bash
./scripts/ops/restore_postgres.sh /var/backups/aiplaza/aiplaza_YYYYMMDD_HHMMSS.dump
```

## Qdrant

### Snapshot (infra szint)
Qdrant collection snapshot API vagy volume backup (`prod_qdrant_data` volume).

### Alkalmazás-szintű rebuild (Postgres source of truth)
Ha Postgres megvan, de Qdrant sérült:
```bash
./scripts/ops/rebuild_qdrant_kb.sh <tenant_slug> <kb_uuid>
```
Ez a `RebuildKnowledgeBaseIndexService` POINT_DELETE_AND_REINDEX módját hívja (chunk szintű újraindexelés).

**Figyelem:** rebuild ≠ snapshot restore. Cluster-szintű Qdrant restore-hoz snapshot/runbook kell.

## Object storage (MinIO)

- Bucket szintű `mc mirror` / provider backup policy.
- Restore után ellenőrizd az ingest fájl referenciákat.

## Evidence checklist (Go-live)

| Lépés | Parancs | Eredmény | Felelős | Időpont |
|-------|---------|----------|---------|---------|
| PG backup | `backup_postgres.sh` | dump fájl | | |
| PG restore teszt | staging restore | app boot OK | | |
| Qdrant rebuild teszt | `rebuild_qdrant_kb.sh` | search OK | | |
| MinIO backup | provider policy | objektumok | | |

## Kapcsolódó alertek

Lásd: `docs/ops/kb-search-alerts.md`
