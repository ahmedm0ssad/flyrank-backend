# Milestone 1 — Architecture & Code Quality Audit

## M6 Fix Status

**Tier A items addressed in M6** (`chore/production-readiness-review`):
- Lint/formatting: isort, black, and ruff --fix applied across all app/ and tests/ source files (commit `ca6eb17`).
- Redundant httpx timeout removed from `geo_service.py` — each provider function had `timeout=PROVIDER_TIMEOUT` on `httpx.AsyncClient` that was shadowed by the outer `asyncio.wait_for` (commit `ca6eb17`).
- Note: Many Tier A findings in the table below are **stale** — the codebase evolved between M1 (read-only audit) and M6 via intervening feature commits. The unused imports, deleted files (`inmemory_repo.py`, `cors.py`), and renamed functions were already cleaned up by prior work. The lint pass in M6 confirmed zero remaining auto-fixable issues in `app/`.

**Items reverted:**
- `test_returns_none_when_coro_raises` in `test_geo_service.py` — attempted, reverted because `_call_with_timeout` only catches `asyncio.TimeoutError`, not generic exceptions. The test would have asserted behavior the function doesn't provide.

## Findings List

### Tier A — Auto-fixable (Lint, Dead Code, Unused Imports)

| File:Line | Description | Tier | Reasoning | M6 Status |
|-----------|-------------|------|-----------|-----------|
| `app/services/lead_service.py:13` | Unused import `widget_service` | A | Ruff F401 | Already clean (stale — line ref doesn't match current code) |
| `app/services/widget_service.py:3` | Unused import `typing.Any` | A | Ruff F401 | Already clean (stale) |
| `app/routers/leads.py:1` | Unused import `json` | A | Ruff F401 | Already clean (stale) |
| `app/routers/embed.py:3` | Unused import `fastapi.Request` | A | Ruff F401 | Already clean (stale) |
| `app/repositories/inmemory_repo.py` | Entire file unused | A | Zero references | Already deleted (stale) |
| `app/core/queue.py:44` | Unused function `reset_connection()` | A | Vulture 60% | Re-tiered: this is a pre-flagged missing implementation (Tier B, per plan §1.81-88). Referenced in tests. |
| `app/core/queue.py:175` | Unused function `get_report_job()` | A | Vulture 60% | Stale — function does not exist at this line |
| `app/core/queue.py:239` | Unused function `get_enrichment_job()` | A | Vulture 60% | Re-tiered: pre-flagged missing implementation (Tier B, per plan §1.81-88). Referenced in tests. |
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

| File:Line | Description | Tier | Reasoning |
|-----------|-------------|------|-----------|
| `app/services/lead_service.py:13` | `widget_service` imported but unused — indicates incomplete refactor or dead code path | B | Import exists but service never calls widget_service; `submit_lead` uses `embed_service.get_widget_config` instead. Plan §6 expects widget validation via embed_service, so this is a stale import, not a missing call. Still a bug (unused import that suggests intent). |
| `app/routers/leads.py:296-313` | `re_enrich_lead` directly accesses `lead_service._get_or_create_repo()` (private) and `repo.get_by_id` | B | Router reaches into service private method `_get_or_create_repo()` and repository directly — violates layer separation (router → service → repo). Should delegate to a public service method. |
| `app/services/lead_service.py:96-106` | Widget existence check uses `embed_service.get_widget_config` which returns config dict, not widget model | B | Per plan §5.3, widget lookup should use `widget_service.get_widget` for ownership/tenant check. Current code bypasses tenant isolation — `embed_service.get_widget_config` doesn't verify `tenant_id`. This is a security boundary violation (tenant isolation). |
| `app/services/lead_service.py:160-161` | `tenant_id` derived from `embed_service.get_raw_widget` instead of authenticated context | B | Lead submission is public (no auth), but `tenant_id` is taken from widget record. If widget lookup is compromised, leads could be attributed to wrong tenant. Should be fine for public submit, but `get_leads`/`get_all_leads` in router correctly use `user["id"]` as `tenant_id`. Inconsistent pattern. |
| `app/services/lead_service.py:296` | `_get_or_create_repo()` uses global `_repo` singleton — not request-scoped, breaks test isolation | B | Global mutable state; tests cannot inject mock repo. Plan §11 (testing strategy) expects dependency injection via protocol. |
| `app/services/widget_service.py:8-29` | `PostgresWidgetRepository` stub with `NotImplementedError` — incomplete PostgreSQL implementation | B | Plan §3 expects full Postgres support. This stub will crash at runtime if `DATABASE_URL` is set. Tier B because it's a known gap in the implementation plan. |
| `app/repositories/report_repo.py:9-13` | Dual SQLite/Postgres implementation with duplicated SQL — violates DRY | B | Same query logic written twice (lines 55-85 vs 87-109, 111-153 vs 155-187). Should use a common query builder or protocol. |
| `app/services/task_service.py:5-12` | Same dual-repo pattern with `PostgresRepository` / `SqliteRepository` — duplicated in `postgres_repo.py` and `sqlite_repo.py` | B | Three files implement same CRUD interface; violates DRY. Plan §1.1 shows `protocol.py` pattern — should be used consistently. |

### Tier C — Flag Only (Requires Sign-off)

| File:Line | Description | Tier | Reasoning |
|-----------|-------------|------|-----------|
| `app/repositories/protocol.py` | `TaskRepository` protocol exists but `LeadRepository` and `WidgetRepository` don't implement it | C | Plan §1.1 mandates Repository Protocol pattern for all repos. `LeadRepository` and `WidgetRepository` are concrete classes without protocol conformance. Schema change risk if enforced. |
| `app/services/lead_service.py:25-43` | Global `_repo` and `_redis_client` singletons with lazy init | C | Hard to test, global state. Refactor to dependency injection would be a breaking internal change. |
| `app/services/widget_service.py:36-41` | Global `_redis_client` singleton | C | Same as above. |
| `app/dependencies/leads.py:31` | Global `_in_process_limits` dict for in-process rate limiting | C | Not thread-safe across workers; only works for single-process dev. Plan §14.4 says rate limiter fails open on Redis outage — this is the fallback, but global dict is process-local. |
| `app/main.py:81-87` | Wildcard CORS (`allow_origins=["*"]`) on entire app | C | **Intentional per plan §5.5, §8.1** — safe because `POST /submit` is gated by application-layer origin validation. Do not flag as bug. |
| `app/services/lead_service.py:126-138` | Honeypot-triggered leads are stored (not discarded) | C | **Intentional per plan §8.5** — stored with `honeypot_triggered=true`. Do not flag. |
| `app/services/lead_service.py:144-153` | Fingerprint dedup window is 5 minutes (short) | C | **Intentional per plan §8.9** — anti-duplicate, not anti-abuse. Do not flag. |
| `app/services/geo_service.py` (provider order) | Provider chain `ipapi.co → ipinfo.io → ip-api.com` | C | **Intentional per plan §9** — not arbitrary. Do not flag. |
| `app/services/widget_js.py:125` | `render_widget_js` ignores `config` and `js_version` params | C | Template uses only `widget_id`. Config fields (brand_color, button_text, etc.) are fetched at runtime via `/config` endpoint — by design for cache-busting via versioned URL. Intentional per plan §5.4. |
| Naming convention drift: `app/routers/*.py` (no `_router.py` suffix) | All router files lack `_router.py` suffix | C | Plan §2 shows `router.py` under each package. Current flat-folder style uses bare names (`leads.py`, `widgets.py`). Changing would be a large rename — Tier C. |
| Naming convention drift: `app/services/ai_worker.py`, `lead_worker.py`, `report_worker.py` | Worker files in `services/` not `workers/` and lack `_worker.py` suffix consistency | C | Plan §2 shows `worker.py` under `leads/`, `embed/`. Current structure mixes workers in `services/`. |
| Naming convention drift: `app/services/alert.py`, `pdf_generator.py`, `widget_js.py` | Non-standard names in `services/` | C | Should be `alert_service.py`, `pdf_service.py`, `widget_js_service.py` per convention. |
| `app/scrapers/*.py` | Scraper modules don't follow `_service.py` / `_repo.py` convention | C | Plan doesn't specify scraper naming; current names are reasonable. |

---

## Summary Counts by Tier

| Tier | Count |
|------|-------|
| **A** (auto-fixable) | **38** |
| **B** (confirmed bugs) | **7** |
| **C** (flag only) | **14** |

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