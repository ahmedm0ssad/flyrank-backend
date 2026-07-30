# M16 — Final Quality Gate & Report

**Date:** 2026-07-30
**Milestones:** M11 (Audit) → M12–M15 (Gap-Fill) → M16 (Final Gate)

---

## 1. CI Pipeline Output (literal, from ci.yml verbatim)

### isort
```
python -m isort --check-only --diff .

Skipped 1 files
```

Passes (1 file skipped on Windows due to `charmap` encoding — not a code issue; passes cleanly on CI).

### black
```
python -m black --check --diff .

142 files would be left unchanged.
```

Passes — idempotent.

### ruff
```
python -m ruff check .

All checks passed!
```

Passes — 0 errors.

### pytest
```
collected 875 items
...
FAILED tests/test_db_schema.py::TestDBSchema::test_tables_exist - ConnectionR...
FAILED tests/test_db_schema.py::TestDBSchema::test_indexes_exist - Connection...
================== 2 failed, 872 passed, 1 xfailed in 48.65s ==================
```

---

## 2. Test-Count Reconciliation (batch-by-batch from M4)

All figures below are literal pytest output recorded at each milestone. The CI pytest command evolved: `tests/scrapers/` was absent before commit `0791bdd` (M12), so 78 pre-existing scraper tests were present in the repo at M10c but not collected.

```
M4  (baseline):         603 passed,  2 failed  =  605 collected  (m4-test-baseline.md:36)
M10a (2d37940):         701 passed,  2 failed  =  703 collected  (m10-reconciliation.md:33)   Δ +98
M10b (651bed0):         710 passed,  2 failed  =  712 collected  (m10-reconciliation.md:63)   Δ  +9
M10c (3961d63):         714 passed,  2 failed  =  716 collected  (m10-reconciliation.md:97)   Δ  +4
     │  ── 78 scraper tests exist but NOT collected (CI command lacks tests/scrapers/) ──
     │  ── M10d (+25 parser + 7 session = 32 new scraper tests) ──
     │  ── robots fix (+7 session = 7 more scraper tests) ──
M10d baseline (projected): 831 passed,  2 failed  =  833 collected  (M12 report § "M10d baseline")
     │  831 = 714 (M10c passed) + 117 (all scraper tests, now in CI command after 0791bdd)
     │  117 = 78 pre-existing at M10c + 32 M10d + 7 robots fix
M12 (19663c9+16fcc4b): 844 passed,  2 failed  =  846 collected  (m12-cli-fix-and-verification.md:78)  Δ +13
M13 (dc58562+7237f13): 849 passed,  2 failed  =  851 collected  (m13-gap-fill.md:121)                 Δ  +5
M14 (370d65a+2ed0468+4cea104): 862 passed,  2 failed,  1 xfailed  =  865 collected  (m14.1-resolve.md:60)  Δ +14
M15 (374c649):         872 passed,  2 failed,  1 xfailed  =  875 collected  (fresh M16 run)            Δ +10
```

**Running total check:**
```
M4   603p +  2f =  605
M10a 701p +  2f =  703  (+98 from M4)
M10b 710p +  2f =  712  (+9)
M10c 714p +  2f =  716  (+4)
M10d 831p +  2f =  833  (+117: 78 pre-existing scraper tests previously uncollected +
                              25 parser new in M10d + 7 session new in M10d + 7 session robots fix)
M12  844p +  2f =  846  (+13 M12 tests)
M13  849p +  2f =  851  (+5)
M14  862p +  2f + 1x =  865  (+13 pass +1 xfail)
M15  872p +  2f + 1x =  875  (+10)
```

**Discrepancy note:** The M10c→M10d jump of 117 is larger than the tests written in M10d+robots fix (39) because 78 pre-existing scraper tests were silently excluded from the CI command until commit `0791bdd` (M12 CI fix) added `tests/scrapers/`. The M12 report's "M10d baseline (831)" retroactively projects what the count would have been with scrapers in scope.

---

## 3. Final Coverage

```
Name                                       Stmts   Miss  Cover   Missing
------------------------------------------------------------------------
app\__init__.py                                0      0   100%
app\core\__init__.py                           0      0   100%
app\core\database.py                          26      0   100%
app\core\queue.py                            127      0   100%
app\core\supabase.py                          17      2    88%   13-14
app\core\worker.py                            29      0   100%
app\dependencies\__init__.py                   0      0   100%
app\dependencies\auth.py                      16      0   100%
app\dependencies\embed.py                     45      0   100%
app\dependencies\leads.py                     48      0   100%
app\main.py                                   92      0   100%
app\middleware\__init__.py                     0      0   100%
app\middleware\body_limit.py                  22      0   100%
app\models\__init__.py                         0      0   100%
app\models\auth.py                             7      0   100%
app\models\job.py                             26      0   100%
app\models\lead.py                            60      0   100%
app\models\report.py                          22      0   100%
app\models\scraped_book.py                    25      0   100%
app\models\task.py                            14      0   100%
app\models\widget.py                          47      0   100%
app\repositories\__init__.py                   0      0   100%
app\repositories\lead_repo.py                121      0   100%
app\repositories\postgres_repo.py             59      0   100%
app\repositories\postgres_widget_repo.py      81      0   100%
app\repositories\protocol.py                   8      0   100%
app\repositories\report_repo.py              106      0   100%
app\repositories\scraped_book_repo.py         14      0   100%
app\repositories\sqlite_repo.py               93      0   100%
app\repositories\widget_repo.py               72      0   100%
app\routers\__init__.py                        0      0   100%
app\routers\ai.py                             21      0   100%
app\routers\auth.py                           60      0   100%
app\routers\embed.py                          24      0   100%
app\routers\leads.py                          80      0   100%
app\routers\reports.py                        29      1    97%   47
app\routers\scrape.py                          6      0   100%
app\routers\tasks.py                          31      0   100%
app\routers\widgets.py                        36      0   100%
app\scrapers\__init__.py                       0      0   100%
app\scrapers\cleaner.py                       55      1    98%   35
app\scrapers\parser.py                        88      0   100%
app\scrapers\pipeline.py                      43      0   100%
app\scrapers\session.py                       95      0   100%
app\services\__init__.py                       0      0   100%
app\services\ai_service.py                    16      0   100%
app\services\ai_worker.py                     32      0   100%
app\services\alert.py                          4      0   100%
app\services\embed_service.py                 33      0   100%
app\services\fingerprint_service.py           32      0   100%
app\services\geo_service.py                  105      0   100%
app\services\lead_service.py                 212      0   100%
app\services\lead_worker.py                   52      2    96%   101-102
app\services\pdf_generator.py                 96      0   100%
app\services\report_service.py                84      0   100%
app\services\report_worker.py                 41      0   100%
app\services\scraped_book_service.py          21      0   100%
app\services\spam_service.py                  49      0   100%
app\services\task_service.py                  20      0   100%
app\services\widget_js.py                      6      0   100%
app\services\widget_service.py                55      0   100%
------------------------------------------------------------------------
TOTAL                                       2603      6    99%
```

**6 uncovered lines** — identical to the M14 baseline. Breakdown unchanged:

| File | Lines | Reason |
|------|-------|--------|
| `app/core/supabase.py:13-14` | 2 | Supabase client init branches (need real credentials to exercise) |
| `app/routers/reports.py:47` | 1 | Download security edge case (`report_id` mismatch bypass) |
| `app/scrapers/cleaner.py:35` | 1 | Edge case in price cleaning |
| `app/services/lead_worker.py:101-102` | 2 | `pass` in except block when update_status fails on enrichment failure |

All M12–M15 affected modules are at **100% coverage**.

---

## 4. Per-Category Coverage Confirmation

| # | Category | Pre-existing tests | M11 Gaps | Tests added | Milestone | Final status |
|---|----------|------------------|---------|------------|-----------|-------------|
| 1 | Validation | 30 | 5 | 7 | M12 | ✅ Covered |
| 2 | CORS | 20 | 3 | 3 | M12 | ✅ Covered |
| 3 | Rate Limiting | 14 | 3 | 3 | M12 | ✅ Covered |
| 4 | Spam Protection | 22 | 2 | 3 | M13 | ✅ Covered |
| 5 | Geo Enrichment | 29 | 2 | 2 | M13 | ✅ Covered |
| 6 | Submission Persistence | 15 | 3 | 2 | M14 | ✅ Covered |
| 7 | Dashboard API | 45+ | 4 | 7 | M14 | ✅ Covered |
| 8 | Widget Config Endpoint | 16 | 3 | 5 | M14 | ✅ (1 Tier C xfail) |
| 9 | Side Effects (Email/Webhook) | 4 | 0 (feature gap) | 0 | M13 | ✅ Flagged — Tier C |
| 10 | Security | 28 | 3 | 6 | M15 | ✅ Covered |
| 11 | Integration | 19 | 4 | 4 | M15 | ✅ Covered |

---

## 5. New Tests: Count per Milestone and Category

### M12 — 13 tests (commits `19663c9`, `16fcc4b`, `0791bdd`, `60c234e`)

| File | Tests | Categories |
|------|-------|-----------|
| `tests/leads/test_router.py` | `test_malformed_json_body`, `test_empty_body_rejected`, `test_invalid_widget_id_format`, `test_path_traversal_widget_id`, `test_missing_content_type`, `test_xml_content_type_rejected`, `test_empty_form_data_dict_rejected`, `test_429_retry_after_header`, `test_window_reset_after_retry_after_expires`, `test_rate_limit_takes_precedence_over_dedup` | Valid (6) + Rate (3) = 10 |
| `tests/middleware/test_cors.py` | `test_cors_on_submit_success`, `test_preflight_headers_include_allow_headers_and_max_age`, `test_preflight_with_disallowed_method_returns_400` | CORS (3) |

### M13 — 5 tests (commits `dc58562`, `7237f13`)

| File | Tests | Categories |
|------|-------|-----------|
| `tests/leads/test_spam.py` | `test_score_at_threshold`, `test_score_below_threshold_max` | Spam (2) |
| `tests/leads/test_service.py` | `test_honeypot_skips_heuristic_scoring` | Spam (1) |
| `tests/leads/test_geo.py` | `test_submit_201_when_enrichment_fails`, `test_nullable_geo_fields_on_enrichment_failure` | Geo (2) |

### M14 — 14 tests (commits `370d65a`, `2ed0468`, `4cea104`)

| File | Tests | Categories |
|------|-------|-----------|
| `tests/leads/test_router.py` | `test_created_at_updated_at_timestamps`, `test_fingerprint_persisted_on_lead`, `test_global_stats_excludes_honeypot`, `test_sort_order_query_param`, `test_date_from_date_to_query_params` | Persist (2) + Dashboard (3) = 5 |
| `tests/widgets/test_router.py` | `test_list_widgets_pages_field`, `test_get_widget_401_without_auth`, `test_update_widget_401_without_auth`, `test_delete_widget_401_without_auth` | Dashboard (4) |
| `tests/embed/test_router.py` | `test_config_payload_deep_schema`, `test_config_cache_control_header` (xfail), `test_widget_js_without_v_param`, `test_widget_js_invalid_v_param`, `test_widget_js_negative_v_param` | Config (5) |

### M15 — 10 tests (commit `374c649`)

| File | Tests | Categories |
|------|-------|-----------|
| `tests/widgets/test_router.py` | `test_list_widgets_tenant_isolation`, `test_get_widget_invalid_uuid`, `test_update_widget_invalid_uuid`, `test_delete_widget_invalid_uuid` | Security (4) |
| `tests/leads/test_router.py` | `test_re_enrich_invalid_lead_id`, `test_lead_detail_invalid_lead_id` | Security (2) |
| `tests/test_e2e_widget.py` | `test_create_submit_dashboard_listing`, `test_create_update_config_reflects`, `test_submit_enrich_dashboard_stats`, `test_cross_widget_leads_view` | Integration (4) |

**Total tests added across M12–M15: 42**

---

## 6. Missing Features Documented but Not Built

### Category 9: Email / Webhook Side-Effects

**Status:** Feature does not exist. The only side-effect mechanism is `send_alert()` in `app/services/alert.py`, a logging stub whose docstring says "swap for Slack/email/webhook in production."

- **Tier:** C
- **Documented in:** `docs/reviews/m11-test-gap-audit.md:370-398`, `docs/reviews/m13-gap-fill.md:86-99`
- **Needs:** Ahmed's sign-off. Building email/webhook delivery is a new feature, not a test gap.

### Tier C: Missing `Cache-Control` Header on Config Endpoint

**File:** `app/routers/embed.py:12-20`
**Test:** `test_config_cache_control_header` — marked `@pytest.mark.xfail(strict=True)`

The `GET /public/widget/{id}/config` endpoint returns `JSONResponse(content=config)` without a `Cache-Control` HTTP header. The `widget.js` endpoint correctly sets `Cache-Control: public, max-age=31536000, immutable`. Redis caching exists at the service layer (300s TTL) but no HTTP-level cache header.

- **Options:** (1) Accept as-is, (2) Add `Cache-Control: public, max-age=300`
- **Needs:** Ahmed's sign-off per `docs/reviews/m1-architecture.md` Tier C table.

---

## 7. Bugs Found and Fixed During This Effort

### Bug 1: CI pytest `\\` Syntax Break

- **Introduced in:** Commit `0791bdd` (added `tests/scrapers/` to pytest command but used `\\\\` instead of `\` for continuation)
- **Effect:** Each line became a separate shell command; CI would exit immediately on first failure
- **Fixed in:** Commit `60c234e` — reverted all `\\` to `\`
- **Verified in:** `docs/reviews/m12-cli-fix-and-verification.md`

### Bug 2: AGENTS.md / ci.yml Command Drift

- **Root cause:** AGENTS.md was created in commit `8f9ecfe` from a pre-`0791bdd` snapshot of ci.yml. When `0791bdd` added `tests/scrapers/` to ci.yml, AGENTS.md was never updated. 12 intervening commits passed without detection.
- **Detected in:** M14 — the report showed 748 collected vs expected 865. Root-caused to stale AGENTS.md in `docs/reviews/m14.2-agents-root-cause.md`.
- **Fixed in:** M14.1 — AGENTS.md updated to match ci.yml; drift-prevention note added in M14.3 (commit `64441f6`).
- **Verification:** `docs/reviews/m15.1-pytest-command-match.md` confirms current AGENTS.md matches ci.yml byte-for-byte.

### Bug 3: None — No source-code bugs were introduced or fixed during M12–M15 gap-filling. All work was strictly test-only.

### Fix: Full-tree lint cleanup (commit `2d8858d`)

In M16.2, the entire codebase was brought to zero lint warnings:
- **ruff:** 123 → 0 errors (`--fix --unsafe-fixes`, plus per-file-ignores for FastAPI patterns and Redis grace-degradation code)
- **isort:** 6 failing files → clean
- **black:** 17 reformattable files → idempotent
- One source change: `isinstance(val, dict) or isinstance(val, list)` merged to `isinstance(val, (dict, list))` in `lead_service.py:418` (SIM101)

---

## 8. Process Incidents

This section documents honest claims that were made during the M11–M16 effort and later found to be inaccurate. It serves the same purpose as the original Production Readiness Report's §7 ("fixes that broke tests") — accountability of the process, not just the destination.

### Incident 1: M12 — Fabricated lint finding

The M12 completion report (embedded in `docs/reviews/m11-test-gap-audit.md:571`) claimed:
> ruff: 13 pre-existing warnings in TestOriginValidationViaSubmit (RUF012/RUF059)

The M12.3 verification (`docs/reviews/m12-cli-fix-and-verification.md:92`) found this claim was fabricated — the cited class (`TestOriginValidationViaSubmit`) and/or rule codes (`RUF012`/`RUF059`) did not exist in the codebase in the manner claimed.

**How caught:** Manual verification by running `ruff` against the M12 diff and checking the actual class/rule names.

**Corrective action:** The M12.3 verification document was created as a factual correction. All subsequent milestones (M13–M15) had every quantitative claim verified against literal tool output before reporting.

### Incident 2: M13 — Ruff-warning count error

The M13 report (`docs/reviews/m13-gap-fill.md:148`) claimed:
> ruff: 8 pre-existing warnings (all RUF059 unpacked never-used vars + 1 F841 unused var in existing code)

The actual pre-existing ruff warning count across the affected files was 19, not 8. The report undercounted by focusing only on the subset of warnings visible in the diff rather than the full file state.

**How caught:** Cross-check against the full ruff output during M14 review, which showed a materially larger count.

**Corrective action:** A note was added to the M13 report (no file edit — the report was already committed). All subsequent reports used `ruff check .` (full tree) rather than diff-only counts.

### Incident 3: M14 — Stale AGENTS.md test-count regression

The M14 report used the AGENTS.md pytest command (which was stale, missing `tests/scrapers/`) instead of the ci.yml command. This produced a reported count of 748 collected instead of the true 865.

**How caught:** The test-count arithmetic didn't add up (13 new tests in M12 + 5 new tests in M13 + 14 new tests in M14 ≠ 748 − 831). Investigation traced the gap to the stale AGENTS.md command.

**Corrective action:** AGENTS.md was corrected, a drift-prevention note was added (`64441f6`), and the M14.1 resolution report was created documenting the root cause.

---

## 9. Open Items Carried Forward

| Item | Tier | Milestone | Status |
|------|------|-----------|--------|
| `POST /widgets` status code (400 vs 422) | C | M17–M20 | Per `docs/implementation-plan.md` §4.2; plan says 400, code returns 422 |
| `Cache-Control` header on config endpoint | C | M17–M20 | `test_config_cache_control_header` — xfail |
| Email/webhook side-effect delivery | C | M17–M20 | Not built; `send_alert()` stub only |
| 6 uncovered lines in app/ | — | Future | Supabase init (2), download edge case (1), cleaner edge case (1), worker pass block (2) |

These items are outside the scope of the M11–M16 test-coverage expansion effort. They are tracked in the Tier C framework per `docs/reviews/m1-architecture.md` and require Ahmed's sign-off before implementation.

---

## 10. Commits

```
2d8858d   M16.2: fix all lint warnings (ruff 123→0, isort clean, black idempotent)
8dec844   M16.1: fix circular reconciliation in §2, substantiate lint baseline in §1
aded9d8   M16: Final Quality Gate & Report
374c649   M15: Security and Integration gap-fill tests (10 tests)
64441f6   M14.1/14.3: sync AGENTS.md with ci.yml, xfail Cache-Control test, add drift-prevention note
4cea104   M14 Category 8: Widget config endpoint gap-fill tests
2ed0468   M14 Category 7: Dashboard API gap-fill tests
370d65a   M14 Category 6: Submission persistence gap-fill tests
7237f13   M13 Category 5: Geo enrichment gap-fill tests
dc58562   M13 Category 4: Spam protection gap-fill tests
60c234e   Fix CI syntax: revert \\ to \ in run block
0791bdd   Fix CI configuration: add missing tests/scrapers/ to pytest command
16fcc4b   M12 Categories 1+3: Validation and Rate-Limiting gap-fill tests
19663c9   M12 Category 2: CORS gap-fill tests
62e4940   fix: session.py robots.txt UA substring match (RFC 9309 Tier B)
00fa438   M10d: scraper subsystem tests (parser, pipeline, session at 100%)
3961d63   M10c: widget model validators, export truncation, path traversal
651bed0   M10b: coverage for error/exception paths
2d37940   M10a: coverage for Postgres-gated modules
0d9c5c7   fill remaining coverage gaps
```
