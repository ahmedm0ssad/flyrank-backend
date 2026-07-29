# Production Readiness Review — One Agent Prompt Per Milestone

Companion prompts for `docs/production-readiness-plan.md`. Paste each block
below as a separate agent session, one at a time.

## Setup (do this once)

1. Confirm `docs/production-readiness-plan.md` and `docs/implementation-plan.md`
   (v2) are both present in the repo. Every prompt below references them by
   section number.
2. Create `docs/reviews/` if it doesn't exist — that's where M1–M5 write
   their findings.
3. Work on branch `chore/production-readiness-review`.
4. Run milestones in order: **M1, M2, M3, M4, M5 can run in parallel (five
   separate sessions, or sequentially if you only want one at a time) →
   then M6 → M7 → M8.**
5. Every milestone below is read-only unless explicitly stated otherwise.
   M1–M5 must not modify any file outside `docs/reviews/`.

---

## Milestone 1 — Architecture & Code Quality Audit

```
You are performing Milestone 1 (of 8) of the Production Readiness Review,
specified in docs/production-readiness-plan.md. Read §1 in full before
starting — it defines the fix tiers and the list of intentional design
decisions you must not flag as bugs.

This is a READ-ONLY audit. Do not modify any source file. Your only output
is docs/reviews/m1-architecture.md.

Task — review and document, with file:line evidence for every claim:
- Routers contain no business logic; services contain business logic;
  repositories contain persistence only. List any violation with the
  specific function.
- Circular imports, duplicated abstractions, unnecessary abstractions.
- SOLID violations worth calling out (don't pad the report with trivial
  nitpicks).
- Dead code, unused imports, unused files, unused dependencies in
  requirements/pyproject — for each "unused" claim, show the grep/search
  that proves zero references.
- Duplicated code across modules (e.g. widget vs. lead repository/service
  following inconsistent patterns).
- Naming-convention drift from the established flat-folder style
  (*_service.py, *_repo.py, *_worker.py, *_router.py).
- Stale TODO/FIXME comments, obsolete comments that no longer match the
  code.

For every finding, assign a tier per plan §1 (A/B/C) and state which. If
something looks wrong but matches an item on the plan's intentional-design
list, say so explicitly and do not tier it as a bug.

Deliverable: docs/reviews/m1-architecture.md containing:
- Findings list (file:line, description, tier, reasoning)
- Summary counts by tier
- Architecture score (1-10) with evidence, not just a number

Report back: summary of findings by tier, and the path to the file you
wrote.
```

---

## Milestone 2 — Security Audit

```
You are performing Milestone 2 (of 8) of the Production Readiness Review,
specified in docs/production-readiness-plan.md. Read §1 in full first. This
is the highest-priority milestone in the whole review.

This is a READ-ONLY audit. Do not modify any source file. Your only output
is docs/reviews/m2-security.md.

**Critical safety note before you start**: this repo's .env contains live
Supabase and Groq credentials. Never print, log, quote, paste, or otherwise
reproduce any actual value from .env in your report, in a commit, or in
your output to me. For the secrets-hygiene check, confirm presence and
hygiene only (is .env gitignored, does .env.example list the same key
names without real values) — never the values themselves.

Task — check each of these against the actual running code, not against
what the plan says it should do, and cite file:line for every finding:

1. **Origin validation (docs/implementation-plan.md §8.2) — check this
   first, most carefully, and exhaustively.** Find every place origin/domain
   comparison happens (app/dependencies/embed.py and anywhere it's called
   from). Confirm it parses both values with urlparse and compares
   .hostname exactly (or wildcard-suffix), never a raw string
   .startswith()/substring comparison. If you find the substring bug, this
   is a Tier B finding — the highest-severity one possible in this review.
2. Body-size limit enforced at the ASGI layer before Pydantic parsing
   (§8.6), including behavior when Content-Length is missing or spoofed.
3. Honeypot rows: confirm they are inserted with honeypot_triggered=true,
   never silently dropped (§8.5) — this is intentional-by-design, not a bug,
   if implemented correctly; flag it as a REAL bug only if rows are
   discarded instead.
4. Rate limiting: all 3 tiers present and pipelined into one Redis round
   trip (§8.3); confirm fail-open behavior on Redis outage (§14.4) — this
   is intentional, do NOT flag fail-open itself as a bug, only flag it if
   the code actually fails closed/500s instead.
5. Fingerprint dedup actually wired into the live pipeline, not just
   present as an unused/untested function (§8.9).
6. Tenant isolation — check EVERY query in every widget/lead
   repository/service method individually for a tenant_id filter, not a
   sample. List every method checked, not just the ones with problems.
7. Classic web vulns: SQL injection (parameterized queries everywhere?),
   XSS (form_data rendering, HTML stripping per §8.7), CSRF exposure, SSRF
   (especially in the geo-enrichment provider calls — do they follow
   redirects to internal IPs?), path traversal, unsafe deserialization,
   open redirects, insecure response headers.
8. Secrets: confirm .env is gitignored and was never committed (check git
   history, not just the working tree); confirm .env.example lists the
   same key names as .env without real values; check docker-compose.yml
   and any config file for a hardcoded credential. Report findings without
   reproducing any actual secret value.
9. Auth: confirm get_current_user is actually enforced on every dashboard
   route, not just present in the function signature but bypassed by a
   default or an unguarded early return.

Deliverable: docs/reviews/m2-security.md containing:
- Findings list (file:line, description, tier, plan section cited)
- Explicit confirmation, pass/fail, on each of the 9 items above
- Security score (1-10) with evidence

Report back: summary of findings by tier — especially state clearly whether
the origin-validation substring bug is present or not — and the file path.
```

---

## Milestone 3 — Performance & Background Jobs Audit

```
You are performing Milestone 3 (of 8) of the Production Readiness Review,
specified in docs/production-readiness-plan.md. Read §1 first.

This is a READ-ONLY audit. Do not modify any source file. Your only output
is docs/reviews/m3-performance-jobs.md.

Task:
- N+1 queries in any dashboard list/stats/export endpoint.
- Cross-check db/init.sql's actual indexes against
  docs/implementation-plan.md §3's index list — are they all really
  present, correctly defined (partial indexes where specified, e.g.
  idx_leads_status WHERE status='pending')?
- Anywhere the plan specifies a single pipelined Redis call (§8.3 rate
  limiting) — confirm it's actually one round trip, not N sequential calls.
- Blocking/sync calls inside async request handlers.
- Unbounded or unpaginated queries anywhere in the dashboard endpoints.
- Missing caching where the plan specifies it (widget config 5min TTL,
  geo-by-IP 24h TTL, stats 5min TTL — §5.4, §9, §10.3).
- Background job (enrichment worker) lifecycle: matches
  report_worker.py/ai_worker.py pattern, retry intervals are exactly
  10s/60s/300s per §7, idempotency check on lead.status=='enriched' before
  re-running, alert fires on final failure via app/services/alert.py.
- Geo provider chain: confirm the 3s-per-provider timeout via
  asyncio.wait_for is actually implemented, not just documented, and that
  the 24h cache is checked BEFORE calling any provider, not after.
- Confirm provider order in the actual code is ipapi.co → ipinfo.io →
  ip-api.com per §9 — flag if it's been reordered, since that reordering
  has a specific quota-exhaustion rationale behind it.
- Confirm retry/lifecycle details match the project Agent Guide exactly:
  Redis job-state keys `job:{id}` / `report_job:{id}` /
  `enrichment_job:{id}`, lifecycle `queued → started → finished/failed`,
  backoff 10s → 60s → 300s, max 3 attempts, job timeout 600s.
- **Verify the two known gaps from the Agent Guide against current code**
  (don't skip this — it's a confirm, not a rediscovery): does
  `app/core/queue.py` actually implement `reset_connection()` and
  `get_enrichment_job()`? Tests reference both. If either is genuinely
  missing, this is a Tier B finding — implementation the tests expect but
  the module doesn't provide.

Deliverable: docs/reviews/m3-performance-jobs.md containing:
- Findings list (file:line, description, tier)
- Index audit table: index name from §3 vs. present/missing in db/init.sql
- Explicit pass/fail on the two known-gap items above
- Performance score (1-10) with evidence

Report back: summary of findings by tier, and the file path.
```

---

## Milestone 4 — Test Suite Baseline & Coverage Audit

```
You are performing Milestone 4 (of 8) of the Production Readiness Review,
specified in docs/production-readiness-plan.md. Read §1 first.

This milestone RUNS tests but does not fix anything or write new tests.
Your only file output is docs/reviews/m4-test-baseline.md.

Task:
- Run the exact CI test command from .github/workflows/ci.yml (this is the
  literal command CI uses — use it verbatim, don't approximate with a bare
  `pytest`):

  ```
  python -m pytest \
    tests/embed/ \
    tests/leads/ \
    tests/widgets/ \
    tests/middleware/ \
    tests/models/ \
    tests/repositories/ \
    tests/routers/ \
    tests/services/ \
    tests/test_main.py \
    tests/test_background_jobs.py \
    tests/test_db_schema.py \
    tests/test_e2e_widget.py \
    tests/test_lead_worker.py \
    tests/test_report_worker.py \
    tests/test_worker.py \
    --ignore=tests/test_e2e.py \
    --ignore=tests/test_ai_e2e.py \
    --cov=app --cov-report=term-missing --tb=short -v
  ```

  Note `tests/test_e2e_widget.py` IS part of this run — it is not one of
  the two excluded e2e files. `tests/test_e2e.py` and
  `tests/test_ai_e2e.py` need live Supabase/Redis/server and are always
  excluded from CI; don't try to run them here.
- Report the literal output: total tests, passed, failed, skipped, errors
  — not a paraphrase.
- Report the exact coverage percentage per module from the --cov-report
  output, especially the lead-capture modules (lead_service.py,
  lead_repo.py, spam_service.py, geo_service.py, fingerprint_service.py,
  lead_worker.py, leads router, body_limit middleware).
- Identify SPECIFIC missing test cases (not "needs more tests") in:
  edge cases, failure paths, invalid input, retry logic, timeout handling,
  race conditions (e.g. concurrent submissions hitting the same
  fingerprint), authorization (missing 401/403 cases), rate limiting (all
  3 tiers independently, Redis-outage fail-open), CORS (subdomain-suffix
  bypass attempt, missing Origin on POST).
- Cross-check the ~175-test matrix in docs/implementation-plan.md §11
  against what actually exists — which rows are covered, which are
  missing or thin.

Deliverable: docs/reviews/m4-test-baseline.md containing:
- Exact pass/fail/skip counts (this is the "before" baseline M8 will
  compare against)
- Coverage % per module
- Table: §11 test category vs. actually implemented vs. gap
- List of specific missing test cases, tiered (new tests are always Tier A
  — they only add coverage, never change behavior)
- Test quality score (1-10) with evidence

Report back: the pass/fail baseline numbers and the file path.
```

---

## Milestone 5 — Documentation Audit

```
You are performing Milestone 5 (of 8) of the Production Readiness Review,
specified in docs/production-readiness-plan.md. Read §1 first.

This is a READ-ONLY audit. Do not modify any file. Your only output is
docs/reviews/m5-documentation.md.

Task:
- Does the README's setup/Docker/env-var instructions actually work against
  the current codebase, or reference something stale (old folder
  structure, removed endpoints, wrong env var names)?
- Is API documentation (if any, e.g. OpenAPI descriptions on routes)
  present and accurate for the new widget/lead endpoints?
- Do env vars referenced in code (geo provider tokens, Supabase config,
  Redis/Postgres URLs) all appear in .env.example?
- Any docs that reference the old (pre-audit) widget/embed structure from
  docs/implementation-plan.md §2 that no longer matches the actual flat
  folder layout?
- Project structure section, if present, accurate?

Deliverable: docs/reviews/m5-documentation.md containing:
- Findings list (file, description, tier)
- Documentation score (1-10) with evidence

Report back: summary of findings by tier, and the file path.
```

---

## Milestone 6 — Apply Tier A Fixes

```
You are performing Milestone 6 (of 8) of the Production Readiness Review,
specified in docs/production-readiness-plan.md. Read §1 and §5 in full.
Milestones 1–5 must be complete — read all five docs/reviews/*.md files
before starting.

Task:
- Collect every Tier A finding across all five reports.
- Apply ONLY Tier A fixes: lint/formatting, confirmed zero-reference dead
  code removal, obsolete comment cleanup, and adding new test cases that
  only increase coverage without changing existing behavior.
- Run lint in the exact CI order: `isort --check-only --diff .` →
  `black --check --diff .` → `ruff check .`, then apply the actual
  isort/black/ruff fixes (drop `--check-only`/`--diff` to apply them for
  real). isort profile is `black` — don't fight that in a manual fix.
- Do NOT remove the Ruff per-file-ignores for `B008` in
  `app/routers/auth.py`, `app/dependencies/auth.py`, or
  `app/routers/reports.py` — these are intentional (FastAPI's `Depends()`
  pattern trips B008), not stray suppressions to clean up.
- Do NOT touch anything tiered B or C, even if it looks trivial to you now
  — re-tiering is not your call in this milestone.
- After each logical batch of fixes, run the affected test subset. If
  anything breaks, revert that specific change and note it — don't force
  it through.
- One commit per fix category (formatting, dead code removal, new tests),
  per plan §5's git plan.
- Update each docs/reviews/m*.md file: mark every Tier A item you fixed
  with "Fixed in commit <hash>", and mark anything you attempted but
  reverted with "Attempted, reverted: <reason>".

Deliverables:
- Commits per plan §5 (rows 6 in the commit table)
- Updated docs/reviews/*.md files

Testing:
- Run the full suite after all Tier A fixes are applied. Report exact
  pass/fail counts.

Definition of done:
- [ ] Only Tier A items touched
- [ ] Zero-reference claims verified before any deletion (grep evidence
      preserved in the commit message or PR description)
- [ ] All tests still pass (or reverts documented for ones that didn't)
- [ ] docs/reviews/*.md updated to reflect fix status

Report back: what was fixed, what was reverted and why, final test count.
```

---

## Milestone 7 — Apply Tier B Fixes

```
You are performing Milestone 7 (of 8) of the Production Readiness Review,
specified in docs/production-readiness-plan.md. Read §1 and §5 in full.
Milestone 6 must be merged first — work on top of that clean baseline.

Task:
- Collect every Tier B finding across all five docs/reviews/*.md reports.
- For EACH Tier B item: state the plan section it violates, the current
  buggy behavior, and the fix — before writing any code. Then apply the
  fix.
- Do NOT touch anything tiered C. If a Tier B fix turns out, on closer
  inspection, to actually require a schema change or contract change,
  STOP, re-tier it to C in the relevant docs/reviews/*.md file, and move
  on without applying it.
- Do NOT "fix" anything on the intentional-design list in plan §1 even if
  a Tier B finding references it incorrectly — re-check against §1 before
  touching origin validation, honeypot storage, rate-limit fail-open
  behavior, cache-busting mechanism, geo provider order, or the fingerprint
  window.
- After each fix, run the specific tests covering that code path, then the
  broader suite. Revert and document (don't force) any fix that breaks a
  previously-passing test.
- One commit per fix, or per closely-related group of fixes if the set for
  one finding is large (e.g. the tenant_id sweep across multiple
  repository methods can be one commit).
- Update each docs/reviews/m*.md file: mark every Tier B item "Fixed in
  commit <hash>, plan §X", or "Reverted: <reason>", or "Re-tiered to C:
  <reason>".

Deliverables:
- Commits per plan §5 (row 7)
- Updated docs/reviews/*.md files

Testing:
- Run the full suite after all Tier B fixes are applied. Report exact
  pass/fail counts.

Definition of done:
- [ ] Every Tier B item addressed: fixed, reverted-with-reason, or
      re-tiered to C with reason — none silently skipped
- [ ] No item from the plan §1 intentional-design list was altered
- [ ] All tests pass, or reverts documented
- [ ] docs/reviews/*.md updated

Report back: full list of Tier B items and their outcome (fixed / reverted
/ re-tiered), final test count.
```

---

## Milestone 8 — Final Verification & Report

```
You are performing Milestone 8 (of 8, final) of the Production Readiness
Review, specified in docs/production-readiness-plan.md. Read §6 in full —
it's the exact spec for your output file. Milestones 6 and 7 must be
merged.

Task:
- Run the exact CI command (isort --check-only → black --check → ruff
  check → the full pytest invocation from .github/workflows/ci.yml, same
  one used in Milestone 4) one final time. Compare exact pass/fail counts
  against the Milestone 4 baseline.
- Run coverage again on the lead-capture modules; compare against the M4
  baseline.
- Start Postgres, Redis, API, and worker via `docker compose up --build`.
  Remember Docker Redis is mapped to host port **6380**, not 6379 — use
  that if connecting from outside the compose network. Full-stack
  verification needs `DATABASE_URL` and `SUPABASE_URL`/`SUPABASE_KEY` set
  (the app refuses to start without Supabase config) — use the existing
  .env, but per the credential-safety rule in M2, never print its values.
  Manually verify end-to-end and report the ACTUAL output of each, not
  "verified": widget CRUD, embed config/widget.js delivery, submission
  pipeline (happy path, honeypot path, rate-limited path,
  duplicate/fingerprint path), enrichment worker picking up and completing
  a job, dashboard stats/list/export, authentication on a protected route,
  a live origin-validation-bypass attempt against a lookalike domain
  (confirm it's rejected).
- Compile docs/PRODUCTION_READINESS_REPORT.md per the exact structure in
  plan §6 — pull the Tier C list from all five docs/reviews/*.md files
  into section 6 of the report, since those need Ahmed's explicit
  approval before anyone touches them.
- Do not apply any fixes in this milestone. If the final verification
  surfaces something new, add it to the report as a new finding (tiered),
  do not fix it here.

Deliverable: docs/PRODUCTION_READINESS_REPORT.md per plan §6's structure.

Definition of done:
- [ ] Full suite run, exact before/after counts reported
- [ ] Coverage before/after reported for lead-capture modules
- [ ] All manual e2e flows attempted with real output captured
- [ ] Origin-validation bypass attempt specifically re-verified live,
      not just cited from M2's report
- [ ] Report follows plan §6 structure exactly, including a clearly
      separated Tier C section for Ahmed's approval
- [ ] No fixes applied in this milestone

Report back: the final scores, the before/after test comparison, and the
count of Tier C items awaiting approval.
```