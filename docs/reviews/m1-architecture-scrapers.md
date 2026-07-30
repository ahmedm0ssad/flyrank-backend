# Milestone 1 (Expanded Scope) — Scraper Subsystem Architecture Review

**Context:** This document extends the original M1 architecture review
(`docs/reviews/m1-architecture.md`) to cover the scraper subsystem
(`app/scrapers/*.py`), which was explicitly excluded from the original
review scope per `docs/reviews/m1-architecture.md` note at line 110:
"Plan doesn't specify scraper naming; current names are reasonable" and
`docs/PRODUCTION_READINESS_REPORT.md` §10 ("scrapers not in scope for this
review").

**Reviewed in:** M10d (separate scope expansion). Tests only — no source
changes to `app/scrapers/*`.

---

## Coverage Summary (after M10d tests)

| Module | Stmts | Miss | Cover | Before M10d |
|--------|-------|------|-------|-------------|
| `app/scrapers/parser.py` | 88 | 0 | 100% | 9% |
| `app/scrapers/pipeline.py` | 43 | 0 | 100% | 19% |
| `app/scrapers/session.py` | 93 | 0 | 100% | 26% |
| `app/scrapers/cleaner.py` | 55 | 1 | 98% | 51% |
| **Total scrapers** | **279** | **1** | **99%** | — |

Remaining uncovered: `cleaner.py:35` (`_clean_availability` empty-after-strip
branch — reachable only via input that strips to empty string).

---

## Tier B — Confirmed Bugs

| File:Line | Description | Tier | Reasoning |
|-----------|-------------|------|-----------|
| `app/scrapers/session.py:51` | `RobotsChecker._parse()` uses substring match (`agent.lower() in self._user_agent.lower()`) for user-agent matching instead of exact token matching per RFC 9309. Also, `relevant` flag is never reset on blank lines (group separators), allowing directives to leak across group boundaries. | B | **Violates RFC 9309 (Robots Exclusion Protocol) §2.2.1:** "The robot must use case-insensitive matching to compare the value of the User-agent token with the name of the robot." The `in` operator performs substring matching, causing false positives: `User-agent: Bot` matches `FlyRankBot`, `User-agent: Rank` matches `FlyRankBot`. Additionally, blank lines (group separators per RFC 9309 §2.2) do not reset `relevant`, so orphan directives after a blank line inherit the previous matching section's relevance. Fix: replace `in` with `self._user_agent.lower().startswith(agent.lower())` and reset `relevant = False` on blank lines. | **Fixed in commit `62e4940` — `startswith` token match + blank-line group boundary reset** |

---

## Test Fixtures Created

`tests/fixtures/scraper_html/` — 8 files for realistic DOM-based parser testing:

| File | Purpose |
|------|---------|
| `valid_listing.html` | 3 books with full attributes |
| `listing_with_pagination.html` | 2 books + `<li class="next">` pagination |
| `listing_malformed.html` | 7 edge-case entries (empty href, no anchor, no h3, minimal fields, missing rating/price/availability, no title attr, unmatched rating class) |
| `detail_valid.html` | Full detail page (breadcrumb, table, description, image) |
| `detail_malformed.html` | No h1, no breadcrumb, img without src |
| `robots_disallow_all.txt` | `User-agent: * Disallow: /` |
| `robots_partial.txt` | Multi-agent with specific rules per UA |
| `robots_no_match.txt` | GoogleBot/BingBot only (no match for FlyRankBot) |

---

## Test Counts by Module

| Test file | Tests | Classes added in M10d |
|-----------|-------|-----------------------|
| `tests/scrapers/test_cleaner.py` | 32 | (pre-existing, extended in M10c) |
| `tests/scrapers/test_parser.py` | 43 | `TestParseListingPageEdgeCases`, `TestParseDetailPageEdgeCases`, `TestExtractNextPageUrlEdgeCases` |
| `tests/scrapers/test_pipeline.py` | 6 | (pre-existing, no additions needed — already 100%) |
| `tests/scrapers/test_session.py` | 29 | `TestRobotsCheckerFixtures`, `TestScrapeSessionFixtures` |
| **Total** | **110** | |

---

## Remaining Coverage Gaps (app-wide, 6 lines)

| File:Line | Reason |
|-----------|--------|
| `app/core/supabase.py:13-14` | Subprocess call — only reachable with real Supabase CLI |
| `app/routers/reports.py:47` | Normpath defense-in-depth — Starlette normalizes `..` before routing; unreachable via HTTP |
| `app/scrapers/cleaner.py:35` | `_clean_availability` empty-after-strip branch — edge case only |
| `app/services/lead_worker.py:101-102` | Pre-existing — worker edge case |

---

## Summary

| Tier | Count | Notes |
|------|-------|-------|
| **B** (confirmed bugs) | **1** | `session.py:51` — robots.txt UA substring match (RFC 9309 violation) |
| **C** (flag only) | **0** | No new Tier C items in scraper scope |
