# KB / search alerting

## Ajánlott alert szabályok

| ID | Prioritás | Feltétel | Forrás |
|----|-----------|----------|--------|
| `p2_outbox_stuck` | P2 | `oldest_pending_seconds > 900` vagy pending > 100 | `/internal/health/outbox` |
| `p2_indexing_failed_spike` | P2 | `kb_processing_issues` INDEXING_FAILED ≥ 5 / 10 perc | processing issue recorder |
| `p2_qdrant_verification_failed` | P2 | `QDRANT_VERIFICATION_FAILED` ≥ 1 / 10 perc | indexing pipeline |
| `p2_search_failed_spike` | P2 | `kb.search.qdrant_failed` + `kb.search.embedding_failed` ≥ 10 / 10 perc | Prometheus metrikák |

## Platform admin monitoring

A security monitoring panel tartalmazza:
- `p2_queue_failure_rise` — outbox failed
- `p2_kb_qdrant_verification_failed`
- `p2_kb_indexing_failed_spike`
- `p2_kb_search_failed_spike`
- `p2_outbox_stuck_pending`

## Operációs válasz

1. **Stuck outbox**: `GET /internal/outbox/jobs?status=pending` → `POST /internal/outbox/jobs/{id}/requeue`
2. **Indexing failed**: KB processing monitor → failed item retry / ingest újra
3. **Qdrant verification failed**: readiness gate, majd `rebuild_qdrant_kb.sh`
4. **Search spike**: Qdrant health, embedding provider, rate limit

## Metrikák

- `kb.search.blocked_not_ready`
- `kb.search.embedding_failed`
- `kb.search.qdrant_failed`
- `kb.search.no_results` (info, nem alert)
