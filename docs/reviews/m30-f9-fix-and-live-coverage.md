# M30 — F9 Fix + Live Coverage for Worker Enrichment (closed-loop asyncpg pool)

**Status**: COMPLETE
**Date**: 2026-08-01
**Branch**: `feature/capstone-submission-pack`
**Commits**: `cd12f48` (fix) · `ccd5a1f` (live-Postgres F9 regression test) · (this report, docs)
**Baseline reference**: M29 — F9 reported NEW Tier B; 946 passed / 100% coverage mocked.

---

## 1. Root cause (confirmed by full-file read of every worker)

`app/services/lead_worker.py` `run_enrichment_job` wraps **every** DB operation in its own
`asyncio.run()` — three per job: `repo.get_by_id` (line 42), `repo.update_status` on
success (line 59), and `repo.update_status` on final failure (line 115). All three resolve
to `PostgresLeadRepository`, which calls `app.core.database.get_pool()`. `_pool` is a
**module-level asyncpg singleton** that is created on the *first* `asyncio.run()`'s loop
and left bound to that loop after `asyncio.run()` closes it. Every subsequent `asyncio.run()`
reuses the poisoned pool → `asyncpg.InterfaceError: cannot perform operation: another
operation is in progress` / `RuntimeError: Event loop is closed` / `AttributeError:
'NoneType' object has no attribute 'send'` / `'NoneType' object has no attribute 'connect'`.

Same latent defect in `app/services/report_worker.py` `run_report_job`: three
`asyncio.run(update_report_status(...))` calls → `ReportRepository.update_report_status`
→ `get_pool()`. M29 only observed F9 via the lead worker because no report jobs were
triggered live, but the code path is identical.

`app/services/ai_worker.py` is **not** affected: `run_ai_job` is fully sync (sync
`call_ai` + sync `update_job`), never touches the pool.

`app/core/queue.py` enqueues `app.services.lead_worker.run_enrichment_job`,
`report_worker.run_report_job`, `ai_worker.run_ai_job` on the three RQ queues
(`Retry(max=3, interval=[10, 60, 300])`, timeout 600).

M29's standalone repro (`%TEMP%\opencode\m29_f9_repro.py`): `asyncio.run()` #1
(`get_by_id`) succeeds; `asyncio.run()` #2 raises `InterfaceError`.

---

## 2. Fix design (and why it beats the alternatives)

Keep all three workers' established lifecycle shape — sync RQ wrappers with
`asyncio.run()` per operation — which is the documented M3 lifecycle-match design
(`docs/reviews/m3-performance-jobs.md`), and fix the root cause at the **shared
dependency**. `database.get_pool()` is now loop-aware: it records the loop the singleton
pool was created on (`_pool_loop`); when the currently-running loop differs, it
best-effort closes and drops the pool, then recreates it bound to the current loop.
`close_pool()` resets the tracking. This fixes `lead_worker` **and** `report_worker` in
one place with zero worker restructuring, and `ai_worker` needs nothing.

Alternatives considered and rejected:

- **Open a pool per `asyncio.run()`/job** — pushes lifecycle burden onto each worker,
  duplicates connection churn (min_size=2 per job), and diverges from the M3
  lifecycle-match contract for all three workers.
- **Restructure the workers to run one persistent loop** — a large, risky rewrite of
  every worker (and their 946-test mocked suite) to fix a defect that lives entirely in
  one shared function.
- **Thread-local / per-loop pool caches** — leaks pools across loops and complicates
  shutdown; over-engineered for a process that is a single-threaded RQ worker.

The loop-aware singleton is the minimal change: `+8` statements in one shared module,
covered by a mocked unit test (recreation branch, including the best-effort-close `except`
path) plus a real-asyncpg live regression test.

---

## 3. The fix (`app/core/database.py`)

```diff
 _pool: asyncpg.Pool | None = None
+_pool_loop: asyncio.AbstractEventLoop | None = None


 async def get_pool() -> asyncpg.Pool:
-    global _pool
+    global _pool, _pool_loop
+    loop = asyncio.get_running_loop()
+    if _pool is not None and _pool_loop is not loop:
+        # cached pool was created on a different (now-closed) asyncio.run() loop;
+        # asyncpg pools are bound to their creation loop, so drop best-effort and
+        # recreate below.
+        try:
+            await _pool.close()
+        except Exception:
+            pass
+        _pool = None
+        _pool_loop = None
     if _pool is None:
         ...
         for attempt in range(1, 6):
             try:
                 _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
+                _pool_loop = loop
                 break
             ...
```

`pyproject.toml` adds `"app/core/database.py" = ["BLE001", "S110"]` to the existing
per-file-ignore list (same as `lead_worker.py`, `widget_service.py`, etc.) because the
best-effort close of a pool bound to a closed loop is intentionally exception-swallowed.

---

## 4. Proof: new live test fails pre-fix, passes post-fix

New regression test `TestPostgresLeadRepositoryLive::test_f9_second_asyncio_run_reuses_closed_loop_pool`
in `tests/repositories/test_postgres_lead_repo_live.py` — a **sync** `def test_...` that
runs two back-to-back `asyncio.run()` invocations against the real compose Postgres,
mirroring exactly how RQ calls `run_enrichment_job`: run #1 creates a widget + lead
(`get_pool` on loop A), run #2 does `get_by_id` + `update_status` (loop B). Pre-fix, run #2
reuses the pool bound to loop A's now-closed loop and raises; post-fix it succeeds.

Same file, same real Postgres, only the fix stashed away:

```
$ git stash push -- app/core/database.py tests/core/test_database.py

pre-fix  →  1 failed, 19 passed
  test_f9_second_asyncio_run_reuses_closed_loop_pool FAILED
  asyncpg.exceptions._base.InterfaceError: cannot perform operation: another operation is in progress
  RuntimeError: Event loop is closed
  AttributeError: 'NoneType' object has no attribute 'send'
  (raised inside repo.get_by_id → pool.acquire() on the second asyncio.run)

$ git stash pop

post-fix →  20 passed in 10.93s
```

The other 19 live tests pass both ways (they were unaffected by F9). This is the
confirmation the milestone required: the suite demonstrably catches the exact M29 worker
failure mode.

---

## 5. Live worker run — two consecutive enrichment jobs both complete

Stack up (`app`/`db`/`redis` all healthy, host ports 8000/5432/6380), host worker running
on all three queues with `$env:DATABASE_URL="postgresql://flyrank:flyrank_pass@127.0.0.1:5432/flyrank"`
and `$env:REDIS_URL="redis://localhost:6380/0"`. Seed widget intact
(`e335f32a-b224-49f8-ae64-5a32359726f4`, domain `https://demo.example.com`).

**Lead #1** — `POST /public/widget/{seed}/submit` (Origin: `https://demo.example.com`,
`X-Forwarded-For: 8.8.8.8`) → **201**:

```
HTTP/1.1 201 Created
date: Sat, 01 Aug 2026 06:05:41 GMT
content-type: application/json

{"success":true,"message":"Thank you for your submission","lead_id":"d2b3c4dd-a11f-4d76-b659-5788b6ad28a6"}
```

**Lead #2 submitted immediately after** (the exact "second job" failure in M29) → **201**:

```
HTTP/1.1 201 Created
date: Sat, 01 Aug 2026 06:06:00 GMT
content-type: application/json

{"success":true,"message":"Thank you for your submission","lead_id":"881f3060-47a4-40dd-a6b7-0fc12bc27d7a"}
```

**Worker log** (`worker.log`, token redacted) — job #1 (`741cba7e`) and job #2 (`ba0544ac`)
both complete; neither hits the pre-fix `InterfaceError` path:

```
2026-08-01 09:05:42,198 [INFO] rq.worker: enrichment-jobs: app.services.lead_worker.run_enrichment_job('d2b3c4dd-a11f-4d76-b659-5788b6ad28a6') (741cba7e-5d61-4d01-904f-fdd1731f6af2)
2026-08-01 09:05:48,455 [INFO] app.services.lead_worker: Lead d2b3c4dd-a11f-4d76-b659-5788b6ad28a6 enriched with provider ipinfo
2026-08-01 09:05:48,549 [INFO] rq.worker: Successfully completed ... run_enrichment_job('d2b3c4dd-...') job in 0:00:06.303239s
2026-08-01 09:05:48,550 [INFO] rq.worker: enrichment-jobs: Job OK (741cba7e-5d61-4d01-904f-fdd1731f6af2)
2026-08-01 09:06:01,153 [INFO] rq.worker: enrichment-jobs: app.services.lead_worker.run_enrichment_job('881f3060-47a4-40dd-a6b7-0fc12bc27d7a') (ba0544ac-e76b-4b3b-93fd-871e210e85b9)
2026-08-01 09:06:02,358 [INFO] app.services.lead_worker: Lead 881f3060-47a4-40dd-a6b7-0fc12bc27d7a enriched with provider ipinfo
2026-08-01 09:06:02,400 [INFO] rq.worker: Successfully completed ... run_enrichment_job('881f3060-...') job in 0:00:01.211142s
2026-08-01 09:06:02,400 [INFO] rq.worker: enrichment-jobs: Job OK (ba0544ac-e76b-4b3b-93fd-871e210e85b9)
```

`worker.err` empty.

**Dashboard confirmation** — `GET /widgets/{seed}/leads` (Bearer) → **200**, both leads
`status:"enriched"`, `geo_provider:"ipinfo"` (geo country/city/region/isp are `null`
because ipinfo returns a bogon response for the private docker-gateway IP `172.18.0.1` —
the F7 artifact, see §7; the enrichment **status write itself** is what F9 was blocking):

```
{"id":"881f3060-...","ip_address":"172.18.0.1",...,"geo_provider":"ipinfo",...,"status":"enriched",...}
{"id":"d2b3c4dd-...","ip_address":"172.18.0.1",...,"geo_provider":"ipinfo",...,"status":"enriched",...}
```

**Verdict: PASS.** Both consecutive jobs completed end-to-end on the live stack — the two
jobs (`ceeffef2` / `50358add` / `80367d04`) that failed in M29 with the F9 signature now
both enrich.

---

## 6. Mocked-suite regression — CI command

Verbatim pytest invocation from `.github/workflows/ci.yml`:

```
947 passed in 60.98s
TOTAL ... 2896 statements, 0 missing → 100% coverage
```

**947 passed / 0 failed / 100% coverage** — M29's 946 plus the one new mocked F9 unit test
(`test_recreates_pool_when_bound_loop_changed`, added to the CI-path copy
`tests/repositories/test_core_database.py` and its mirror `tests/core/test_database.py`).
`app/core/database.py` is 37/37 covered (including the best-effort-close `except` branch).
`tests/repositories/test_postgres_lead_repo_live.py` remains auto-ignored via
`pyproject.toml` `addopts`.

---

## 7. F7 — unchanged, still Tier C

No code touched for F7. Reconfirmed by this milestone's own live submits: both were sent
with `X-Forwarded-For: 8.8.8.8`, and both stored `ip_address:"172.18.0.1"` — the header is
still ignored (uvicorn without `--proxy-headers`, `lead_service.py` uses
`request.client.host`). Consequence visible here: geo providers return bogon data for the
private IP, so `geo_country/city/region/isp` stay null while `geo_provider:"ipinfo"` and
`status:"enriched"` are written. Tier C, proxy-trust is a design decision — unchanged.

---

## 8. Findings summary

| ID | Description | Tier | Disposition |
|---|---|---|---|
| F6 | asyncpg `IPv4Address`/`IPv6Address` → `LeadResponse.ip_address: str` → 500 on live writes | B | CLOSED (M28 `e8a39fc`) |
| F7 | X-Forwarded-For not honored; client IP = direct TCP peer (`172.18.0.1`) | C | Unchanged, not fixed — reconfirmed every submit |
| F9 | Worker `asyncio.run()` per op reuses module-level asyncpg pool bound to a closed loop → `InterfaceError`/`Event loop is closed`; enrichment never completes, leads stay pending | B | **CLOSED** (`cd12f48`) — loop-aware `get_pool()` recreates the pool; live proof §4–§5, mocked 947/100% §6 |

`report_worker.py` needed **no code change** — the identical latent bug is fixed by the
shared `get_pool()` change. `ai_worker.py` needed nothing (never touches the pool).

---

## 9. Cleanup & state

- Batch-deleted both verification leads via `POST /widgets/{seed}/leads/batch-delete`
  → **204**; `GET /widgets/{seed}/leads` → `{"items":[],"total":0,...}`. Seed widget intact.
- Stopped the host worker (PID from `%TEMP%\opencode\m30_worker.pid`); removed
  `worker.log`/`worker.err` (the log contained an ipinfo URL carrying the `IPINFO_TOKEN`
  query value — **not reproduced anywhere in this doc**, and deleted with the log).
- `docker compose down` (DB volume retained). Working tree: only the two M27/M29 untracked
  report docs remain uncommitted (intentional).
- JWT/password files remain in `%TEMP%\opencode\` (treated as REDACTED; never committed).
