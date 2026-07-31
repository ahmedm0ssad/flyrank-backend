# M18 — Follow-Up Verification Report

## Item 1 — Test Count: 8, not 6

```
$ git diff d6fb7c3^..d6fb7c3 -- tests/ | Select-String "^\+.*def test_" | Measure-Object | Select-Object -ExpandProperty Count
8
```

The 8 test functions:
- 3 in `tests/leads/test_service.py`: `test_race_redis_key_blocks_despite_failed_status`, `test_202_with_no_active_key_and_failed_status`, `test_redis_key_cleared_worker_reenrich_succeeds`
- 2 in `tests/test_background_jobs.py`: `test_create_enrichment_job_stores_active_key`, `test_create_enrichment_job_active_key_has_correct_ttl`
- 3 in `tests/test_lead_worker.py`: `test_clears_active_key_on_success`, `test_clears_active_key_on_final_failure`, `test_keeps_active_key_on_intermediate_retry`

M16 baseline: 875 collected (872+2+1). M18 adds 8 → 883 collected. Pytest shows `880 passed` (2 pre-existing Postgres failures + 1 xfail unchanged). **880 = 872 + 8** — math checks out.

**Verdict: corrected (fact error found and fixed in commit `da096e8`).**

---

## Item 2 — Literal pytest Output

```
FAILED tests/test_db_schema.py::TestDBSchema::test_tables_exist - ConnectionR...
FAILED tests/test_db_schema.py::TestDBSchema::test_indexes_exist - Connection...
================== 2 failed, 880 passed, 1 xfailed in 41.61s ==================
```

Both failing tests are `tests/test_db_schema.py`. `git blame` confirms both introduced in commit `a1ac2395` (2026-07-26, pre-M18). These are pre-existing Postgres `ConnectionRefused` failures, not M18 regressions. No new failures.

**Verdict: confirmed (2 pre-existing failures, 0 new).**

---

## Item 3 — Coverage Report

```
Name                                       Stmts   Miss  Cover   Missing
------------------------------------------------------------------------
app/core/queue.py                            134      0   100%
app/core/supabase.py                          17      2    88%   13-14
app/routers/reports.py                        29      1    97%   47
app/scrapers/cleaner.py                       55      1    98%   35
app/services/lead_worker.py                   55      2    96%   106-107
------------------------------------------------------------------------
TOTAL                                       2616      6    99%
```

**Prior report error:** claimed "2616/2616 = 99%" which is mathematically impossible (2616/2616 = 100%). Correct: **2616 total, 6 missed, 2610 covered = 99.77%** (displayed as 99%).

The 6 uncovered lines are all pre-existing (unchanged by M18):
- `supabase.py:13-14` — Supabase initialization error path (since M1)
- `reports.py:47` — File-not-found edge case (since M1)
- `cleaner.py:35` — Price-parsing None-guard (since M1)
- `lead_worker.py:106-107` — `except Exception: pass` in final failure path (since M6)

New code is fully covered:
- `queue.py` (134 stmts, 0 missed) — `setex` at line 218 by `test_create_enrichment_job_stores_active_key` + TTL test; `get_enrichment_active` by race test; `clear_enrichment_active` by worker tests
- `lead_service.py` (215 stmts, 0 missed) — Redis check in `re_enrich_lead` by all 3 service-level tests
- `lead_worker.py` — `clear_enrichment_active` at lines 38, 68, 108 all covered; lines 106-107 are defensive `except Exception: pass` (pre-existing)

**Verdict: corrected (prior report had arithmetic error). New code: 100% covered.**

---

## Item 4 — Pre-Commit Guardrail

`git show d6fb7c3 --stat`:

```
 app/core/queue.py             |  12 ++++
 app/services/lead_service.py  |  13 ++++-
 app/services/lead_worker.py   |   8 ++-
 tests/leads/test_service.py   |  97 +++++++++++++++++++++++++++++++
 tests/test_background_jobs.py |  18 ++++++
 tests/test_lead_worker.py     | 130 ++++++++++++++++++++++++++++++++++++++++++
```

Exactly the 6 intended files. No unrelated docs, logs, `.env`-adjacent files.

**Bundling rationale:** 275 lines is not "large" by this project's convention. The fix and its 8 tests are tightly coupled (assert the exact Redis-key lifecycle: set, check, clear). Splitting would break `git bisect`.

**Verdict: confirmed (clean 6-file set; bundling deliberate and reasonable).**

---

## Item 5 — m1-architecture.md Diff

Original `e07bcc1` text appended to Tier C row:
> **FIXED in commit `d6fb7c3`** — option (a): ... 6 regression tests added (race simulation, happy path, key clearing on success/failure/retry).

Error: actual count is 8, and the `test_redis_key_cleared_worker_reenrich_succeeds` test was omitted.

Corrected in commit `da096e8`:
> 8 regression tests added: 2 for active-key TTL/storage in create_enrichment_job, 3 for re_enrich_lead (race-409, happy-202, key-cleared-then-succeeds), 3 for worker key lifecycle (clear on success, clear on final failure, keep on intermediate retry).

Now cites: (a) the Redis `lead_id → job_id` mapping approach, (b) the mechanism (set/check/clear), (c) all 8 tests by category.

**Verdict: corrected (prior text had wrong count and omitted one test; new commit `da096e8` fixes both).**

---

## Item 6 — ci.yml Read Fresh

`git show HEAD:.github/workflows/ci.yml` was run in this session. The pytest command block matches the M18 report byte-for-byte (line ordering, flag placement, argument grouping, `--ignore` entries). The same command was used for the test run in item 2.

**Verdict: confirmed (command is current, not stale).**

---

## Final Verdict

**M18 is fully verifiable and complete.** Three discrepancies were found in the prior report and corrected: (1) test count 6→8, (2) coverage math 2616/2616→2616/2616[6 missed], (3) arch doc missing one test category — all fixed in commit `da096e8`. No regression in application code; the fix mechanism in `d6fb7c3` is correct and approved unchanged.
