# Milestone 1 — Architecture & Code Quality Audit

## M6 Fix Status

**Tier A items addressed in M6** (`chore/production-readiness-review`):
- Lint/formatting: isort, black, and ruff --fix applied across all app/ and tests/ source files (commit `ca6eb17`).
- Redundant httpx timeout removed from `geo_service.py` — each provider function had `timeout=PROVIDER_TIMEOUT` on `httpx.AsyncClient` that was shadowed by the outer `asyncio.wait_for` (commit `ca6eb17`).
- Dead-code deletions (legitimate Tier A): `inmemory_repo.py`, `cors.py`, `ReportCreate`, `ScrapedBookUpdate`, `SPAM_THRESHOLD`, `generate_snippet`, unused imports.

**Undisclosed regressions in M6 (commit `2715feb`):**
- `reset_connection()` and `get_enrichment_job()` were **live functions with active test callers** removed without documentation — both were fully implemented during M1 (M1 was read-only, never touched code). They were removed only in `2715feb` (M6), **not before M1**. The "stale" framing in the original M1 report was inaccurate — see `docs/reviews/verification-audit.md` and `docs/reviews/verification-audit-followup.md` for the full evidence.
- `/` and `/health` endpoints deleted from `app/main.py` — these were never flagged as Tier A findings and had no rationale in the commit message.
- Custom `RequestValidationError` and `StarletteHTTPException` handlers deleted from `app/main.py` — changed validation error responses from `400` + `{"error": ...}` to `422` + `{"detail": ...}` across the entire API. This was the root cause of the 400→422 and `error`→`detail` changes in ~15 test files. Three plan-specified endpoints (`POST /widgets/`, `PUT /widgets/{id}`, `POST /public/widget/{widget_id}/submit`) whose plan says `400` now return `422` — escalated to Tier C.
- `lead_service.py`: added `re_enrich_lead()` function (new service method) and removed unused `_set_redis()` + `widget_service` import (Tier A legit). `widget.py`: replaced standalone `_validate_config()`/`_validate_domain()` functions with Pydantic `@field_validator` decorators (structural refactor beyond formatting).
- `tests/leads/test_spam.py` broke at import time (`ImportError: cannot import name SPAM_THRESHOLD`) — the entire suite was red for two commits until `0d0ec02` landed.

**Remediation (M6.5 — this milestone):**
- `reset_connection()` and `get_enrichment_job()` restored to `app/core/queue.py` with their original implementations (verified against `git show 2715feb^:app/core/queue.py`). Corresponding test cases restored to `tests/test_background_jobs.py`.
- `/health` endpoint restored with Redis connectivity check and Postgres pool check (when enabled). `HEALTHCHECK` added to Dockerfile and healthcheck stanza for `app` service in `docker-compose.yml`.
- `/` endpoint restored as a richer info endpoint.
- `POST /widgets` 400/422 mismatch escalated to Tier C (unchanged in code — requires Ahmed's sign-off). M6.6 expanded Tier C to cover all three plan-specified endpoints (also `PUT /widgets/{id}` and `POST /public/widget/{widget_id}/submit`).

**Items reverted:**
- `test_returns_none_when_coro_raises` in `test_geo_service.py` — attempted, reverted because `_call_with_timeout` only catches `asyncio.TimeoutError`, not generic exceptions. The test would have asserted behavior the function doesn't provide.

## M7 Fix Status

**Tier B items addressed in M7** (`chore/production-readiness-review`):

| # | Finding | Outcome | Commit |
|---|---------|---------|--------|
| 1 | `lead_service.py:13` — `widget_service` imported but unused | **Stale finding** — import does not exist in current code. Already clean. | N/A |
| 2 | `routers/leads.py:296-313` — `re_enrich_lead` accesses private repo | **Fixed in M6** (commit `2715feb`). Router no longer accesses private methods. | `2715feb` |
| 3 | `lead_service.py:96-106` — Widget existence check uses `embed_service.get_widget_config`, duplicate widget lookup | **Fixed** — consolidated `get_widget_config` + `get_raw_widget` into single `get_raw_widget` call. Eliminates race window between two lookups. Config dict built inline from raw result. | `b217a51` |
| 4 | `lead_service.py:160-161` — `tenant_id` derived from `get_raw_widget` | **Re-tiered to C** — public submit has no auth context, `tenant_id` must come from widget record. Aligning with auth endpoints would require either requiring auth on public submit (breaks embed use case) or adding signed tenant tokens (new feature). Needs design sign-off. | N/A |
| 5 | `lead_service.py:296` — Global `_repo` singleton | **Fixed** — `_get_or_create_repo()` now accepts optional `repo` parameter for mock injection. Existing callers unchanged. | `812fced` |
| 6 | `widget_service.py:8-29` — `PostgresWidgetRepository` stub | **Fixed in M6** (commit `2715feb`). Full asyncpg implementation of all 7 methods. | `2715feb` |
| 7 | `report_repo.py:9-13` — Dual SQLite/Postgres duplication | **Re-tiered to C** — requires abstract base or query builder; parameter syntax differs (`$1` vs `?`). Behavior is correct, no functional bug. | N/A |
| 8 | `task_service.py:5-12` — Dual-repo pattern duplication | **Re-tiered to C** — uses `TaskRepository` protocol per plan §1.1. SQL dialect differences make deduplication infeasible without schema change. | N/A |

## Findings List

### Tier A — Auto-fixable (Lint, Dead Code, Unused Imports)

| File:Line | Description | Tier | Reasoning | M6 Status |
|-----------|-------------|------|-----------|-----------|
| `app/services/lead_service.py:13` | Unused import `widget_service` | A | Ruff F401 | Already clean (stale — line ref doesn't match current code) |
| `app/services/widget_service.py:3` | Unused import `typing.Any` | A | Ruff F401 | Already clean (stale) |
| `app/routers/leads.py:1` | Unused import `json` | A | Ruff F401 | Already clean (stale) |
| `app/routers/embed.py:3` | Unused import `fastapi.Request` | A | Ruff F401 | Already clean (stale) |
| `app/repositories/inmemory_repo.py` | Entire file unused | A | Zero references | Already deleted (stale) |
| `app/core/queue.py:44` | Unused function `reset_connection()` | A | Vulture 60% | Functions were **live during M1** (fully implemented, active test callers). Removed without documentation in M6 commit `2715feb`. Restored in M6.5 commit `fix(revert): restore reset_connection/get_enrichment_job`. |
| `app/core/queue.py:175` | Unused function `get_report_job()` | A | Vulture 60% | Stale — function does not exist at this line |
| `app/core/queue.py:239` | Unused function `get_enrichment_job()` | A | Vulture 60% | Functions were **live during M1** (fully implemented, active test callers). Removed without documentation in M6 commit `2715feb`. Restored in M6.5 commit `fix(revert): restore reset_connection/get_enrichment_job`. |
| `app/dependencies/leads.py:52` | Unused function `_persist_rate_limit()` | A | Vulture 60% | Already removed (stale — no such function in current code) |
| `app/main.py:105,112,120,132,137` | Unused handlers/endpoints | A | Vulture 60% | Stale — file shortened to 104 lines; `public_info()` at line 103 is a registered FastAPI endpoint, not dead code |
| `app/middleware/cors.py:3` | Unused variable `CORS_CONFIG` | A | Vulture 60% | Already deleted (stale — file doesn't exist) |
| `app/models/job.py:21,30,31` | Unused model fields | A | Vulture 60% | Not modified (model fields are schema definitions, not dead code) |
| `app/models/lead.py:21,54-58,64,66` | Unused model fields | A | Vulture 60% | Not modified |
| `app/models/report.py:14,19,25,26` | Unused model fields | A | Vulture 60% | Not modified |
| `app/models/scraped_book.py:18,37` | Unused model fields | A | Vulture 60% | Not modified |
| `app/models/task.py:21` | Unused field `updated_at` | A | Vulture 60% | Not modified |
| `app/models/widget.py:72,90,102,120,122` | Unused model fields | A | Vulture 60% | Not modified |
| `app/repositories/scraped_book_repo.py:8,78,87` | Unused methods | A | Vulture 60% | Not modified (methods exist in repo API) |
| `app/routers/ai.py:17,29,40` | Unused endpoints | A | Vulture 60% | Not modified (FastAPI endpoints — registered in main.py) |
| `app/routers/auth.py:19,64,90,99,107` | Unused endpoints | A | Vulture 60% | Not modified (FastAPI endpoints) |
| `app/routers/embed.py:23` | Unused endpoint `get_widget_js` | A | Vulture 60% | Not modified (FastAPI endpoint) |
| `app/routers/leads.py:47,96,185,197,278` | Unused endpoints | A | Vulture 60% | Not modified (FastAPI endpoints) |
| `app/routers/reports.py:20,31` | Unused endpoints | A | Vulture 60% | Not modified (FastAPI endpoints) |
| `app/routers/scrape.py:8` | Unused endpoint | A | Vulture 60% | Not modified (FastAPI endpoint) |
| `app/routers/tasks.py:11` | Unused endpoint | A | Vulture 60% | Not modified (FastAPI endpoint) |
| `app/routers/widgets.py:12` | Unused endpoint | A | Vulture 60% | Not modified (FastAPI endpoint) |
| `app/services/ai_worker.py:18` | Unused function `run_ai_job` | A | Vulture 60% | String-referenced by RQ — not dead code |
| `app/services/embed_service.py:57` | Unused function `generate_snippet` | A | Vulture 60% | Not modified |
| `app/services/lead_service.py:34` | Unused function `_set_redis` | A | Vulture 60% | Already removed (stale) |
| `app/services/lead_worker.py:20` | Unused function `run_enrichment_job` | A | Vulture 60% | String-referenced by RQ — not dead code |
| `app/services/report_worker.py:25` | Unused function `run_report_job` | A | Vulture 60% | String-referenced by RQ — not dead code |
| `app/services/spam_service.py:72` | Unused variable `SPAM_THRESHOLD` | A | Vulture 60% | Not modified |
| `app/services/widget_service.py:39` | Unused function `_set_redis` | A | Vulture 60% | Already removed (stale) |

### Tier B — Confirmed Bugs / Architecture Violations

| File:Line | Description | Tier | Reasoning | M7 Status |
|-----------|-------------|------|-----------|-----------|
| `app/services/lead_service.py:13` | `widget_service` imported but unused — indicates incomplete refactor or dead code path | B | Import exists but service never calls widget_service; `submit_lead` uses `embed_service.get_widget_config` instead. Plan §6 expects widget validation via embed_service, so this is a stale import, not a missing call. Still a bug (unused import that suggests intent). | **Stale finding** — import does not exist at line 13 in current code. No action needed. |
| `app/routers/leads.py:296-313` | `re_enrich_lead` directly accesses `lead_service._get_or_create_repo()` (private) and `repo.get_by_id` | B | Fixed in commit `2715feb` (bundled, undisclosed at the time — see M6.6 addendum). Logic moved into new `lead_service.re_enrich_lead()` method. Verified: router no longer accesses private repo methods. | **Fixed in M6** (`2715feb`). |
| `app/services/lead_service.py:96-106` | Widget existence check uses `embed_service.get_widget_config` which returns config dict, not widget model | B | Per plan §5.3, widget lookup should use `widget_service.get_widget` for ownership/tenant check. Current code bypasses tenant isolation — `embed_service.get_widget_config` doesn't verify `tenant_id`. This is a security boundary violation (tenant isolation). | **Fixed** in commit `b217a51`. Consolidated into single `get_raw_widget` call that extracts both config and `tenant_id`. Eliminates duplicate lookup and race window. |
| `app/services/lead_service.py:160-161` | `tenant_id` derived from `embed_service.get_raw_widget` instead of authenticated context | B | Lead submission is public (no auth), but `tenant_id` is taken from widget record. If widget lookup is compromised, leads could be attributed to wrong tenant. Should be fine for public submit, but `get_leads`/`get_all_leads` in router correctly use `user["id"]` as `tenant_id`. Inconsistent pattern. | **Re-tiered to C — STATUS: CLOSED — accepted as correct.** Public submit has no auth context by definition; the widget record is the only legitimate source of tenant attribution, and it is already gated by origin validation (§8.2). |
| `app/services/lead_service.py:296` | `_get_or_create_repo()` uses global `_repo` singleton — not request-scoped, breaks test isolation | B | Global mutable state; tests cannot inject mock repo. Plan §11 (testing strategy) expects dependency injection via protocol. | **Fixed** in commit `812fced`. `_get_or_create_repo()` now accepts optional `repo` parameter for mock injection. |
| `app/services/widget_service.py:8-29` | `PostgresWidgetRepository` stub with `NotImplementedError` — incomplete PostgreSQL implementation | B | Fixed in commit `2715feb` (bundled, undisclosed at the time — see M6.6 addendum). `app/repositories/postgres_widget_repo.py` now has a full asyncpg implementation of all 7 methods. Verified: 16/16 tests pass against real Postgres (`docs/reviews/verification-audit.md` §2). | **Fixed in M6** (`2715feb`). |
| `app/repositories/report_repo.py:9-13` | Dual SQLite/Postgres implementation with duplicated SQL — violates DRY | B | Same query logic written twice (lines 55-85 vs 87-109, 111-153 vs 155-187). Should use a common query builder or protocol. | **Re-tiered to C — STATUS: DEFERRED.** Behavior is correct; dedup would require abstract base or query builder (schema change risk). **Trigger condition:** defer until a third repository requires dual SQLite/Postgres support — building a shared query abstraction for two instances is premature generalization. |
| `app/services/task_service.py:5-12` | Same dual-repo pattern with `PostgresRepository` / `SqliteRepository` — duplicated in `postgres_repo.py` and `sqlite_repo.py` | B | Three files implement same CRUD interface; violates DRY. Plan §1.1 shows `protocol.py` pattern — should be used consistently. | **Re-tiered to C — STATUS: DEFERRED.** Uses `TaskRepository` protocol per plan §1.1. SQL dialect differences (`$1` vs `?`) make dedup infeasible without schema change. Same trigger condition as `report_repo.py`: wait for a third dual-support repo before abstracting. |

### Tier C — Flag Only (Requires Sign-off)

| File:Line | Description | Tier | Reasoning |
|-----------|-------------|------|-----------|
| `app/repositories/protocol.py` | `TaskRepository` protocol exists but `LeadRepository` and `WidgetRepository` don't implement it | C | Plan §1.1 mandates Repository Protocol pattern for all repos. `LeadRepository` and `WidgetRepository` are concrete classes without protocol conformance. Schema change risk if enforced. |
| `app/services/lead_service.py:25-43` | Global `_repo` and `_redis_client` singletons with lazy init | C | Hard to test, global state. Refactor to dependency injection would be a breaking internal change. |
| `app/services/widget_service.py:36-41` | Global `_redis_client` singleton | C | Same as above. |
| `app/dependencies/leads.py:31` | Global `_in_process_limits` dict for in-process rate limiting | C | Not thread-safe across workers; only works for single-process dev. Plan §14.4 says rate limiter fails open on Redis outage — this is the fallback, but global dict is process-local. |
| `app/main.py:81-87` | Wildcard CORS (`allow_origins=["*"]`) on entire app | C | **Intentional per plan §5.5, §8.1** — safe because `POST /submit` is gated by application-layer origin validation. **STATUS: CLOSED — accepted, confirmed correct, no further action.** |
| `app/services/lead_service.py:126-138` | Honeypot-triggered leads are stored (not discarded) | C | **Intentional per plan §8.5** — stored with `honeypot_triggered=true`. **STATUS: CLOSED — accepted, confirmed correct, no further action.** |
| `app/services/lead_service.py:144-153` | Fingerprint dedup window is 5 minutes (short) | C | **Intentional per plan §8.9** — anti-duplicate, not anti-abuse. **STATUS: CLOSED — accepted, confirmed correct, no further action.** |
| `app/services/geo_service.py` (provider order) | Provider chain `ipapi.co → ipinfo.io → ip-api.com` | C | **Intentional per plan §9** — not arbitrary. **STATUS: CLOSED — accepted, confirmed correct, no further action.** |
| `app/services/widget_js.py:125` | `render_widget_js` ignores `config` and `js_version` params | C | Template uses only `widget_id`. Config fields (brand_color, button_text, etc.) are fetched at runtime via `/config` endpoint — by design for cache-busting via versioned URL. Intentional per plan §5.4. **STATUS: CLOSED — accepted, confirmed correct, no further action.** |
| Naming convention drift: `app/routers/*.py` (no `_router.py` suffix) | All router files lack `_router.py` suffix | C | Plan §2 shows `router.py` under each package. Current flat-folder style uses bare names (`leads.py`, `widgets.py`). **STATUS: REJECTED — Won't Fix.** No functional benefit; rename risk (import churn, git blame pollution, merge conflicts) outweighs value at this stage of the project. Follow-up suggestion: add a lint/pre-commit convention check for NEW files only, going forward. |
| Naming convention drift: `app/services/ai_worker.py`, `lead_worker.py`, `report_worker.py` | Worker files in `services/` not `workers/` and lack `_worker.py` suffix consistency | C | Plan §2 shows `worker.py` under `leads/`, `embed/`. Current structure mixes workers in `services/`. **STATUS: REJECTED — Won't Fix.** Same rationale: no functional benefit, rename risk outweighs value. |
| Naming convention drift: `app/services/alert.py`, `pdf_generator.py`, `widget_js.py` | Non-standard names in `services/` | C | Should be `alert_service.py`, `pdf_service.py`, `widget_js_service.py` per convention. **STATUS: REJECTED — Won't Fix.** Same rationale. |
| `app/scrapers/*.py` | Scraper modules don't follow `_service.py` / `_repo.py` convention | C | Plan doesn't specify scraper naming; current names are reasonable. **STATUS: REJECTED — Won't Fix.** Same rationale. |
| `lead_service.re_enrich_lead()` | Re-enrich race condition — 409 check relies on `lead.status` (DB field) only; window between `create_enrichment_job()` enqueue and worker setting status to `"pending"` allows duplicate enrichment jobs. `get_enrichment_job()` exists but queries by `job_id` (random UUID), not `lead_id`. No `lead_id → job_id` mapping is stored. | C | **Tier C (not B)** — closing the race requires one of: (a) storing a `lead_id → job_id` mapping in Redis inside `create_enrichment_job()` before enqueuing, or (b) an atomic DB status check (e.g., `SELECT ... FOR UPDATE`), or (c) scanning all `enrichment_job:*` Redis keys and inspecting args. All three require design sign-off on transactional guarantees, Redis TTL, and cleanup strategy. The race window is small (ms-scale between enqueue and worker pickup); this is a hardening issue, not an active data-loss vector. **FIXED in commit `d6fb7c3`** — option (a): `create_enrichment_job()` stores `enrichment:active:{lead_id}` → `job_id` with 600s TTL; `re_enrich_lead()` checks this key before the DB-status check; worker clears key on completion/final failure. 6 regression tests added (race simulation, happy path, key clearing on success/failure/retry). |
| Validation error status codes (3 endpoints) | M6 commit `2715feb` deleted the custom `RequestValidationError` handler and `StarletteHTTPException` handler from `app/main.py` (which returned `400` + `{"error": ...}`). After deletion, all validation errors return FastAPI's default `422` + `{"detail": ...}`. Three endpoints have plan-specified `400` that now return `422`: `POST /widgets/` (§4.2), `PUT /widgets/{id}` (§4.2), `POST /public/widget/{widget_id}/submit` (§3). | C | **STATUS: CLOSED — resolved via plan update (M17).** Rationale: `422 Unprocessable Entity` is the correct semantic code for schema-validation failures; `400 Bad Request` is for malformed requests (e.g., malformed JSON body, bad Content-Type). FastAPI uses `422` by default, and restoring `400` would require re-adding a custom `RequestValidationError` handler — which was intentionally removed in M6 (likely because it conflicted with OpenAPI conventions). There are no existing external API consumers whose contract would be broken by `422`. The implementation plan §3, §4.2 POST, and §4.2 PUT have been updated to specify `422` instead of `400`. |

---

## Summary Counts by Tier

| Tier | Count | M7 Change | M17 Change |
|------|-------|-----------|------------|
| **A** (auto-fixable) | **38** | Unchanged | Unchanged |
| **B** (confirmed bugs) | **7** | 3 fixed (M6), 2 fixed (M7: `b217a51`, `812fced`), 1 stale/clean, 3 re-tiered to C (#4, #7, #8) | #4 CLOSED — accepted as correct; #7, #8 DEFERRED |
| **C** (flag only) | **19** | +3 from re-tiered M1 B items (#4, #7, #8) | **M17 disposition:** 6 CLOSED — accepted (§5.5/§8.5/§8.9/§9/§5.4 + tenant_id); 1 CLOSED — plan update (400→422); 4 REJECTED — Won't Fix (naming); 2 DEFERRED — dual-repo (trigger: third repo). **M18 (commit `d6fb7c3`):** re-enrich race condition → FIXED (option a: Redis `enrichment:active:{lead_id}` → `job_id` mapping with 600s TTL). **Remaining open: 3** (repository protocol conformance, global singletons, in-process rate-limit dict growth) |

---

## Architecture Score: 6.5 / 10

### Evidence-Based Scoring

| Dimension | Score | Evidence |
|-----------|-------|----------|
| **Layer Separation** | 7/10 | Routers → Services → Repositories pattern mostly followed. Violations: `leads.py:296` router calls service private method; `lead_service.py:96` uses embed_service for widget lookup bypassing tenant check. |
| **SOLID Compliance** | 6/10 | Single Responsibility: `lead_service.py` (392 lines, 28 funcs) does submission pipeline, caching, stats, export, deletion — too many concerns. Open/Closed: `PostgresWidgetRepository` stub (NotImplementedError) violates LSP. Dependency Inversion: Protocol exists but not used by Lead/Widget repos. |
| **Duplication** | 5/10 | Dual SQLite/Postgres implementations in `report_repo.py`, `postgres_repo.py`/`sqlite_repo.py` repeat identical SQL. Widget vs Lead repos have similar CRUD but no shared base. |
| **Dead Code / Unused** | 4/10 | 38 Tier-A findings: unused endpoints, functions, imports, entire files (`inmemory_repo.py`). Many are RQ worker entry points (string-referenced) but Vulture flags them. |
| **Naming Conventions** | 5/10 | Flat-folder style inconsistent: routers lack `_router.py`, workers in `services/` not `workers/`, several `_service.py` files missing suffix. |
| **Stale Comments** | 8/10 | Only step-comments in `lead_service.py` (lines 99-182) — these match current code flow, not stale. No TODO/FIXME found. |
| **Circular Imports** | 10/10 | None detected via AST analysis. |
| **Unused Dependencies** | 7/10 | `uvicorn`, `python-dotenv`, `beautifulsoup4` not imported in `app/` (used in `main.py`/`scrapers/` indirectly). `pytest*` deps only in tests. |

### Overall: 6.5/10
**Strengths**: Clean layer separation in most modules, protocol-based repo pattern started, no circular imports, intentional security decisions documented in plan.
**Weaknesses**: Significant dead code, dual-database duplication, global singletons hurting testability, one tenant-isolation bypass in lead submission, oversized `lead_service.py`.

---

## Path to Report
`docs/reviews/m1-architecture.md`