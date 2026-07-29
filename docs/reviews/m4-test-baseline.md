# M4 — Test Baseline (`docs/reviews/m4-test-baseline.md`)

*Milestone 4 of 8 — Production Readiness Review. Read-only audit; fixes in M6.*

## M6 Fix Status

**Tier A items addressed in M6** (`chore/production-readiness-review`):

New test cases added in commit `0d0ec02`:

| # | Missing test | File | Status |
|---|-------------|------|--------|
| 1 | LeadSubmit with `referer` > 500 chars | `tests/leads/test_models.py` | Fixed in commit `0d0ec02` |
| 2 | `form_data` with nested dict (non-string values) rejection | `tests/leads/test_models.py` | Fixed in commit `0d0ec02` |
| 15 | WidgetCreate with `config.fields` containing empty string | `tests/widgets/test_models.py` | Fixed in commit `0d0ec02` |
| 16 | WidgetCreate with `config.fields` > 20 items | `tests/widgets/test_models.py` | Fixed in commit `0d0ec02` |
| 17 | LeadSubmit with `form_data` key containing HTML/script injection | `tests/leads/test_models.py` | Fixed in commit `0d0ec02` |
| 12 | Geo enrichment when Redis cache has stale/malformed JSON | `tests/services/test_geo_service.py` | Fixed in commit `0d0ec02` |
| 13 | `spam_service.check_spam` when `form_data` contains non-string values | `tests/leads/test_spam.py` | Fixed in commit `0d0ec02` |
| 14 | `spam_service.check_spam` when all checks return empty (zero score) | `tests/leads/test_spam.py` | Fixed in commit `0d0ec02` |

**Attempted, reverted:**
- #23 (`_call_with_timeout` when coroutine raises) — reverted because `_call_with_timeout` only catches `asyncio.TimeoutError`, not generic exceptions. Test would fail against current behavior.

---

## 1. Pass / Fail / Skip Counts

| Metric | Value |
|--------|-------|
| Total collected | **605** |
| Passed | **603** |
| Failed | **2** |
| Skipped | **0** |
| Errors | **0** |
| Duration | 156.75s |

### Failed tests (both `tests/test_db_schema.py`)

| Test | Reason |
|------|--------|
| `TestDBSchema::test_tables_exist` | `TimeoutError` — `asyncpg.connect()` to Postgres fails because no local Postgres is running. |
| `TestDBSchema::test_indexes_exist` | Same — both try to connect to `DATABASE_URL` which is unset in test config. |

These are expected failures on this environment (no Postgres). They would also fail in CI unless a Postgres service is configured in the CI workflow.

---

## 2. Coverage per Module

```
Name                                        Stmts   Miss   Cover   Missing
---------------------------------------------------------------------------
app/__init__.py                                 0      0   100%
app/core/__init__.py                            0      0   100%
app/core/database.py                           26     15    42%   15-27, 32-34
app/core/queue.py                             114     19    83%   25-27, 32-34, 39-41, 126, 166-171, 176-178
app/core/supabase.py                           17      5    71%   13-14, 25-27
app/core/worker.py                             31      8    74%   34-35, 41-46, 50
app/dependencies/__init__.py                    0      0   100%
app/dependencies/auth.py                       16      0   100%
app/dependencies/embed.py                      45      6    87%   17-18, 23, 37, 46-47
app/dependencies/leads.py                      49      2    96%   26-27
app/main.py                                    69     27    61%   36-68, 104
app/middleware/__init__.py                      0      0   100%
app/middleware/body_limit.py                   22      1    95%   12
app/models/__init__.py                          0      0   100%
app/models/auth.py                              7      0   100%
app/models/job.py                              26      0   100%
app/models/lead.py                             60      1    98%   29
app/models/report.py                           22      0   100%
app/models/scraped_book.py                     25      0   100%
app/models/task.py                             14      0   100%
app/models/widget.py                           47      2    96%   35, 39
app/repositories/__init__.py                    0      0   100%
app/repositories/lead_repo.py                 121      4    97%   144-145, 222-223
app/repositories/postgres_repo.py              59     11    81%   35-37, 39-41, 88-94
app/repositories/postgres_widget_repo.py       75      1    99%   160
app/repositories/protocol.py                    8      0   100%
app/repositories/report_repo.py               106     38    64%   10, 58-70, 89-97, 120-153
app/repositories/scraped_book_repo.py          14      0   100%
app/repositories/sqlite_repo.py                93      0   100%
app/repositories/widget_repo.py                72      3    96%   100-102
app/routers/__init__.py                         0      0   100%
app/routers/ai.py                              21      0   100%
app/routers/auth.py                            60      8    87%   24, 33, 45, 56-59, 76
app/routers/embed.py                           24      0   100%
app/routers/leads.py                           77      0   100%
app/routers/reports.py                         29      3    90%   40, 47, 58
app/routers/scrape.py                           6      0   100%
app/routers/tasks.py                           31      0   100%
app/routers/widgets.py                         36      0   100%
app/scrapers/__init__.py                        0      0   100%
app/scrapers/cleaner.py                        55     19    65%   13, 17-18, 23, 29, 33-35, 43-44, 55, 57, 59, 61, 77-81
app/scrapers/parser.py                         88     80     9%   18-66, 70-119, 123-131
app/scrapers/pipeline.py                       43     43     0%   1-75
app/scrapers/session.py                        93     93     0%   1-124
app/services/__init__.py                        0      0   100%
app/services/ai_service.py                     16      3    81%   20-26
app/services/ai_worker.py                      32      0   100%
app/services/alert.py                           4      1    75%   11
app/services/embed_service.py                  33      0   100%
app/services/fingerprint_service.py            32      0   100%
app/services/geo_service.py                   105      8    92%   89-91, 115-119
app/services/lead_service.py                  203      8    96%   187-188, 298-300, 321-323
app/services/lead_worker.py                    52      4    92%   31, 57, 101-102
app/services/pdf_generator.py                  96      0   100%
app/services/report_service.py                 84     19    77%   52, 84, 93-103, 125-137, 144-150
app/services/report_worker.py                  41      0   100%
app/services/scraped_book_service.py           21     13    38%   9-34
app/services/spam_service.py                   49      0   100%
app/services/task_service.py                   20      2    90%   6-8
app/services/widget_js.py                       6      0   100%
app/services/widget_service.py                 55      3    95%   8-10, 88
-----------------------------------------------------------------------------
TOTAL                                         2550    450    82%
```

### Lead-capture module detail

| Module | Cover | Missing lines |
|--------|-------|---------------|
| `app/services/lead_service.py` | **96%** | 187-188, 298-300, 321-323 |
| `app/repositories/lead_repo.py` | **97%** | 144-145, 222-223 |
| `app/services/spam_service.py` | **100%** | — |
| `app/services/geo_service.py` | **92%** | 89-91, 115-119 |
| `app/services/fingerprint_service.py` | **100%** | — |
| `app/services/lead_worker.py` | **92%** | 31, 57, 101-102 |
| `app/routers/leads.py` | **100%** | — |
| `app/middleware/body_limit.py` | **95%** | 12 |
| `app/dependencies/leads.py` | **96%** | 26-27 |
| `app/dependencies/embed.py` | **87%** | 17-18, 23, 37, 46-47 |

---

## 3. §11 Test Matrix — Actual vs. Gap

| Category | Path (matrix ∈ actual) | Target | Actual | Gap |
|----------|------------------------|--------|--------|-----|
| Unit — Widget Models | `tests/widgets/test_models.py` | 9 | **10** | +1 (over) |
| Unit — Lead Models | `tests/leads/test_models.py` | 8 | **11** | +3 (over) |
| Unit — Spam | `tests/leads/test_spam.py` | 11 | **9** | **-2** |
| Unit — Geo | `tests/leads/test_geo.py` | 11 | **10** | **-1** |
| Unit — Fingerprint | `tests/leads/test_fingerprint.py` | 6 | **9** | +3 (over) |
| Unit — Widget JS | `tests/embed/test_widget_js.py` | 8 | **9** | +1 (over) |
| Repository — Widgets | `tests/widgets/test_repository.py` | 13 | **18** | +5 (over) |
| Repository — Leads | `tests/leads/test_repository.py` | 15 | **22** | +7 (over) |
| Service — Widgets | `tests/widgets/test_service.py` | 9 | **13** | +4 (over) |
| Service — Leads | `tests/leads/test_service.py` | 13 | **18** | +5 (over) |
| Service — Embed | `tests/embed/test_service.py` | 8 | **6** | **-2** |
| Router — Public | `tests/embed/test_router.py` | 14 | **11** | **-3** |
| Router — Widgets | `tests/widgets/test_router.py` | 15 | **16** | +1 (over) |
| Router — Leads | `tests/leads/test_router.py` | 13 | **39** | +26 (over) |
| Background Jobs | `tests/test_lead_worker.py` | 9 | **10** | +1 (over) |
| Security — CORS | `tests/middleware/test_cors.py` | 9 | **14** | +5 (over) |
| Security — Body Limit | `tests/middleware/test_body_limit.py` | 5 | **5** | 0 |
| Rate Limit | `tests/leads/test_rate_limit.py` | 9 | **10** | +1 (over) |
| Integration | `tests/test_e2e_widget.py` | 7 | **7** | 0 |
| **Total** | | **~175** | **~238** | **+63** |

### Categories below target

| Area | Missing |
|------|---------|
| **Spam (−2)** | No test for `honeypot detection stores row (not discard)` — the spam module `check_spam()` function is tested but the pipeline branch that stores honeypot rows is only tested in `test_e2e_widget.py::test_honeypot_flow`. No unit test verifies the `honeypot.py` → `lead_service.process_submission` path that inserts the row with `honeypot_triggered=true`. No test for `email_blacklist` threshold logic at the boundary (±0.5). |
| **Geo (−1)** | No test for circuit breaker (if implemented per §9). Provider chain fallback is tested, but no test exercises the `asyncio.wait_for` timeout boundary at exactly 3.0s. |
| **Embed Service (−2)** | Missing: snippet generation with version param test (covered in `test_widget_js.py` indirectly but not in the embed service context); no test for `validate_origin` returning `False` when widget config is `None`/missing. |
| **Router — Public (−3)** | Missing: `POST /submit` returning `400` for validation error at the embed router level (covered in `leads/test_router.py` instead); `404` for widget not found; `429` for rate limited; `413` for payload too large. These are all tested via the leads router integration tests, but the embed router itself has no direct `POST /submit` endpoint tests. |

---

## 4. Specific Missing Test Cases (all Tier A)

New tests only add coverage — they never change behavior.

### 4.1 Edge cases

| # | Missing test | File | Where it belongs |
|---|-------------|------|-----------------|
| 1 | LeadSubmit with `referer` > 500 chars | `tests/leads/test_models.py` | Validator boundary |
| 2 | `form_data` with nested dict (non-string values) rejection | `tests/leads/test_models.py` | Type validation |
| 3 | Widget domain with `https://*.co.uk` (multi-part TLD) origin validation | `tests/middleware/test_cors.py` | Wildcard domain edge case |
| 4 | Widget domain with port number origin validation | `tests/middleware/test_cors.py` | Port-stripping in `validate_origin` |
| 5 | `widget.js` with `js_version=0` (edge of valid range) | `tests/embed/test_widget_js.py` | Boundary |
| 6 | `widget.js` with `js_version` very large integer | `tests/embed/test_widget_js.py` | Boundary |

### 4.2 Failure paths

| # | Missing test | File | Where it belongs |
|---|-------------|------|-----------------|
| 7 | `lead_service.submit_lead` with widget config cached but widget hard-deleted (race) | `tests/leads/test_service.py` | Race condition simulation |
| 8 | `lead_service.submit_lead` when `lead_repo.create` raises DB exception | `tests/leads/test_service.py` | DB failure path |
| 9 | `lead_service.submit_lead` when Redis `mark_seen` fails after DB insert | `tests/leads/test_service.py` | Partial failure (lead created but fingerprint not cached) |
| 10 | `lead_service.get_leads` when widget belongs to wrong tenant | `tests/leads/test_service.py` | Tenant isolation |
| 11 | `lead_service.get_widget_stats` with no leads for widget | `tests/leads/test_service.py` | Empty edge case |
| 12 | Geo enrichment when Redis `geo:ip:{ip}` cache has stale/malformed JSON | `tests/services/test_geo_service.py` | Cache corruption |
| 13 | `spam_service.check_spam` when `form_data` contains non-string values | `tests/leads/test_spam.py` | Type safety |
| 14 | `spam_service.check_spam` when all field checks return empty lists (zero score) | `tests/leads/test_spam.py` | Threshold boundary |

### 4.3 Invalid input

| # | Missing test | File | Where it belongs |
|---|-------------|------|-----------------|
| 15 | WidgetCreate with `config.fields` containing empty string | `tests/widgets/test_models.py` | Input validation |
| 16 | WidgetCreate with `config.fields` > 20 items | `tests/widgets/test_models.py` | Max items |
| 17 | LeadSubmit with `form_data` key containing HTML/script injection | `tests/leads/test_models.py` | Injection |
| 18 | `POST /submit` with `Content-Type: application/xml` (not JSON) | `tests/leads/test_router.py` | Content-type enforcement |

### 4.4 Retry logic

| # | Missing test | File | Where it belongs |
|---|-------------|------|-----------------|
| 19 | Enrichment worker retry with `max_attempts` reached, queue depth check | `tests/test_lead_worker.py` | Retry exhaust |
| 20 | `create_enrichment_job` with Redis down at enqueue time | `tests/test_background_jobs.py` | Redis outage |
| 21 | Re-enrich endpoint when lead status is `enriched` (idempotent skip) at router level | `tests/leads/test_router.py` | Idempotency |

### 4.5 Timeout handling

| # | Missing test | File | Where it belongs |
|---|-------------|------|-----------------|
| 22 | Geo provider timeout at exactly 3.0s (granular timeout) | `tests/services/test_geo_service.py` | Timeout boundary |
| 23 | `call_with_timeout` when coroutine raises (not just returns None) | `tests/services/test_geo_service.py` | Exception during timeout |

### 4.6 Race conditions

| # | Missing test | File | Where it belongs |
|---|-------------|------|-----------------|
| 24 | Two concurrent submissions with same fingerprint (before first one caches) | `tests/leads/test_service.py` | Concurrent dedup race |
| 25 | Two concurrent submissions hitting rate limiter simultaneously (both increment before either checks limit) | `tests/leads/test_rate_limit.py` | Race in window counter |

### 4.7 Authorization (missing 401/403 cases)

| # | Missing test | File | Where it belongs |
|---|-------------|------|-----------------|
| 26 | `GET /widgets/{id}/embed` without auth returns 401 | `tests/widgets/test_router.py` | Auth check |
| 27 | `GET /widgets/{id}/copy` without auth returns 401 | `tests/widgets/test_router.py` | Auth check |
| 28 | `POST /widgets/{id}/leads/{lead_id}/re-enrich` without auth returns 401 | `tests/leads/test_router.py` | Auth check |
| 29 | `DELETE /widgets/{id}/leads/{lead_id}` without auth returns 401 | `tests/leads/test_router.py` | Auth check |
| 30 | `POST /widgets/{id}/leads/batch-delete` without auth returns 401 | `tests/leads/test_router.py` | Auth check |
| 31 | `GET /leads` (cross-widget) with wrong tenant returns 403 | `tests/leads/test_router.py` | Tenant isolation |
| 32 | `GET /widgets/{id}/export` without auth returns 401 | `tests/leads/test_router.py` | Auth check |
| 33 | `PUT /widgets/{id}` without auth returns 401 | `tests/widgets/test_router.py` | Auth check |

### 4.8 Rate limiting (all 3 tiers independently, Redis-outage fail-open)

| # | Missing test | File | Where it belongs |
|---|-------------|------|-----------------|
| 34 | Rate limiter returns `Retry-After` header value matching window | `tests/leads/test_rate_limit.py` | Header verification |
| 35 | Rate limiter `global_ip` tier with different IPs (verify independent counting) — existing `test_per_ip_isolation` covers this | — | Covered |
| 36 | Rate limiter `widget_global` tier — when widget_global is exhausted but per-IP is not, only the global limit blocks | `tests/leads/test_rate_limit.py` | Tier independence |
| 37 | Redis-outage fail-open: after Redis returns, the in-process limiter resets correctly | `tests/leads/test_rate_limit.py` | State transition |

### 4.9 CORS (subdomain-suffix bypass, missing Origin)

| # | Missing test | File | Where it belongs |
|---|-------------|------|-----------------|
| 38 | `POST /submit` with `Origin` header matching widget domain exactly but with `http://` (not `https://`) when widget expects `https://` | `tests/middleware/test_cors.py` | Protocol mismatch |
| 39 | `POST /submit` with no `Origin` and no `Referer` header | `tests/middleware/test_cors.py` | Fallback chain |
| 40 | Wildcard `https://*.example.com` matching `sub.sub.example.com` (two levels deep) | `tests/middleware/test_cors.py` | Multi-level subdomain |

---

## 5. Additional Gap: Known Pre-flagged Issues (from Agent Guide)

| Issue | Confirmation | Tier |
|-------|-------------|------|
| `queue.reset_connection()` called in tests but does not exist in `app/core/queue.py` | Confirmed — `tests/test_background_jobs.py` calls it, function missing | **B** (implementation gap) |
| `queue.get_enrichment_job()` referenced in tests but not implemented in `app/core/queue.py` | Confirmed — `tests/test_background_jobs.py` calls it, function missing | **B** (implementation gap) |

---

## 6. Test Quality Score: **7/10**

### Evidence

**Strengths:**
- 603/605 pass (only 2 fail due to missing Postgres, expected)
- 82% overall coverage, 100% on high-value routers (`leads.py`, `embed.py`, `widgets.py`)
- Strong coverage on lead repository (97%), spam service (100%), fingerprint service (100%)
- Rate limiter has Redis-fail-open tests (4 dedicated tests)
- CORS tests are thorough: 14 tests covering exact match, wildcard subdomain, subdomain-suffix bypass, punycode, IDN, port stripping
- E2E widget test covers the full happy path + honeypot + dedup + rate limit + enrichment pipeline (7 tests)
- 238 actual tests vs ~175 target (+63 extra)

**Weaknesses:**
- 2 Postgres-dependent tests will always fail in CI (no Postgres service in workflow — need `services.postgres` in CI)
- Embed router has 11 tests vs 14 target — missing direct `POST /submit` endpoint tests (covered indirectly via leads router)
- Embed service has 6 tests vs 8 target — missing snippet generation with version param and origin validation with None config
- Spam tests at 9 vs 11 target — missing honeypot store-not-discard unit test and email blacklist threshold boundary
- Geo tests at 10 vs 11 — missing circuit breaker and exact timeout boundary
- 40+ specific missing test cases identified (all Tier A)
- Coverage drops below 80% on several modules (database.py 42%, supabase.py 71%, report_repo.py 64%, main.py 61%)
- Scrapers have 0–9% coverage (not in scope for this review, but drags overall number)
- No test marks 2 known missing functions (`reset_connection`, `get_enrichment_job`)

**Conclusion:** Solid baseline with excellent coverage on lead-capture code paths. Gaps are in edge cases, failure paths, auth checks, and a handful of missing unit tests. Tier A additions would bring this to 8–8.5/10. The two known implementation gaps (Tier B) need code fixes before their tests can pass.
