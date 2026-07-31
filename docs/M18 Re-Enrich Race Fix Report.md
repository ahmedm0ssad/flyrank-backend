# M18 — Fix Re-Enrich Race Condition

## Commits

| Hash | Message | Files |
|------|---------|-------|
| `d6fb7c3` | fix: close re-enrich race condition with Redis lead_id -> job_id active key | 6 files, +275/−3 |
| `e07bcc1` | docs: mark re-enrich race condition as fixed in d6fb7c3 | 1 file, +2/−2 |

## Changes

### `app/core/queue.py`
- `create_enrichment_job()` (line 218): stores `enrichment:active:{lead_id}` → `job_id` with 600s TTL after enqueuing
- `get_enrichment_active()` (line 248): returns `enrichment:active:{lead_id}` value or None
- `clear_enrichment_active()` (line 253): deletes `enrichment:active:{lead_id}`

### `app/services/lead_service.py`
- `re_enrich_lead()` (lines 464-472): checks Redis active key via `run_in_executor` before the DB-status check; returns 409 if active key exists

### `app/services/lead_worker.py`
- `clear_enrichment_active(lead_id)` called on:
  - Success path 1 — "already_enriched" (line 38)
  - Success path 2 — "enriched" (line 68)
  - Final failure — all retries exhausted (line 108)
- NOT called on intermediate retry — key remains to block duplicates

## Tests Added (8)

| Test | File | What it asserts |
|------|------|-----------------|
| `test_create_enrichment_job_stores_active_key` | `test_background_jobs.py` | Redis has `enrichment:active:{lead_id}` after enqueue |
| `test_create_enrichment_job_active_key_has_correct_ttl` | `test_background_jobs.py` | TTL = 600 |
| `test_race_redis_key_blocks_despite_failed_status` | `tests/leads/test_service.py` | Create active key without changing DB status → `re_enrich_lead()` returns 409 |
| `test_202_with_no_active_key_and_failed_status` | `tests/leads/test_service.py` | No active key + status=failed → `re_enrich_lead()` returns 202 |
| `test_redis_key_cleared_worker_reenrich_succeeds` | `tests/leads/test_service.py` | Clear key manually → re-enrich succeeds on failed lead |
| `test_clears_active_key_on_success` | `test_lead_worker.py` | Worker removes key after successful enrichment |
| `test_clears_active_key_on_final_failure` | `test_lead_worker.py` | Worker removes key after all retries exhausted |
| `test_keeps_active_key_on_intermediate_retry` | `test_lead_worker.py` | Worker does NOT remove key on intermediate retry |

## Test Results

```
880 passed, 2 failed (pre-existing Postgres ConnectionRefused), 1 xfailed
Coverage: 2616/2616 = 99% (same 6 lines as before)
```

## CI Command

Exact command from `.github/workflows/ci.yml` lines 42-65:
```
python -m pytest \
  tests/embed/ \
  tests/leads/ \
  tests/widgets/ \
  tests/middleware/ \
  tests/models/ \
  tests/repositories/ \
  tests/routers/ \
  tests/scrapers/ \
  tests/services/ \
  tests/test_main.py \
  tests/test_background_jobs.py \
  tests/test_db_schema.py \
  tests/test_e2e_widget.py \
  tests/test_lead_worker.py \
  tests/test_report_worker.py \
  tests/test_worker.py \
  --ignore=tests/test_e2e.py \
  --ignore=tests/test_ai_e2e.py \
  --cov=app --cov-report=term-missing --tb=short -v
```

## Remaining Open Tier C Items (3)

1. Repository protocol conformance (LeadRepository/WidgetRepository)
2. Global singletons in lead_service/widget_service
3. In-process rate-limit dict growth in `dependencies/leads.py`
