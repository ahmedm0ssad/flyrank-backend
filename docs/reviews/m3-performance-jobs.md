# Milestone 3 — Performance & Background Jobs Audit

## M6 Fix Status

**Tier A items addressed in M6** (`chore/production-readiness-review`):
- Redundant `timeout=PROVIDER_TIMEOUT` removed from all three provider functions (`_call_ipapi`, `_call_ipinfo`, `_call_ipapi_com`) in commit `ca6eb17`. The outer `asyncio.wait_for` at `_call_with_timeout` is the effective timeout.

## Findings List

### Tier A — Auto-fixable

| File:Line | Description | Tier | Reasoning | M6 Status |
|-----------|-------------|------|-----------|-----------|
| `app/services/geo_service.py:46,76,97` | Redundant `timeout=PROVIDER_TIMEOUT` on each `httpx.AsyncClient` | A | `asyncio.wait_for` at line 124 already enforces the 3s timeout. The httpx client timeout is a no-op shadow (the outer `wait_for` always fires first). Remove the httpx timeout parameter. | Fixed in commit `ca6eb17` |

### Tier B — Confirmed Bugs / Architecture Violations

| File:Line | Description | Tier | Reasoning |
|-----------|-------------|------|-----------|
| `app/services/lead_service.py:186` | `create_enrichment_job` called without `await` from async handler | B | `create_enrichment_job` (`app/core/queue.py:181`) uses sync `redis.Redis` (`get_connection()` returns sync client). Calling a sync blocking function from an async FastAPI handler blocks the event loop. The `except Exception: pass` at line 188 silently swallows any error. Plan §7 expects enrichment to be enqueued asynchronously. |
| `app/dependencies/leads.py:77-78` | EXPIRE calls outside the Redis pipeline — up to 3 extra round trips | B | Plan §8.3 specifies the 3-tier rate limiter must be "pipelined into a single Redis round trip, not 3 sequential calls." The INCRs are pipelined (lines 71-74) but the EXPIRE calls (lines 76-78) fire as separate `await redis.expire()` calls — up to 3 additional round trips per request when all tiers are first-hit. Fix: append EXPIRE commands to the same pipeline and execute once. |
| `app/core/queue.py` | `reset_connection()` is missing | B (Pre-flagged) | Agent Guide §1 confirms this function is referenced in tests but does not exist. Current file (217 lines) has no such function. |
| `app/core/queue.py` | `get_enrichment_job()` is missing | B (Pre-flagged) | Agent Guide §1 confirms this function is referenced in tests but not implemented. Current file has `create_enrichment_job`, `update_enrichment_job`, `get_enrichment_queue` but no `get_enrichment_job`. The M1 report (`m1-architecture.md:16`) had a stale line reference (`line 239`, which no longer exists in the current file) — the function simply doesn't exist. |
| `app/services/lead_service.py:356` | `export_csv` returns unbounded data | B | No `LIMIT`/`OFFSET` on export data. Plan §10.4 specifies pagination for all list endpoints but export has no page/page_size params. With large lead tables this will load all rows into memory and could OOM. Plan §6 (pipeline) shows export as a dashboard feature but doesn't address its pagination — add a max-row guard or streaming cursor. |

### Tier C — Flag Only (Requires Sign-off)

| File:Line | Description | Tier | Reasoning |
|-----------|-------------|------|-----------|
| `app/repositories/lead_repo.py:177-179` | `batch_delete` calls `self.delete()` per lead in a loop | C | In-memory implementation performs N individual deletes. A Postgres-backed version should use `DELETE WHERE id = ANY($1)` for a single round trip. In-memory repo makes this invisible until Postgres adapter is written. |
| `app/repositories/lead_repo.py` | No Postgres-backed `LeadRepository` exists | C | Only in-memory implementation exists. All performance concerns (N+1, index usage, query plans) are unverifiable against real Postgres. Plan §3 specifies dual SQLite/Postgres pattern (as in `report_repo.py`), but leads only have in-memory storage. |

---

## Index Audit Table

Source: `db/init.sql` vs `docs/implementation-plan.md` §3

| # | Index Name (from §3) | Table | Definition | Present in db/init.sql | Correctly Defined | Notes |
|---|---------------------|-------|-----------|----------------------|-------------------|-------|
| 1 | `PRIMARY KEY` | widgets | `(id)` | Line 48 `UUID PRIMARY KEY` | ✓ | |
| 2 | `idx_widgets_tenant` | widgets | `(tenant_id)` | Line 59 | ✓ | |
| 3 | `idx_widgets_domain` | widgets | `(tenant_id, domain)` UNIQUE | Line 60 | ✓ | `UNIQUE INDEX` as specified |
| 4 | `PRIMARY KEY` | leads | `(id)` | Line 66 `UUID PRIMARY KEY` | ✓ | |
| 5 | `idx_leads_widget` | leads | `(widget_id, created_at DESC)` | Line 87 | ✓ | DESC ordering included |
| 6 | `idx_leads_tenant` | leads | `(tenant_id, created_at DESC)` | Line 88 | ✓ | |
| 7 | `idx_leads_status` | leads | `(status) WHERE status = 'pending'` | Line 89 | ✓ | Partial index <u>is</u> specified with `WHERE` clause |
| 8 | `idx_leads_spam` | leads | `(spam_score)` | Line 90 | ✓ | |
| 9 | `idx_leads_fingerprint` | leads | `(fingerprint, created_at DESC)` | Line 91 | ✓ | |
| 10 | `idx_leads_honeypot` | leads | `(honeypot_triggered) WHERE honeypot_triggered = FALSE` | Line 92 | ✓ | Partial index <u>is</u> specified with `WHERE` clause |
| 11 | `PRIMARY KEY` | rate_limits | `(id)` | Line 98 `BIGSERIAL PRIMARY KEY` | ✓ | |
| 12 | `idx_rate_limits_lookup` | rate_limits | `(ip_address, endpoint, scope, window_start)` | Line 107 | ✓ | |

**Verdict: All 12 indexes from §3 are present and correctly defined in `db/init.sql`. Partial indexes on `idx_leads_status` and `idx_leads_honeypot` include their `WHERE` clauses.** ✓

---

## Known-Gap Verification (Agent Guide §1)

| Expected Function | Status in `app/core/queue.py` | Verdict |
|-------------------|-------------------------------|---------|
| `reset_connection()` | **MISSING** — not defined anywhere in the file | **FAIL — Tier B** |
| `get_enrichment_job()` | **MISSING** — `create_enrichment_job`, `update_enrichment_job`, `get_enrichment_queue` exist but no `get_enrichment_job` | **FAIL — Tier B** |

Both gaps from the Agent Guide are confirmed. Neither function exists in the current code. The M1 report's line references (lines 44 and 239) are stale — the file has been modified since M1 was written, and neither function was ever implemented.

---

## Redis Pipelining

### Plan §8.3 Requirement

> "all three tiers use the same `INCR` + `EXPIRE` primitive, **pipelined into a single Redis round trip**"

### Actual Implementation (`app/dependencies/leads.py`)

```python
pipe = redis.pipeline()             # pipeline opened
for key, _ in keys_and_limits:
    pipe.incr(key)                  # 3 INCRs queued
counts = await pipe.execute()       # 1 round trip — ✓

for (key, _), count in zip(...):    # separate loop
    if count == 1:
        await redis.expire(key, ...) # 3 separate round trips — ✗
```

**Verdict**: The INCRs are correctly pipelined (1 round trip). However, when all 3 keys are first-hit (e.g., first request from a new IP), 3 additional `EXPIRE` commands fire as individual round trips. Total: **4 round trips**, not 1. The fix is to queue `EXPIRE` on the same pipeline.

---

## Blocking / Sync Calls Inside Async Handlers

| File:Line | Caller (async context) | Sync Call | Impact |
|-----------|----------------------|-----------|--------|
| `app/services/lead_service.py:186` | `submit_lead` (async FastAPI handler) | `create_enrichment_job(str(lead.id))` | Sync `redis.Redis` (from `get_connection()`) called without `await`. Blocks event loop while Redis does HSET/EXPIRE. Exception silently swallowed at line 188. |

No other blocking calls found. Redis operations in `embed_service.py`, `fingerprint_service.py`, `lead_service.py` (stats cache), and `dependencies/leads.py` all use the async Redis client (`redis_ai.Redis`) correctly with `await`.

---

## Unbounded / Unpaginated Queries

| Endpoint | File:Line | Issue |
|----------|-----------|-------|
| `GET /widgets/{id}/export` | `lead_repo.py:129-147` / `lead_service.py:340` | `get_export_data()` returns **all** matching leads with no `LIMIT`. No pagination params. Could exhaust memory on large datasets. |

All list endpoints (`/widgets`, `/widgets/{id}/leads`, `/leads`) accept `page` / `page_size` and respect max 100. ✓

---

## Caching Verification (Plan §5.4, §9, §10.3)

| What | Cache Key | Specified TTL | Actual TTL | Present | Correct? |
|------|-----------|---------------|------------|---------|----------|
| Widget config | `widget:config:{id}` | 300s (5 min) | `CONFIG_CACHE_TTL = 300` (`embed_service.py:3`) | ✓ | ✓ |
| Geo-by-IP | `geo:ip:{ip}` | 86400s (24h) | `GEO_CACHE_TTL = 86400` (`geo_service.py:11`) | ✓ | ✓ |
| Widget stats | `stats:widget:{widget_id}` | 300s (5 min) | `_CACHE_TTL = 300` (`lead_service.py:76`) | ✓ | ✓ |
| Tenant stats | `stats:tenant:{tenant_id}` | 300s (5 min) | Same `_CACHE_TTL` | ✓ | ✓ |
| Submission fingerprint | `submission:fp:{fingerprint}` | 300s (5 min) | `FINGERPRINT_TTL = 300` (`fingerprint_service.py:4`) | ✓ | ✓ |

All specified caches are implemented with the correct TTLs. ✓

---

## Background Job Lifecycle (Enrichment Worker)

### Pattern Match vs report_worker.py / ai_worker.py

| Aspect | `lead_worker.py` | `report_worker.py` | `ai_worker.py` | Match? |
|--------|-----------------|-------------------|-----------------|--------|
| `get_current_job()` | Line 21 ✓ | Line 26 ✓ | Line 19 ✓ | ✓ |
| `_now()` helper | Line 16 ✓ | Line 21 ✓ | Line 14 ✓ | ✓ |
| Update to STARTED | Line 25 ✓ | Line 30 ✓ | Line 23 ✓ | ✓ |
| Update to QUEUED on retry | Line 91 ✓ | Line 66 ✓ | Line 53 ✓ | ✓ |
| Update to FAILED on final | Line 103 ✓ | Line 75 ✓ | Line 61 ✓ | ✓ |
| `send_alert()` on final failure | Line 112 ✓ | Line 82 ✓ | Line 68 ✓ | ✓ |
| Re-raise on failure | Line 113 ✓ | Line 84 ✓ | Line 70 ✓ | ✓ |
| Track `current_attempt` in meta | Line 78 ✓ | Line 53 ✓ | Line 39 ✓ | ✓ |

### Retry / Idempotency / Lifecycle

| Requirement (Plan §7 / Agent Guide) | Actual | Match? |
|-------------------------------------|--------|--------|
| Retry `max=3, interval=[10, 60, 300]` | `queue.py:68,151,197` — `Retry(max=3, interval=[10, 60, 300])` | ✓ |
| Job timeout 600s | `queue.py:75,158,204` — `job_timeout=600` | ✓ |
| Redis job-state keys | `job:{id}`, `report_job:{id}`, `enrichment_job:{id}` | ✓ |
| Lifecycle `queued → started → finished/failed` | All three workers follow this | ✓ |
| Idempotency: check `lead.status == 'enriched'` before re-running | `lead_worker.py:33` — `if lead.status == "enriched":` | ✓ |

Full match on all lifecycle and retry parameters. ✓

---

## Geo Provider Chain (Plan §9)

### Provider Order

| # | Provider | Code Function | Line | Matches §9? |
|---|----------|---------------|------|-------------|
| 1 | ipapi.co | `_call_ipapi` | `geo_service.py:140` | ✓ (first) |
| 2 | ipinfo.io | `_call_ipinfo` | `geo_service.py:145` | ✓ (second) |
| 3 | ip-api.com | `_call_ipapi_com` | `geo_service.py:150` | ✓ (last, as documented last resort) |

**Verdict**: Order is correct per plan §9 (ipapi.co → ipinfo.io → ip-api.com). ✓

### 3s Timeout via `asyncio.wait_for`

`geo_service.py:122-127` — `_call_with_timeout` wraps each provider call:
```python
async def _call_with_timeout(coro, ip, provider_name):
    return await asyncio.wait_for(coro, timeout=PROVIDER_TIMEOUT)
```
`PROVIDER_TIMEOUT = 3.0` at line 20. **This is actually implemented**, not just documented. ✓

Each provider also sets `timeout=PROVIDER_TIMEOUT` on `httpx.AsyncClient` — redundant but harmless (the `wait_for` always fires first).

### Cache Checked BEFORE Calling Providers

`geo_service.py:130-137`:
```python
def geo_enrich(ip):
    ...
    cached = get_cached_geo(ip)     # Line 134 — cache lookup first
    if cached:
        return cached                # Line 137 — return immediately
    async def _chain():              # Line 139 — only defined if cache miss
        ...
```

Cache is checked and short-circuits before any provider is called. ✓

---

## Performance Score: 8 / 10

| Dimension | Score | Evidence |
|-----------|-------|----------|
| **Redis Pipeline** | 6/10 | INCRs pipelined correctly (1 round trip) but EXPIREs fire as separate calls (up to +3). Plan §8.3 specifies single round trip. |
| **Indexes** | 10/10 | All 12 indexes from plan §3 are present, correctly defined, including both partial indexes with `WHERE` clauses. |
| **Caching** | 10/10 | All 5 specified caches (widget config, geo-by-IP, widget stats, tenant stats, fingerprint) implemented with correct TTLs. |
| **Blocking Calls** | 6/10 | One confirmed blocking call: `create_enrichment_job` (sync Redis) called without `await` from async handler. No others found. |
| **Background Jobs** | 9/10 | Lifecycle, retries, timeouts, idempotency all match plan and Agent Guide. Two known-gap functions missing from queue.py (Tier B). |
| **Geo Chain** | 10/10 | Provider order correct, `asyncio.wait_for` 3s timeout implemented, cache checked before providers. |
| **Pagination** | 8/10 | All list endpoints paginated with `page`/`page_size`. Export endpoint has no limit — unbounded data return. |

### Overall: 8/10

**Strengths**: Full index coverage, correct caching on all paths, matching background-job lifecycle, correct geo chain with proper timeouts and cache-first strategy.

**Weaknesses**: EXPIRE calls not pipelined (violating plan §8.3 single-round-trip requirement), one blocking sync Redis call in async handler, export endpoint unbounded, two pre-flagged functions (`reset_connection`, `get_enrichment_job`) genuinely missing from `queue.py`.
