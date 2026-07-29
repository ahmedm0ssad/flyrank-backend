# Milestone 5 — Documentation Audit

## M6 Fix Status

No Tier A findings in this report. All items are Tier B (`IPINFO_TOKEN` missing from `.env.example`) or Tier C (README gaps, OpenAPI descriptions). No changes applied.

## Findings List

| # | File | Description | Tier |
|---|------|-------------|------|
| 1 | `README.md:68-76` | **README missing widget/lead/embed endpoints** — The "API Endpoints" table (§109-159) lists only tasks, auth, scraper, AI, and reports. It omits all widget CRUD (`GET/POST/PUT/DELETE /widgets`), embed endpoints (`GET /public/widget/{id}/config`, `GET /public/widget/{id}/widget.js`), lead submission (`POST /public/widget/{id}/submit`), lead dashboard endpoints (`GET /widgets/{id}/leads`, `GET /widgets/{id}/leads/{id}`, `GET /widgets/{id}/stats`, `GET /widgets/{id}/export`, `POST /widgets/{id}/leads/{id}/re-enrich`, `DELETE /widgets/{id}/leads/{id}`, `POST /widgets/{id}/leads/batch-delete`), cross-widget endpoints (`GET /leads`, `GET /leads/stats`). | C |
| 2 | `.env.example:1-7` | **Missing `IPINFO_TOKEN`** — `app/services/geo_service.py:70` reads `IPINFO_TOKEN` via `os.getenv("IPINFO_TOKEN", "")` but this variable is not listed in `.env.example`. Anyone setting up from the example will silently skip the ipinfo.io geo provider, degrading enrichment reliability. | B |
| 3 | `README.md:88-105` | **Docker Redis port mismatch** — README §"Starting the AI Worker" (line 98) instructs `docker run -d -p 6379:6379 redis:7-alpine` and the env-var table shows `REDIS_URL=redis://host:6379/0`. However, the Docker Compose stack maps Redis to host port **6380** (per AGENTS.md ground truth). Manual and Docker paths disagree; users following the README will fail to connect to the compose-managed Redis. | C |
| 4 | `README.md:213-255` | **Project Structure section is stale** — Lists files at `app/` root (`database.py`, `queue.py`, `worker.py`, `supabase_client.py`) that actually live in `app/core/`. Omits `app/core/` entirely, plus all new modules: `app/models/lead.py`, `app/models/widget.py`, `app/routers/embed.py`, `app/routers/leads.py`, `app/routers/widgets.py`, `app/services/lead_service.py`, `app/services/embed_service.py`, `app/services/widget_service.py`, `app/services/geo_service.py`, `app/services/spam_service.py`, `app/services/fingerprint_service.py`, `app/services/lead_worker.py`, `app/services/widget_js.py`, `app/repositories/lead_repo.py`, `app/repositories/widget_repo.py`, `app/repositories/postgres_widget_repo.py`, `app/dependencies/embed.py`, `app/dependencies/leads.py`, `app/core/supabase.py`, `app/core/worker.py`, `app/middleware/body_limit.py`. | C |
| 5 | `README.md:160-209` | **Missing architecture sections for widget/lead pipeline** — README has architecture sections for AI Jobs (§160-188) and PDF Report Generation (§191-209) but nothing describing the widget submission pipeline, geo enrichment, spam detection, or honeypot system. These are substantial features with no architectural documentation for new contributors. | C |
| 6 | `app/routers/embed.py`, `app/routers/leads.py`, `app/routers/widgets.py` (all routes) | **No OpenAPI descriptions on any new endpoint** — None of the 15+ widget/lead/embed routes carry `description=`, `summary=`, or docstrings. The `/docs` OpenAPI UI shows bare function names and Pydantic schemas with no endpoint-level explanations. | C |
| 7 | `docs/implementation-plan.md:62-119` (§2) | **Folder structure spec does not match actual flat layout** — The plan describes `app/embed/`, `app/leads/`, `app/widgets/` sub-packages with separate `router.py`, `service.py`, `models.py`, `repository.py` inside each. The actual code uses a flat layer-per-type layout: `app/routers/embed.py`, `app/services/embed_service.py`, `app/models/lead.py`, etc. Also `app/middleware/cors.py` does not exist (CORS is configured inline in `app/main.py`; the matching test `tests/middleware/test_cors.py` does exist). This is a spec-to-implementation drift, not user-facing, but it will confuse anyone cross-referencing the plan against the codebase. | C |
| 8 | `README.md:213-255` | **Missing `app/middleware/` and `app/core/` in project tree** — The `middleware/` directory (contains `body_limit.py`) and `core/` directory (contains `database.py`, `queue.py`, `worker.py`, `supabase.py`) are not listed at all in the project structure tree. | C |

---

## Documentation Score

**Score: 4 / 10**

### Evidence

**Strengths (what's correct):**
- `.env.example` lists 6 of the 7 code-referenced env vars (missing only `IPINFO_TOKEN`).
- README installation instructions (`pip install -r requirements.txt` and `uvicorn app.main:app --reload`) are correct and match the current codebase.
- The "Testing" section accurately references `pytest` and lists working test paths.
- Supabase authentication requirements and known limitations are well documented.
- The AI/PDF background-job architecture sections are accurate for their respective domains.

**Weaknesses (what's wrong):**
- **Severely incomplete endpoint documentation**: The README covers only ~40% of the API surface. The entire widget/lead/embed feature set — the core of the recent v2 work — has zero user-facing endpoint documentation.
- **Stale project structure**: The directory tree § in the README references an older layout (`app/database.py`, `app/queue.py`, `app/supabase_client.py`) that hasn't existed since the `app/core/` refactor. New modules are absent.
- **Missing env var**: `IPINFO_TOKEN` is consumed by `geo_service.py` but absent from `.env.example` — a setup-completeness gap.
- **Port inconsistency**: README documents Redis on port 6379 but Docker Compose uses 6380, creating a "works-on-my-machine" class of setup failure.
- **Zero OpenAPI descriptions**: All new routes appear as bare names in Swagger UI with no endpoint descriptions.
- **No architecture docs for the new lead-capture pipeline**: Unlike AI jobs and PDF reports, none of the submission pipeline, enrichment, or security systems (rate limiting, origin validation, honeypot, fingerprint dedup) are documented in the README.

The documentation is functional for the pre-v2 feature set but has not been updated to reflect the substantial widget/lead/embed feature additions. A reader relying solely on the README or OpenAPI docs would not know these features exist or how to use them.
