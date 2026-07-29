# Production Readiness Review — Implementation Plan

*Companion to `docs/implementation-plan.md` (v2) — this plan governs the
final pre-deployment audit, not new feature work.*

**Why this is split into milestones**: the original single "review
everything, fix everything, iterate until done" prompt has no checkpoints.
Run as one session, an agent either skims everything shallowly or goes deep
on one area and runs out of context before the rest, and "fix as you find"
means schema changes, deletions, and rewrites can happen with nobody
reviewing them until after the fact. This plan breaks the work into 5
independent read-only audits (parallelizable), 2 gated fix passes, and 1
final verification/report milestone — matching the audit-then-fix discipline
already used for M2/M3 in the feature plan.

---

## Table of Contents

1. [Ground Truth & Fix Tiers](#1-ground-truth--fix-tiers)
2. [Review Domains → Milestone Map](#2-review-domains--milestone-map)
3. [Milestones](#3-milestones)
4. [Dependency Graph](#4-dependency-graph)
5. [Git Plan](#5-git-plan)
6. [Final Report Spec](#6-final-report-spec)
7. [Escalation / Stop Conditions](#7-escalation--stop-conditions)

---

## 1. Ground Truth & Fix Tiers

### Ground truth
`docs/implementation-plan.md` (v2) is the spec. Deviation from it is a
candidate bug — cite the section number.

**The following are intentional design decisions from the plan. Any
milestone that flags one of these must mark it "intentional per plan §X,
not a defect" — not fix it:**

- Wildcard CORS (`allow_origins=["*"]`) on public widget endpoints (§5.5,
  §8.1) — safe because `POST /submit` is separately gated by
  application-layer origin validation.
- Honeypot-triggered leads are **stored**, not discarded (§8.5).
- The 3-tier rate limiter **fails open** on Redis outage (§14.4).
- Widget.js cache invalidation is via versioned URL, not a shortened TTL
  (§5.4).
- Geo provider order `ipapi.co → ipinfo.io → ip-api.com` (§9) — deliberate,
  not arbitrary.
- Fingerprint dedup window is a short 5 minutes on purpose — anti-duplicate,
  not anti-abuse (§8.9).

A genuine bug *inside* one of these areas (e.g. the origin check actually
does substring matching instead of exact-hostname matching) is still a real
defect — flag it as such, separately from the list above.

### Repo-verified facts (from the project Agent Guide — treat as ground
truth, not audit targets)

- `.github/workflows/ci.yml` is the source of truth for "passing": order is
  isort → black → ruff → pytest, with an exact test-path invocation that
  **excludes `tests/test_e2e.py` and `tests/test_ai_e2e.py`** (need live
  Supabase/Redis/server) but **includes `tests/test_e2e_widget.py`** — it
  is NOT excluded from CI. Don't conflate the two.
- DB: SQLite by default (no `DATABASE_URL`); Postgres via asyncpg when
  `DATABASE_URL` is set. `widgets`, `leads`, `reports`, `scraped_books`
  require Postgres.
- Auth: the app refuses to start without `SUPABASE_URL` + `SUPABASE_KEY`.
- Redis job-state keys: `job:{id}`, `report_job:{id}`, `enrichment_job:{id}`
  — lifecycle `queued → started → finished/failed`. Retry: 10s → 60s →
  300s, max 3 attempts, job timeout 600s.
- Docker: Redis on host port **6380** (not 6379), Postgres on 5432.
- Ruff has intentional per-file-ignores for `B008` in
  `app/routers/auth.py`, `app/dependencies/auth.py`,
  `app/routers/reports.py` — these are framework quirks (FastAPI
  `Depends()` in defaults), not stray suppressions to clean up.
- **`.env` contains live Supabase and Groq credentials. No milestone may
  print, log, quote, or otherwise reproduce any value from it in a report,
  commit, or anywhere else — confirm presence/hygiene only (is it
  gitignored, does `.env.example` list the same keys without values).**

### Known pre-flagged gaps (verify, don't rediscover from scratch)

Two issues are already known from test references in the Agent Guide.
Confirm and tier them rather than treating them as a fresh find:
- `queue.reset_connection()` is called in tests but does not exist in
  `app/core/queue.py`.
- `queue.get_enrichment_job()` is referenced in tests but not implemented
  in `app/core/queue.py`.

M3 confirms these against current code and tiers them (very likely Tier B
— a missing implementation the tests expect). M7 implements the fix.

### Fix tiers

Every finding from Milestones 1–5 gets sorted into exactly one tier:

- **Tier A — auto-fixable, no approval needed.** Lint/formatting, confirmed
  zero-reference dead code (show the grep), obsolete comments, missing
  tests that only add coverage without touching existing behavior.
- **Tier B — confirmed bug, fix but list explicitly before touching.**
  Unambiguous deviation from a specific plan section (e.g. missing
  `tenant_id` filter, wrong pipeline order, wrong retry intervals). Cite
  the section.
- **Tier C — flag only, never touch without Ahmed's sign-off.** File
  deletion beyond zero-reference dead code, DB schema changes, anything on
  the ground-truth list above, API contract changes (path/status
  code/response shape), README/docs restructuring, CI config changes,
  anything uncertain. Default to this tier when in doubt.

---

## 2. Review Domains → Milestone Map

| Domain (from original review scope) | Milestone |
|---|---|
| Architecture, layering, SOLID, duplication, dead code, unused deps, naming conventions | M1 |
| CORS, auth, tenant isolation, injection classes, secrets, origin validation, honeypot, rate-limit fail-open, fingerprint dedup | M2 |
| N+1 queries, indexes, Redis usage, blocking calls, background job lifecycle, retries, idempotency | M3 |
| Test suite baseline run, coverage gaps, missing edge/failure/race-condition cases | M4 |
| README, API docs, env vars, setup instructions, docs-vs-code drift | M5 |
| Apply Tier A fixes from M1–M5 | M6 |
| Apply Tier B fixes from M1–M5 | M7 |
| Full suite re-run, manual e2e verification, compiled Production Readiness Report, Tier C list for approval | M8 |

---

## 3. Milestones

### Milestone 1 — Architecture & Code Quality Audit (read-only)
**Effort**: 1.5h · **Deliverable**: `docs/reviews/m1-architecture.md`
**Depends on**: nothing

### Milestone 2 — Security Audit (read-only)
**Effort**: 2h · **Deliverable**: `docs/reviews/m2-security.md`
**Depends on**: nothing · **Highest priority milestone in this plan**

### Milestone 3 — Performance & Background Jobs Audit (read-only)
**Effort**: 1.5h · **Deliverable**: `docs/reviews/m3-performance-jobs.md`
**Depends on**: nothing

### Milestone 4 — Test Suite Baseline & Coverage Audit (read-only)
**Effort**: 1h · **Deliverable**: `docs/reviews/m4-test-baseline.md`
**Depends on**: nothing

### Milestone 5 — Documentation Audit (read-only)
**Effort**: 45min · **Deliverable**: `docs/reviews/m5-documentation.md`
**Depends on**: nothing

> **M1–M5 are independent of each other** — all read-only, all only depend
> on repo state. Can run as five parallel sessions.

### Milestone 6 — Apply Tier A Fixes
**Effort**: 1h · **Deliverable**: commits + updated `docs/reviews/*.md`
marking each Tier A item as fixed
**Depends on**: M1–M5 complete

### Milestone 7 — Apply Tier B Fixes
**Effort**: 2h · **Deliverable**: commits + updated `docs/reviews/*.md`
marking each Tier B item as fixed, cited against its plan section
**Depends on**: M1–M5 complete, M6 merged first (fix the easy stuff, commit,
then tackle real bugs on a clean baseline)

### Milestone 8 — Final Verification & Report
**Effort**: 1.5h · **Deliverable**: `docs/PRODUCTION_READINESS_REPORT.md`
**Depends on**: M6, M7 complete

---

## 4. Dependency Graph

```
M1 (Architecture) ─┐
M2 (Security)      ─┤
M3 (Perf/Jobs)      ├─→ M6 (Tier A fixes) ─→ M7 (Tier B fixes) ─→ M8 (Final report)
M4 (Test baseline)  ┤
M5 (Documentation) ─┘
```

---

## 5. Git Plan

Branch: `chore/production-readiness-review` (off the feature branch once
M1–M8 of the feature plan are merged, or off `main` if already merged).

| # | Commit message | Milestone |
|---|---|---|
| 1 | `docs(review): architecture and code quality audit findings` | M1 |
| 2 | `docs(review): security audit findings` | M2 |
| 3 | `docs(review): performance and background job audit findings` | M3 |
| 4 | `docs(review): test suite baseline and coverage audit` | M4 |
| 5 | `docs(review): documentation audit findings` | M5 |
| 6 | `fix: apply tier-A safe fixes (lint, dead code, formatting)` | M6 |
| 7 | `fix: apply tier-B confirmed bug fixes` (one commit per bug if the set is small, or one commit per finding category) | M7 |
| 8 | `docs(review): final production readiness report` | M8 |

No mega-commits. Each Tier B fix should be traceable to a specific finding
in the M1–M5 reports.

---

## 6. Final Report Spec

`docs/PRODUCTION_READINESS_REPORT.md` (produced in M8) must contain:

1. Executive Summary
2. Scores 1–10 (Architecture, Security, Performance, Maintainability, Test
   Quality, Documentation, Overall) — **each with evidence, not a bare
   number**
3. Strengths
4. Tier A fixes applied (list + commit refs)
5. Tier B fixes applied (list + plan section cited + commit refs)
6. **Tier C — flagged, NOT applied, needs Ahmed's approval** (list +
   reasoning per item)
7. Any fix attempted in M6/M7 that broke a test and was reverted, with
   reason
8. Remaining security findings still open
9. Remaining performance findings still open
10. Technical debt
11. Test suite: exact pass/fail counts before (M4 baseline) vs. after
    (M8), coverage % on lead-capture modules
12. Documentation gaps still open
13. Recommended next steps, prioritized

---

## 7. Escalation / Stop Conditions

Any milestone must stop and report back — not guess — if it encounters:

- Anything that would require a DB schema change to fix
- Anything that would delete a file with more than zero references
- Anything on the §1 ground-truth list that looks buggy but the agent isn't
  fully certain is actually a defect vs. a misunderstood design choice
- A fix that breaks a previously-passing test (revert it, don't force it)
- Any change to an existing API's path, status code, or response shape

In all of these cases: flag as Tier C, document the reasoning, move on.