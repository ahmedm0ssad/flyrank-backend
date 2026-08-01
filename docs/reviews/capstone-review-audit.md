# Capstone Review — Audit Report (FlyRank Widget Platform)

**Branch audited:** `feature/capstone-submission-pack` (working tree of
`D:\ZC-UST\FlyRank\Backend AI`)
**Audit date:** 2026-08-01
**Auditor:** opencode review pass
**Scope:** Definition-of-Done (§6), acceptance probes (§12), security,
resilience, and rubric scoring. This report is **read-only** — no source files
were modified, no commits were created.

> **Method note.** The capstone brief itself (the source of the §6 checkbox
> list and §12 probes/rubric) is **not present in this repository**. The §6
> checkboxes are reconstructed from `EVIDENCE.md` (which restates them as
> "one proof per Definition-of-Done checkbox") and from the API surface in
> `capstone.yaml` / `docs/implementation-plan.md`. Every conclusion below is
> verified against actual source code and actual tests — not against the
> brief's prose.

---

## 1. Summary verdict

**Verdict: PASS — with one Major gap and five Minor issues.**

The submission is in strong shape: `938 passed`, **100% line coverage** over
`2873` statements, lint/format clean, all 16 reconstructed Definition-of-Done
boxes pass **except one**, and the seven rubric dimensions score 4–5.

**The single Major finding (F1) is that the capstone's headline cross-origin
claim — "the widget renders on a page served from a different origin than your
API" (DoD #6) — is not true of the code as written.** The bundle hardcodes
origin-relative URLs (`/public/widget/...`) for both the config fetch and the
submit POST. On a genuinely second-origin page those requests resolve against
the *page's* origin, not the API, so the documented demo (`customer-site` on
`:5500` against the API on `:8000`) would request `http://localhost:5500/...`
and get a 404, and the widget would silently never render. The automated
"proofs" for this box assert only that the string `"/public/widget/"` appears
in the JS — they assert the buggy pattern rather than exercising a second
origin. See F1 and the DoD table (rows #3, #6, #15).

Beyond that, the engineering is consistent, honest, and well documented:
tenant isolation, HTML escaping, parameterized SQL, secret hygiene, CORS
scoping with application-layer origin validation, a 3-tier rate limiter with a
bounded in-process fallback, a degrade-not-fail geo chain, a fail-open
webhook, and idempotent retrying enrichment jobs are all real, and each is
backed by a passing test.

---

## 2. Definition-of-Done matrix (§6)

Reconstructed from `EVIDENCE.md` (16 checkboxes in 6 groups). Each row: verdict,
the EVIDENCE.md proof, and the code/tests that actually support (or fail) it.

### WIDGET MANAGEMENT

| # | Checkbox | Verdict | Evidence (EVIDENCE.md) | Verified code / tests |
|---|----------|---------|------------------------|------------------------|
| 1 | Authenticated CRUD for widgets; unauthenticated requests rejected | **PASS** | `test_*_401_without_auth` (×5) | Router guards every widget route with `get_current_user` (`app/routers/widgets.py`); 401/201/200/204/404/409/422 all covered in `tests/widgets/test_router.py` |
| 2 | Multi-tenant isolation: tenant A cannot read/modify tenant B's widgets or submissions | **PASS** (see F2) | `test_tenant_isolation_in_list`, `test_tenant_isolation`, `test_get_widget_403_wrong_tenant`, `test_list_widgets_tenant_isolation` | Every repo query scopes `tenant_id` (`app/repositories/widget_repo.py`, `lead_repo.py`, `postgres_widget_repo.py`, `postgres_lead_repo.py`); cross-tenant read returns 404 (leak-safe). `tests/widgets/test_repository.py:249`, `tests/leads/test_repository.py:336` |

### WIDGET DELIVERY

| # | Checkbox | Verdict | Evidence (EVIDENCE.md) | Verified code / tests |
|---|----------|---------|------------------------|------------------------|
| 3 | Embed snippet generated per widget | **PARTIAL** (F5) | `TestGenerateScriptTag::*` | `generate_script_tag` exists and is unit-tested (`app/services/widget_js.py:127`, `tests/embed/test_widget_js.py:31-52`) but has **zero callers in `app/`** — no API endpoint returns the snippet, and its default `base_url=""` output is origin-relative |
| 4 | Public config endpoint: small payload + correct cache headers | **PASS** | `test_config_200`, `test_config_payload_deep_schema`, `test_config_cache_control_header` | `Cache-Control: public, max-age=300` at `app/routers/embed.py:27`; 300s Redis cache in `embed_service.get_widget_config`. Test asserts only presence of `public`/`max-age` (see F3) |
| 5 | Widget JS served as a versioned bundle (new version = new URL / cache-bust) | **PASS** | `test_widget_js_200`, `test_widget_js_caching_headers`, `test_widget_js_without_v_param`, `test_versioned_url_changes_with_version` | `Cache-Control: public, max-age=31536000, immutable` at `app/routers/embed.py:63`; `PUT /widgets/{id}` bumps `js_version` → new `?v=N` URL; 410 after soft-delete (`tests/embed/test_router.py:87-96`) |
| 6 | Widget renders on a page from a different origin than your API | **FAIL** (F1) | `test_widget_js_served` + runtime-config tests + manual demo | Bundle's config/submit URLs are **origin-relative** (`app/services/widget_js.py:3,83`); a second-origin page resolves them against the page origin → 404 → no render. Tests only assert the string appears; no browser/cross-origin test exists. The manual proof (`customer-site` on `:5500`) would fail |
| 7 | Cross-origin submissions work: CORS headers correct, preflight handled | **PASS** | `test_options_preflight` (embed + middleware), `test_preflight_headers_include_allow_headers_and_max_age`, `test_origin_exact_match_accepted` | `CORSMiddleware` `allow_origins=["*"]`, methods `GET/POST/OPTIONS` (`app/main.py`); `POST /submit` adds application-layer origin validation (`app/dependencies/leads.py`) |

### PUBLIC SUBMISSION API

| # | Checkbox | Verdict | Evidence (EVIDENCE.md) | Verified code / tests |
|---|----------|---------|------------------------|------------------------|
| 8 | All input validated; malformed/oversized payloads → 4xx + JSON errors | **PASS** | `test_422_validation_error`, `test_413_payload_too_large`, `test_403_origin_mismatch`, `test_404_widget_not_found`, `test_escapes_html_tags` | Pydantic `LeadSubmit` + `html.escape(quote=True)` (`app/models/lead.py:14`); 50KB `BodyLimitMiddleware`; clean 4xx JSON, never 500. 422 is FastAPI default (was 400 pre-M6 — documented, see §6) |
| 9 | Valid submissions stored safely, linked to correct widget + tenant | **PASS** | `test_201_success`, `test_submit_enrich_dashboard_stats`, `test_fingerprint_persisted_on_lead` | E2E drives create → submit → enrich → read-back asserting `widget_id`/`tenant_id` linkage |
| 10 | Rate limiting per IP and/or widget returns 429 under burst; API keeps serving legitimate traffic | **PASS** | `test_429_rate_limited`, `test_429_retry_after_header`, `test_window_reset_after_retry_after_expires`, `test_rate_limit_takes_precedence_over_dedup` | 3 tiers (global-IP 100 / widget-IP 30 / widget-global 1000 per 60s) at `app/dependencies/leads.py:12-16`, `Retry-After` on 429; bounded in-process LRU fallback when Redis is down (F-pass, §5) |

### ABUSE PROTECTION

| # | Checkbox | Verdict | Evidence (EVIDENCE.md) | Verified code / tests |
|---|----------|---------|------------------------|------------------------|
| 11 | At least one spam-prevention technique demonstrably blocks spam | **PASS** | `test_honeypot_flow`, `test_honeypot_returns_fake_success`, `test_honeypot_branch`, `test_honeypot_skips_dispatch`, `test_url_in_message`, `test_email_blacklist`, `test_threshold_logic_above`, `test_dedup_returns_same_lead_id` | Honeypot (fake success + stored-as-spam) + heuristic scoring (`app/services/spam_service.py`) + SHA-256 fingerprint dedup returning the existing `lead_id` |

### ENRICHMENT & SAFE SIDE EFFECTS

| # | Checkbox | Verdict | Evidence (EVIDENCE.md) | Verified code / tests |
|---|----------|---------|------------------------|------------------------|
| 12 | Geo enrichment fallback chain: provider A down → provider B answers | **PASS** | `test_fallback_to_ipinfo_when_ipapi_fails`, `test_fallback_to_ipapi_com_when_first_two_fail`, `test_provider_order_is_correct`, `test_timeout_on_first_provider_falls_through` | `ipapi.co → ipinfo.io → ip-api.com`, 3s timeout/provider, 24h Redis cache (`app/services/geo_service.py`) |
| 13 | All providers down → submission still succeeds (degrade, never fail) | **PASS** | `test_all_providers_fail_returns_none`, `test_submit_201_when_enrichment_fails`, `test_nullable_geo_fields_on_enrichment_failure` | Submit returns 201 regardless; lead stored with nullable geo, `status="failed"` only after retries exhausted (`app/services/lead_worker.py`) |
| 14 | Failing confirmation email/webhook doesn't prevent storage | **PASS** | `test_webhook_failure_still_201`, `test_webhook_success_still_201`, `test_webhook_failure_still_returns_lead` | `dispatch_webhook` never raises (timeout/DNS/refused/non-2xx all caught), 3s `wait_for`, fire-and-forget after store, strong task reference `_webhook_tasks` (`app/services/webhook_service.py`, `app/services/lead_service.py:34`) |

### TESTS & DOCUMENTATION

| # | Checkbox | Verdict | Evidence (EVIDENCE.md) | Verified code / tests |
|---|----------|---------|------------------------|------------------------|
| 15 | Tests cover CORS preflight, invalid payload, oversized payload, rate limiting, spam control, provider fallback, successful widget rendering | **PARTIAL** (F1) | Scenario→proof table (EVIDENCE.md:253-261) | Six of seven scenarios genuinely pass. "Successful widget rendering" is proven only at the string level (`test_js_references_config_at_runtime`); no test executes the bundle in a browser/second origin, and the bundle actually doesn't work there |
| 16 | README (diagram, setup, API docs) + the five submission-pack files present | **PASS** | `ls` output | `README.md` (diagram + API table), `capstone.yaml`, `EVIDENCE.md`, `BUILDLOG.md`, `.env.example` all present and verified |

**DoD tally: 12 PASS · 2 PARTIAL (#3, #15) · 1 FAIL (#6) · 1 PASS-with-note (#2).**

---

## 3. Acceptance probes (§12) — mapping

The six probes are reconstructed from the six DoD groups (the brief's exact
wording is external to this repo). Each probe maps to tests that are inside
the CI pytest invocation (verified in §7).

| Probe (group) | What it exercises | Covering tests (all in CI path) |
|---|---|---|
| P1 · Widget CRUD + auth | Authenticated CRUD, 401/404/409/422, tenant isolation | `tests/widgets/test_router.py`, `tests/widgets/test_repository.py` |
| P2 · Widget delivery | Config endpoint + cache headers; versioned immutable widget.js | `tests/embed/test_router.py`, `tests/embed/test_widget_js.py`, `tests/services/test_embed_service.py` |
| P3 · Public submission API | Validation/4xx, oversized payload, storage, 3-tier rate limiting | `tests/leads/test_router.py`, `tests/models/test_lead.py`, `tests/middleware/test_body_limit.py` (413 asserted in `test_router.py`) |
| P4 · Abuse protection | Honeypot, heuristic scoring, fingerprint dedup | `tests/leads/test_spam.py`, `tests/leads/test_router.py`, `tests/test_e2e_widget.py` |
| P5 · Enrichment & safe side effects | Geo fallback chain, all-down degrade, fail-open webhook, retry/idempotency | `tests/leads/test_geo.py`, `tests/test_lead_worker.py`, `tests/routers/test_webhook_submit.py`, `tests/leads/test_webhook.py` |
| P6 · Tests & documentation | Full-suite green + submission-pack files | Entire CI invocation (§7) |

---

## 4. Security review

| Item | Verdict | Where | Notes |
|---|---|---|---|
| Tenant isolation | **PASS** | `app/repositories/{widget_repo,lead_repo,postgres_widget_repo,postgres_lead_repo}.py` | `tenant_id` in every `WHERE`; cross-tenant read → 404 (no existence leak); list filtered by tenant |
| Input validation / HTML escaping | **PASS** | `app/models/lead.py:14` | `html.escape(value.strip(), quote=True)`; XSS test `tests/models/test_lead.py`; email/phone format validation; widget.js uses `textContent` for user data (verified in M2 review) |
| CORS | **PASS** (scoped) | `app/main.py` | `allow_origins=["*"]`, methods `GET/POST/OPTIONS`, no credentials; safe because `POST /submit` is gated by application-layer origin validation; documented limitation (`README.md:530-532`) |
| Secret handling | **PASS** | `.gitignore`, `.env.example` | `.env` git-ignored and untracked (`git check-ignore .env` → `.env`); `.env.example` holds placeholders only; `AGENTS.md` warns not to commit `.env` |
| Rate-limit fallback when Redis down | **PASS** | `app/dependencies/leads.py:30-57` | Bounded (10,000-key) LRU in-process fallback; fail-open; tested (`tests/leads/test_rate_limit.py:102`); documented limitation |
| SQL injection | **PASS** | `app/repositories/postgres_lead_repo.py:11,50`; `postgres_widget_repo.py` | Parameterized `$n` asyncpg queries; sort column from `_SORT_WHITELIST`; search fields from constants; batch delete via `id = ANY($1::uuid[])`; no string interpolation of user input |
| Additional | **PASS** | `app/models/widget.py` | `webhook_url` must be HTTPS |

No security **failures** found. All requested items are implemented, tested,
and honestly documented where scoped down.

---

## 5. Resilience review

| Area | Verdict | Evidence |
|---|---|---|
| Geo fallback chain — degrade-not-fail | **PASS** | 3 providers, 3s timeouts, 24h cache; all-down → `None` → lead still stored (201) |
| Fail-open webhook | **PASS** | Never raises; all failure modes caught; fire-and-forget; honeypot/no-URL skip; strong task ref prevents GC mid-flight |
| Enrichment job retries + idempotency | **PASS** | exp backoff 10s→60s→300s, max 3, 600s timeout; `enrichment:active:{lead_id}` key prevents concurrent duplicate jobs; re-enrich returns 409 (`tests/leads/test_service.py:192-219`); "already enriched" skip; active key cleared on success/final-failure, kept on intermediate retry |
| Dedup | **PASS** | SHA-256 fingerprint + Redis 5-min window; returns original `lead_id`; rate limit takes precedence over dedup |
| Rate limiting under Redis outage | **PASS** | Bounded LRU in-process fallback (evicts oldest, capped at 10k keys) |
| Payload guard before parsing | **PASS** | 50KB `BodyLimitMiddleware` runs before body parsing |
| Cache invalidation on update | **PASS** | `widget_service.invalidate_cache` deletes the Redis config key; `js_version` bump produces a new URL so stale `immutable` caches are never served |

---

## 6. Rubric scores (1–5)

| Dimension | Score | Rationale |
|---|---|---|
| Architecture | **5** | Clean layering (routers → services → repositories → models), dependency injection via `Depends` (M20/M21), repository protocols with conformance tests, background workers separated from request path, lifespan-managed init. |
| Correctness | **4** | 938 tests / 100% coverage and every reconstructed acceptance behavior holds in-suite. Deducted one point because the headline cross-origin claim (DoD #6) is not true of the shipped bundle (F1) — the code is internally consistent, but a documented capability does not actually work. |
| Resilience | **5** | Geo degrade-not-fail, fail-open webhook, retry/idempotency for enrichment, fingerprint dedup, and a bounded fail-open rate-limit fallback — each degrade path is explicitly tested. |
| Security | **5** | Tenant isolation, HTML escaping, parameterized SQL, secret hygiene, scoped CORS + application-layer origin validation, rate limiting with fallback. No failures found. |
| AI cost & grounding | **4** | The capstone's request path has **zero** LLM calls — geo and spam are deterministic/heuristic and fully grounded, so marginal AI cost is nil. The only LLM in the repo is the optional Groq job worker (mocked offline when no key), which is a host-repo feature, not part of this capstone's domain. Scored 4 (not 5) only because there is no AI-leveraged feature in the capstone itself to evaluate. |
| Testing | **4** | Exceptional breadth (100% coverage, E2E, failure paths, boundary cases). Deducted one point: DoD #6/#15 "rendering" is not tested at browser or second-origin level, and the tests that claim to prove it assert the buggy URL pattern (F1). |
| Communication | **4** | README, EVIDENCE (one proof per checkbox), BUILDLOG, capstone.yaml, and an extensive M1–M23 review trail are thorough and honest (limitations explicitly documented). Deducted one point for the stale AGENTS.md Tier-C entry (F4) and small EVIDENCE line-ref drift (F3). |

**Weighted verdict: 4.4 / 5.** Passes DoD on 12/16 boxes outright; the two
PARTIAL boxes and the single FAIL all trace back to F1 (cross-origin render).

---

## 7. Findings table

> **Resolution (added by M26, 2026-08-01):** these findings were resolved
> after this audit — see M23 (CI baseline reconciliation,
> `docs/reviews/m23-ci-reconciliation.md`), M24 (F1/F5 fix, commits `33a0e5e`
> and `cdfe4f9`, recorded in `EVIDENCE.md:100-104`), and M25 (final
> verification + closing table, `docs/reviews/m25-final-verification.md`).
> **All F1–F5 are Fixed / Verified-fixed / Closed as of M25 — none remain
> open.**

| ID | Severity | File:Line | Description | Recommendation |
|----|----------|-----------|-------------|----------------|
| F1 | **Major** | `app/services/widget_js.py:3,83,124,128` | Config fetch and submit POST use **origin-relative** URLs (`/public/widget/...`). XHR resolves these against the page origin, so on a second-origin page (`customer-site` on `:5500` vs API on `:8000`) the widget requests `http://localhost:5500/...` → 404 → silent no-render. `render_widget_js` accepts `config`/`js_version` but ignores them; the API base is never injected. The EVIDENCE.md manual proof (DoD #6) would fail, and the tests (`test_widget_js_served`, `test_js_references_config_at_runtime`, `test_client_side_config_url_constructed_at_runtime` — `tests/embed/test_widget_js.py:14-28`) assert only that `"/public/widget/"` appears in the string, i.e. they assert the bug. | Derive the API origin from `document.currentScript.src` inside the IIFE (or inject `base_url` at render time) so config/submit URLs are absolute to the API host. Add a test that executes the bundle against a simulated foreign document origin (jsdom, or a small browser/Playwright check) asserting the rendered config request hits the API host, and a cross-origin submit request. |
| F2 | Minor | `tests/widgets/test_router.py:238` | Test named `test_get_widget_403_wrong_tenant` **asserts 404** (line 243). Code returns 404 for cross-tenant reads (correct, leak-safe), and `docs/implementation-plan.md:401` specifies 403 for "not owner". Behavior is fine; name/plan/doc disagree. | Rename to `test_get_widget_not_found_for_wrong_tenant` or document that cross-tenant reads deliberately return 404. |
| F3 | Minor | `EVIDENCE.md:96,82-83` | Line-ref drift: cites `app/routers/embed.py:54` for the `immutable` header (actual `:63`). Also claims the config cache-control test "asserts `Cache-Control: public, max-age=300`", but `test_config_cache_control_header` only checks `public`/`max-age` presence (`tests/embed/test_router.py:60-67`). The code does return exactly `public, max-age=300` (`embed.py:27`). | Refresh the cited line numbers; soften the prose to "asserts presence of `public` and `max-age`". |
| F4 | Minor | `AGENTS.md:96-99` | AGENTS.md lists "POST /widgets status code" as an **open** Tier C item needing Ahmed's sign-off, but `docs/reviews/m1-architecture.md:113` marks it **CLOSED** (resolved via plan update M17, recorded at `docs/implementation-plan.md:7`). README.md:533-535 and EVIDENCE.md:297-298 document the 422 behavior honestly. Only AGENTS.md is stale. | Update AGENTS.md to mark the item resolved (422, plan updated). |
| F5 | Minor | `app/services/widget_js.py:127-129` | `generate_script_tag` (the "embed snippet") has **zero callers in `app/`** — no endpoint returns it, so a customer can't obtain the snippet from the API (DoD #3 only partially satisfied). Also its default `base_url=""` output is origin-relative (`<script src="/public/widget/...">`), unlike the absolute `http://localhost:8000/...` shown in EVIDENCE.md:67. | Expose the snippet from a widget endpoint (e.g. include in the widget GET response) and default `base_url` to the API's public base, or document that the customer constructs it. |

**Documented-limitations check (honesty).** README.md §Limitations (lines
520-545) and EVIDENCE.md §Honest notes (lines 285-302) candidly cover: the
branch-not-repo deviation, fully-open CORS, the 400→422 status-code change,
process-local rate-limit fallback, and the webhook-instead-of-email side
effect. These are stated, not hidden. The one place the docs over-claim is
DoD #6's render proof (F1) — that claim is made in EVIDENCE.md:99-116, and it
is the single significant honesty gap.

---

## 8. Verified by

All commands run from the repo root on the audited working tree (win32,
Python 3.13.14). Results are reproduced verbatim below.

### isort

```text
$ python -m isort --check-only --diff .
Skipped 1 files
```

### black

```text
$ python -m black --check --diff .
Warning: Python 3.13 cannot parse code formatted for Python 3.15.
         To fix this: run Black with Python 3.15, set --target-version to py313,
         or use --fast to skip the safety check.
         Black's safety check verifies equivalence by parsing the AST, which fails
         when the running Python is older than the target version.
All done!  ✨ 🍰 ✨
154 files would be left unchanged.
```

> The warning is a Black version-safety heuristic, not a check failure;
> `--check --diff` exited clean with all 154 files unchanged.

### ruff

```text
$ python -m ruff check .
All checks passed!
```

### pytest (exact CI / capstone.yaml invocation)

```text
$ python -m pytest tests/embed/ tests/leads/ tests/widgets/ tests/middleware/ \
    tests/models/ tests/repositories/ tests/routers/ tests/scrapers/ \
    tests/services/ tests/test_main.py tests/test_background_jobs.py \
    tests/test_e2e_widget.py tests/test_lead_worker.py tests/test_report_worker.py \
    tests/test_worker.py --ignore=tests/test_e2e.py --ignore=tests/test_ai_e2e.py \
    --cov=app --cov-report=term-missing --tb=short -v

TOTAL                                       2873      0   100%
============================ 938 passed in 46.75s =============================
```

> Every `EVIDENCE.md`-cited test name (68) was confirmed to exist and pass in
> this run. Coverage is 100% of `app/` (2873 statements, 0 missed). This run
> matches EVIDENCE.md's claimed `938 passed / 100%` — the reproduction
> confirms the recorded result (their stated duration, 36.88s, differs from
> this machine's 46.75s; the outcome is identical).

---

## 9. Recommended next actions (for the author, not performed here)

1. **Fix F1** — make the bundle resolve its API base from the script's own
   URL and add a second-origin/browser-level test. This is the only blocker to
   a clean DoD pass.
2. Resolve the doc nits F2–F4 and wire up F5's snippet endpoint.
3. Re-run the §8 commands to confirm green, then (optionally) record the
   re-verification in EVIDENCE.md.

No source files were modified and nothing was committed during this audit.
