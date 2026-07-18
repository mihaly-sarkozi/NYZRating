# DB migration flow (public + tenant)

Az alkalmazás **saját verziózott migration registryt** használ (nem Alembic):

| Séma | Tábla | Revízió formátum |
|------|-------|------------------|
| `public` | `platform_schema_migrations` | `platform.public.0001_core` … |
| tenant | `<slug>.schema_migrations` | pl. `kb.search.schema.v1` |

## Release előtti lépések

1. **Dry-run review**: nézd át az új revíziókat a kódban (`core/modules/tenant/schema/public.py`, modul `bootstrap/tenant_hooks.py`).
2. **Backup**: `scripts/ops/backup_postgres.sh` (lásd `docs/ops/backup-restore-qdrant.md`).
3. **Migration futtatás** (külön deploy lépés, ne app startup-on):
   ```bash
   ./scripts/ops/migrate_db.sh
   ```
4. **Readiness**: `GET /api/health/ready` → `checks.migrations=ok`.
5. **Tenant sync**: `init_db.py` végén `sync_existing_tenant_schemas` minden aktív tenantra.

## Új migration hozzáadása

- **Public**: új `platform.public.NNNN_*` revízió a `public.py`-ban, idempotens DDL.
- **Tenant modul**: új hook a modul `bootstrap/tenant_hooks.py`-ban, regisztrálva az app manifestben.
- Teszt: unit/integration a séma diffre; ne futtasd élesben először startup guard nélkül.

## Rollback

- Nincs automatikus down migration. Rollback = előző app verzió + DB restore backupból.
- Tenant-only változásnál célzott SQL script készülhet, de release policy: **forward-only + backup**.

## Production tiltás

- `init_db.py` automatikus futtatása app induláskor productionben kerülendő; használj külön migration jobot CI/CD-ből.
