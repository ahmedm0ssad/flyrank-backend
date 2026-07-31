# M19 — Repository Protocols and Bounded In-Process Rate Limiter

## Part 1: Repository Protocols

**Commit:** `c3a96e3`

```
 app/repositories/lead_repo.py                   |  3 ++-
 app/repositories/postgres_widget_repo.py        |  3 ++-
 app/repositories/protocol.py                    |  8 +++++---
 app/repositories/widget_repo.py                 |  3 ++-
 tests/repositories/test_protocol_conformance.py | 21 +++++++++++++++++++++
 5 files changed, 32 insertions(+), 6 deletions(-)
```

**Pre-commit guardrail:** only those 5 files staged — confirmed.

**Changes:**
- `app/repositories/protocol.py`: Renamed `LeadRepository` → `LeadRepositoryProtocol`, `WidgetRepository` → `WidgetRepositoryProtocol` (both `@runtime_checkable`). Existing `TaskRepository` left unchanged.
- `app/repositories/lead_repo.py`: `class LeadRepository(LeadRepositoryProtocol)` — import added, class line updated.
- `app/repositories/widget_repo.py`: `class WidgetRepository(WidgetRepositoryProtocol)` — same pattern.
- `app/repositories/postgres_widget_repo.py`: `class PostgresWidgetRepository(WidgetRepositoryProtocol)` — same pattern.
- `tests/repositories/test_protocol_conformance.py`: 3 `isinstance` conformance tests (LeadRepository, WidgetRepository, PostgresWidgetRepository all check against their protocols).

No method signatures were changed — the protocols describe the real implementations, not the reverse.

## Part 2: Bounded In-Process Rate Limiter

**Commit:** `7f58e08`

```
 app/dependencies/leads.py      |  4 ++++
 tests/leads/test_rate_limit.py | 31 +++++++++++++++++++++++++++++++
 2 files changed, 35 insertions(+)
```

**Pre-commit guardrail:** only those 2 files staged — confirmed.

**Changes:**
- `app/dependencies/leads.py`: Added `_MAX_IN_PROCESS_KEYS = 10_000` constant. In `_check_in_process`, after the normal limit-loop, if `len(_in_process_limits) > _MAX_IN_PROCESS_KEYS`, the dict is fully cleared.
- `tests/leads/test_rate_limit.py`: Added `TestInProcessLimitBounding` with 2 tests — `test_fails_open_and_bounded` (dict stays ≤ bound under many keys) and `test_single_ip_still_rate_limited_after_clear` (individual IP limiting still works after eviction).

**Fail-open behavior unchanged** (plan §14.4): existing tests `test_redis_down_fails_open` and `test_redis_down_in_process_blocks_after_limit` both pass. Redis-down submissions still succeed via the fallback dict, which is now bounded.

## Full CI Test Suite

Command (from `.github/workflows/ci.yml`):
```
python -m pytest tests/embed/ tests/leads/ tests/widgets/ tests/middleware/ tests/models/ tests/repositories/ tests/routers/ tests/scrapers/ tests/services/ tests/test_main.py tests/test_background_jobs.py tests/test_db_schema.py tests/test_e2e_widget.py tests/test_lead_worker.py tests/test_report_worker.py tests/test_worker.py --ignore=tests/test_e2e.py --ignore=tests/test_ai_e2e.py --cov=app --cov-report=term-missing --tb=short -v
```

**Result: 885 passed, 2 failed, 1 xfailed in 66.79s — Coverage: 2624 stmts, 6 missed, 99%**

| Metric | Value |
|--------|-------|
| Passed | 885 |
| Failed | 2 (pre-existing `test_tables_exist`, `test_indexes_exist` — Postgres `ConnectionRefused`) |
| Xfailed | 1 (pre-existing `test_config_cache_control_header`) |
| Coverage | 2624 statements, 6 missed, 99% |
| Uncovered lines | `supabase.py:13-14`, `reports.py:47`, `cleaner.py:35`, `lead_worker.py:106-107` — all pre-existing |

**No regressions from M19 changes.**

## m1-architecture.md Updated

- Repository protocol conformance (line 98): marked **FIXED** in commit `c3a96e3`.
- Unbounded fallback dict (line 102, new row): marked **FIXED** in commit `7f58e08`.
- Summary table (line 123): Tier C count → 20; remaining open → **1** (global singletons).
