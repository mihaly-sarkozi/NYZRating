# AIPLAZA skálázási stratégia

Ez a dokumentum a jelenlegi architektúra skálázási határait és az 1k+ tenant / magas ingest terhelés előtti döntéseket rögzíti. **Elsődleges szempont: migráció idő és tranzakció-biztonság**, nem a futásidejű query teljesítmény.

---

## 1. Séma-per-tenant: hol a határ?

### Jelenlegi modell

- Tenant adat: PostgreSQL **séma slug néven** (`SET LOCAL search_path` — lásd `session_context.py`).
- Public meta: `public.tenants`, `public.tenant_configs`, domain mapping.
- Tenant séma migráció: hook registry (`kb.*.schema.v*`, chat, stb.) → `upgrade_tenant_schema()` tenantonként.
- Release migráció: `sync_existing_tenant_schemas()` — **minden aktív tenant × minden pending hook**, szekvenciálisan.

### Mi lassul 500–2000 tenant felett?

| Terület | Hatás |
|---------|--------|
| `pg_catalog` | Sok séma × sok tábla → lassabb metadata lekérdezések, `\dt`, ORM reflection, backup restore |
| Migráció | N tenant × M hook = O(N×M) DDL; egy release window alatt lineárisan nő |
| Connection pool | Ugyanaz a pool, sok különböző `search_path`; SET LOCAL + RESET védi, de sok séma = nagyobb katalógus-memória |
| Operáció | Restore, reindex, monitoring tenantonként nehezebb |

### Döntési fa (1k+ tenant)

```
                    ┌─────────────────────────┐
                    │  Tenant count / growth  │
                    └───────────┬─────────────┘
                                │
           < 500 ───────────────┼────────────── 500–2000 ──────────────> 2000+
                                │                                │
                    Séma/tenant maradhat          Hibrid tier          DB shard
                    (optimalizált migráció)       (RLS + dedikált)      (több PG instance)
```

### Ajánlott fázisok

#### Fázis A — most → ~500 tenant (változtatás minimális)

- **Marad:** séma-per-tenant.
- **Migráció javítások** (fontosabb mint query tuning):
  - Release migráció **ne** app startup-on (`init_db.py`), hanem külön job: `scripts/ops/migrate_db.sh` + CI Postgres integration.
  - Tenant migráció **batch + párhuzamos shard**: pl. 4 worker, tenant slug hash `% 4`, külön tranzakció tenantonként.
  - **Canary**: először 1–3 tenant, majd 10%, majd 100%; rollback = app verzió vissza + DB restore (forward-only séma).
  - Metrika: `tenant.migration.duration_ms`, `tenant.migration.pending_count`.
- **Pool:** megtartjuk SET LOCAL + pool RESET (implementálva).

#### Fázis B — ~500–2000 tenant: **hibrid tier**

Új mező: `public.tenants.storage_tier`:

| Tier | Tárolás | Mikor |
|------|---------|-------|
| `shared_rls` | Egy `tenant_shared` séma, minden sor `tenant_id` + **RLS policy** | Demo, free, kis tenant (< X MB adat, < Y ingest/hó) |
| `dedicated_schema` | Jelenlegi slug séma | Growth/Business, nagy KB, compliance igény |
| `dedicated_db` | Külön PG instance (shard) | Enterprise, nagy ingest, SLA |

**Migráció shared_rls-re:**

1. Dupla-írás ablak (új tenantok shared-be).
2. Offline move: dedikált séma → shared táblák COPY + verify checksum.
3. Cutover: routing `storage_tier` alapján; session factory tier szerint `search_path` vagy RLS `SET app.tenant_id`.

**RLS minta (PostgreSQL):**

```sql
ALTER TABLE tenant_shared.kb_chunks ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tenant_shared.kb_chunks
  USING (tenant_id = current_setting('app.tenant_id')::bigint);
```

Az alkalmazás minden shared-tier session elején: `SET LOCAL app.tenant_id = '<id>'`.

**Miért hibrid?** A legtöbb tenant kicsi; a pg_catalog terhelés a sok kis sémától jön. A nagy tenantok továbbra is dedikált sémában maradnak (nincs noisy neighbor RLS-ben).

#### Fázis C — 2000+ tenant: **DB shard**

Új mező: `public.tenants.db_shard_id` → `database_url` a shard registry-ben.

```
                    ┌──────────────┐
   Router / API ───►│ Shard router │──► PG shard 0 (tenant A,C,E…)
                    │ (session     │──► PG shard 1 (tenant B,D,F…)
                    │  factory)    │──► PG shard N
                    └──────────────┘
```

- Tenant feloldás után a snapshot tartalmazza a `db_shard_id`-t.
- `make_session_factory()` shard-aware: DSN pool tenant tier/shard szerint.
- Migráció: **shardonként** fut, nem egy globális loop.
- Cross-shard query: tilos; platform admin aggregáció async read replica / warehouse.

### Migrációs SLA célok (tervezési számok)

| Tenant count | Max release migráció (p95) | Megjegyzés |
|--------------|----------------------------|------------|
| 100 | < 5 perc | Szekvenciális OK |
| 500 | < 30 perc | 4 parallel worker |
| 2000 (hibrid) | < 45 perc | Csak `dedicated_schema` + shared egyszeri hook |
| 2000 (shard) | < 20 perc / shard | Shard párhuzamosan |

---

## 2. Tenant feloldás: `run_in_executor` és cache

### Jelenlegi hot path

```python
# tenant_middleware.py ~163
slug, is_custom_domain, snapshot = await loop.run_in_executor(
    None,  # ← default ThreadPoolExecutor (min(32, cpu+4))
    lambda: self._resolution_service.resolve_request(host),
)
```

Hasonló minta: `auth_middleware.py` (~159) — token + DB user lookup.

`TenantResolutionService` már cache-el:

| Cache | TTL | Kulcs |
|-------|-----|-------|
| domain → slug | 300 s | `domain2tenant:{host}` |
| tenant snapshot | 60 s | `tenant:{slug}` |

### Szűk keresztmetszet

- Minden **cache miss** request → sync DB + threadpool slot.
- Default pool ~32 szál: 32 egyidejű cold request után sorban állnak az async coroutine-ök.
- Redis cache miss esetén ugyanez.

### Rövid táv (implementálható, alacsony kockázat)

1. **Dedikált executor** middleware-nek (ne `None`):
   ```python
   TENANT_EXECUTOR = ThreadPoolExecutor(
       max_workers=int(os.getenv("TENANT_RESOLVE_MAX_WORKERS", "64")),
       thread_name_prefix="tenant-resolve",
   )
   ```
2. **Agresszívabb snapshot TTL** stabil tenantokra:
   - `TENANT_TTL_SEC`: 60 → 300 (config: `tenant_snapshot_cache_ttl_sec`).
   - Domain mapping: 300 → 900 (ritkán változik).
   - Provisioning / config write: meglévő `invalidate_tenant_cache()` marad.
3. **Warm cache**: signup/provisioning végén `warm_tenant_cache(slug)` (már létezik `resolution.py`-ban).
4. **Metrikák** (már részben van):
   - `platform.tenant.resolution.failure.count`
   - Új: `platform.tenant.resolution.cache_hit`, `platform.tenant.resolution.executor_wait_ms`.

### Közép táv

- **Async Redis** (aioredis / redis.asyncio): cache hit path executor nélkül.
- **Snapshot denormalizálás**: JWT vagy session cookie mellé `tenant_id` + `security_version` — auth middleware cache hit gyakoribb.
- **Edge cache** (CDN / reverse proxy): statikus tenant routing custom domain-ekhez.

---

## 3. Outbox worker horizontális skála + autoskálázás

### Jelenlegi modell (jó alap)

- `PlatformEventOutboxRepository.claim_next_batch()` — **FOR UPDATE SKIP LOCKED**.
- Több `INSTANCE_ROLE=worker` process párhuzamosan dolgozhat.
- Publish oldal: `platform_event_outbox_backlog_soft_limit: 5000` — felette `EventDeliveryError` (backpressure).

### Autoskálázási jelek

A `/internal/health/outbox` snapshot már adja:

- `pending`, `running`, `failed`, `dead_letter`
- `oldest_pending_seconds`, `stuck_leases`

**Prometheus metrikák** (részben létezik):

- `outbox.backlog_size` (observe)
- `platform.outbox.queued.count`
- `outbox.publish_rejected_total{reason=backlog_soft_limit}`

**HPA / K8s javaslat:**

```yaml
# Példa: scale worker deployment
metrics:
  - type: External
    external:
      metric:
        name: outbox_pending_jobs
      target:
        type: AverageValue
        averageValue: "500"   # ~500 pending / worker replica
```

**Szabályok:**

| Jel | Akció |
|-----|-------|
| `pending > 2000` 5 percig | +1 worker replica |
| `oldest_pending_seconds > 300` | +1 worker replica (sürgős) |
| `pending < 200` 15 percig | -1 replica (min 1) |
| `dead_letter` spike | Alert, ne autoscale — operátor |

**Backlog soft limit szerepe:** 5000 = publish backpressure (web védése). Autoscale **nem** helyettesíti — a worker throughput-ot kell növelni, mielőtt a web elutasít publish-t.

### Event tier szétválasztás (közép táv)

| Queue / event_type prefix | Worker pool |
|---------------------------|-------------|
| `knowledge.*`, `kb.*` | `worker-ingest` (CPU heavy) |
| `email.*`, `audit.*` | `worker-io` |
| default | `worker-general` |

Külön `event_type` filter a claim query-ben, vagy külön outbox partition tábla.

---

## 4. Embedding: külön szűk keresztmetszet

### Jelenlegi helyzet

- `requirements.txt`: `torch`, `sentence-transformers` — **nagy CPU/RAM**.
- `LocalEmbeddingAdapter` default `embedding_device=cpu` (`embedding_assembly.py`).
- Embedding pipeline outbox eventeken keresztül fut (`knowledge.*` handler).
- **Kockázat:** ha web process importálja a torch stack-et (search cold start, lazy import hiány), a web réteg memória és startup függ az embedding modelltől.

### Cél architektúra

```
┌─────────────┐     outbox      ┌──────────────────┐
│  web (API)  │ ─── publish ──► │ platform_outbox  │
└─────────────┘                 └────────┬─────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │ worker-general │   │ worker-embed │   │ worker-index │
            │ (light events) │   │ torch/GPU    │   │ qdrant upsert│
            └──────────────┘   └──────────────┘   └──────────────┘
```

### Konkrét lépések

1. **`INSTANCE_ROLE=embedding`** (vagy `worker` + `OUTBOX_EVENT_FILTER=knowledge.embedding.*`):
   - Dedikált Docker service / K8s deployment.
   - Resource limits: CPU 4–8, RAM 8–16 GB; GPU node optional.
2. **Web/search ne importáljon torch-ot:**
   - Query embedding: `embedding_provider=openai` **vagy** gRPC/http hívás dedikált embedding service-re.
   - Guard: startup check — web role esetén `import torch` tiltás / lazy fail fast.
3. **Modell cache volume:** `EMBEDDING_MODEL_CACHE_DIR=/models` — read-only mount, ne töltse le minden pod.
4. **Skála:** embedding worker HPA a `kb_embedding_jobs` pending count / outbox `knowledge.embedding.*` backlog alapján.
5. **Fallback:** nagy burst esetén `embedding_provider=openai` átmeneti kapcsoló tenant szinten (feature flag).

### Search vs ingest szétválasztás

| Művelet | Hol fusson | Indok |
|---------|------------|-------|
| Batch ingest embedding | `worker-embed` | torch, hosszú CPU |
| Query embedding (search/chat) | OpenAI API vagy kis dedikált **query-embed** service | alacsony latency, web közel |
| Index upsert | `worker-index` | Qdrant I/O |

---

## 5. Összefoglaló prioritás

| Prioritás | Tétel | Hatás | Effort |
|-----------|-------|-------|--------|
| P0 | Migráció job app startup-ból külön + batch tenant upgrade | Release biztonság | Kész (runbook) |
| P0 | SET LOCAL + pool RESET | Tenant izoláció | Kész |
| P1 | Dedikált tenant resolve thread pool + TTL config | Web throughput | ~1 nap |
| P1 | Outbox backlog → Prometheus → worker HPA | Ingest burst | ~2 nap |
| P1 | Embedding worker külön deployment, web torch-free | Web stability | ~3–5 nap |
| P2 | `storage_tier` mező + shared RLS pilot | 500+ tenant | ~2–3 hét |
| P2 | `db_shard_id` + shard router | 2000+ tenant | ~1–2 hónap |

---

## 6. Kapcsolódó fájlok

| Terület | Fájl |
|---------|------|
| search_path | `core/kernel/db/session_context.py`, `session.py` |
| Tenant cache | `core/infrastructure/cache/__init__.py`, `core/modules/tenant/routing/resolution.py` |
| Middleware executor | `core/modules/tenant/middleware/tenant_middleware.py`, `core/modules/auth/middleware/auth_middleware.py` |
| Tenant migráció | `core/modules/tenant/schema/service.py` (`sync_existing_tenant_schemas`) |
| Outbox | `core/kernel/events/outbox.py`, `event_channel.py`, `base.py` (`platform_event_outbox_backlog_soft_limit`) |
| Embedding | `apps/kb/kb_embedding/bootstrap/embedding_assembly.py` |
| Migráció ops | `docs/ops/db-migrations.md`, `scripts/ops/migrate_db.sh` |
