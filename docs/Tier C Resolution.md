# Tier C Resolution — Milestone Prompts (M17–M20)

Companion prompts to `docs/reviews/m1-architecture.md`'s Tier C table.
Run in order: **M17 → M18 → M19 → M20**. M17 must run first since it
finalizes the decisions the other three depend on and shrinks the Tier C
list to what's genuinely still open. M20 is deliberately last since it
carries the most structural risk.

Each milestone is independently runnable as its own agent session.

---

## Milestone 17 — Tier C Documentation Closures (no code changes)

```
You are performing Milestone 17 — Tier C Documentation Closures. This
milestone touches ONLY docs/reviews/m1-architecture.md and
docs/implementation-plan.md. Zero source code changes.

Read docs/reviews/m1-architecture.md's full Tier C table first.

Task — resolve the following items by DECISION, not by code change:

1. Formally close these 5 items as "Accepted — intentional design,
   confirmed correct, no further action":
   - Wildcard CORS (main.py:81-87)
   - Honeypot rows stored, not discarded
   - Fingerprint dedup 5-minute window
   - Geo provider order
   - render_widget_js ignoring config/js_version
   For each, add one line stating why it's closed (already documented in
   the table, just add a "STATUS: CLOSED — accepted" marker) so it stops
   reading as an open decision.

2. Resolve the 400 vs 422 status code Tier C item: update
   docs/implementation-plan.md §4.2 (line ~383, POST /widgets), §4.2 PUT
   (line ~399), and §3 (line ~319, POST /public/widget/{id}/submit) to
   specify 422 instead of 400. Add a one-line rationale in the plan: 422
   is the correct semantic code for schema-validation failures (400 is
   for malformed requests), it's FastAPI's own convention, and there are
   no existing external consumers whose contract this would break. Mark
   this Tier C item CLOSED in m1-architecture.md, citing the plan update.
   Do NOT touch any application code or restore the deleted exception
   handler — this is a plan correction, not a code change.

3. Resolve the tenant_id-sourced-from-widget-record Tier C item: mark
   CLOSED — accepted as correct. Rationale: public submit has no
   authenticated context by definition; the widget record is the only
   legitimate source of tenant attribution, and it is already gated by
   origin validation. No code change.

4. Formally REJECT the naming-convention Tier C items (router _router.py
   suffix, workers in services/ vs workers/, non-standard service names)
   as "Won't Fix — no functional benefit, rename risk outweighs value at
   this stage of the project." If desired, note as a follow-up
   suggestion: add a lint/pre-commit convention check for NEW files only,
   going forward — but do not implement this in this milestone.

5. Formally DEFER the dual-repo duplication items (report_repo.py,
   task_service.py/postgres_repo.py/sqlite_repo.py) with an explicit
   trigger condition: "Defer until a third repository requires dual
   SQLite/Postgres support — building a shared query abstraction for
   two instances is premature generalization."

Update the Tier C summary count table to reflect: 5 closed-accepted,
1 closed-via-plan-update (400/422), 1 closed-accepted (tenant_id),
4 rejected (naming), 2 deferred (dual-repo). Remaining genuinely open
Tier C items after this milestone: re-enrich race condition, repository
protocol conformance, global singletons, in-process rate-limit dict
growth — these carry forward to M18-M20.

Follow the AGENTS.md pre-commit guardrail. One commit for the plan
update, one commit for the m1-architecture.md updates.

Report back: git show --stat for both commits, and the updated Tier C
summary counts.
```

---

## Milestone 18 — Fix Re-Enrich Race Condition (Tier B, approved)

```
You are performing Milestone 18 — Fix Re-Enrich Race Condition. This
resolves the Tier C item in docs/reviews/m1-architecture.md describing
the race between create_enrichment_job() enqueue and the worker setting
lead.status='pending', which allows duplicate enrichment jobs. This has
been approved for a fix using option (a): a Redis lead_id → job_id
mapping.

SCOPE: touch ONLY app/core/queue.py, app/services/lead_service.py (the
re_enrich_lead path), and their tests. Nothing else.

Task:
1. In create_enrichment_job() (app/core/queue.py), after enqueuing,
   store a Redis key `enrichment:active:{lead_id}` → job_id, with TTL
   matching the existing job timeout (600s per the Agent Guide).
2. In lead_service.re_enrich_lead(), before the existing DB-status check
   (lead.status in ("enriched", "pending")), also check whether
   `enrichment:active:{lead_id}` exists in Redis. If it does, return 409
   regardless of DB status — this closes the window between enqueue and
   the worker's DB write.
3. Clear the `enrichment:active:{lead_id}` key when the worker completes
   (success or final failure) in run_enrichment_job(), so a genuinely
   completed/failed lead can be re-enriched afterward.
4. Add regression tests:
   - Simulate the race: call create_enrichment_job() without yet
     updating lead.status, then call re_enrich_lead() — assert 409.
   - Confirm re_enrich_lead() still returns 202 for a lead with no
     active Redis key and status='failed' (the normal happy path).
   - Confirm the Redis key is cleared after the worker completes, and a
     subsequent re-enrich attempt on a truly failed lead succeeds.

HARD RULES (carried from this project's established process):
- One commit for the fix, a separate commit for tests if large.
- Follow the AGENTS.md pre-commit guardrail (git status / git diff
  --cached --stat) before each commit.
- Run the full test suite; paste literal pytest output (not paraphrased)
  — this project has had repeated issues with unverified/incomplete test
  counts, confirm your command matches the current .github/workflows/ci.yml
  exactly (read it fresh, don't rely on memory or a prior report).
- Verify every specific claim (line numbers, key names, test counts)
  against actual output before stating it.

Update docs/reviews/m1-architecture.md: move this item from Tier C to
"Fixed in commit <hash>", citing the approach and the tests added.

Report back: commit hashes with --stat, the literal test output, and
confirmation of the current ci.yml command used.
```

---

## Milestone 19 — Repository Protocols + Bounded Rate-Limit Dict

```
You are performing Milestone 19 — Repository Protocols and Bounded
In-Process Rate Limiter. Two independent, approved fixes bundled because
both are small and additive.

## Part 1 — Repository Protocols

SCOPE: app/repositories/protocol.py, app/repositories/lead_repo.py,
app/repositories/widget_repo.py, app/repositories/postgres_widget_repo.py.

Do NOT force LeadRepository/WidgetRepository to implement the existing
TaskRepository protocol — they have genuinely different shapes. Instead:
1. Define two NEW protocols in app/repositories/protocol.py:
   LeadRepositoryProtocol and WidgetRepositoryProtocol, matching the
   actual public methods already implemented by LeadRepository and
   WidgetRepository (create, get_by_id, list_by_*, update, delete, etc.
   — introspect the current classes, don't guess signatures).
2. Add `class LeadRepository(LeadRepositoryProtocol):` /
   `class WidgetRepository(WidgetRepositoryProtocol):` — this should be
   a pure typing addition; if any method signature genuinely doesn't
   match, do NOT change the implementation to fit the protocol — instead
   adjust the protocol definition to match the real implementation. The
   protocol must describe reality, not prescribe a change to it.
3. Same for PostgresWidgetRepository conforming to WidgetRepositoryProtocol.
4. Add a test that asserts each concrete class satisfies its protocol
   (e.g. via `isinstance(repo, LeadRepositoryProtocol)` with
   `@runtime_checkable`, or a static typing check if the project uses one).

## Part 2 — Bounded In-Process Rate Limiter

SCOPE: app/dependencies/leads.py only.

The `_in_process_limits` global dict (used as the Redis-outage fail-open
fallback per plan §14.4 — do NOT change the fail-open behavior itself)
currently grows unbounded during a sustained Redis outage, keyed by
IP+widget+endpoint with no eviction.

Task: add a bound — either a max-size cap with LRU-style eviction of the
oldest entries, or a periodic sweep removing entries older than the rate
limit window (60s). Choose whichever is simpler given the existing code
structure; do not over-engineer this into a new caching library
dependency. Add a test simulating many distinct IP/widget keys under
fail-open mode and asserting the dict does not grow past the chosen
bound.

HARD RULES:
- One commit for Part 1, one commit for Part 2 — do not bundle them
  together even though they're in the same milestone.
- Do not change the fail-open behavior itself (plan §14.4, intentional).
- AGENTS.md pre-commit guardrail before each commit.
- Run the full test suite using the CURRENT .github/workflows/ci.yml
  command (read it fresh). Paste literal output.
- Verify every specific claim against actual output before stating it.

Update docs/reviews/m1-architecture.md: mark the repository-protocol
Tier C item "Fixed in commit <hash>", and add the in-process rate-limit
bound as a newly-fixed item (it wasn't separately tracked before — add
it to the findings table as Tier C→Fixed with a one-line description).

Report back: commit hashes with --stat for both parts, literal test
output, confirmation the fail-open behavior itself is unchanged.
```

---

## Milestone 20 — Singleton → Dependency Injection Refactor (own milestone, larger scope)

```
You are performing Milestone 20 — Singleton to DI Refactor. This is a
larger, approved refactor — treat it with more caution than M18/M19.
Read docs/reviews/m1-architecture.md's global-singleton Tier C items
first (lead_service.py:25-43, widget_service.py:36-41).

SCOPE: app/services/lead_service.py, app/services/widget_service.py,
app/routers/leads.py, app/routers/widgets.py, and their dependency
wiring. Do not touch anything else.

Context: M7 already added an optional `repo` parameter to
_get_or_create_repo() for test injection, but production code paths
still default to module-level `_repo`/`_redis_client` globals. This
milestone replaces the global-singleton pattern with FastAPI's
Depends()-based dependency injection (or `functools.lru_cache`-wrapped
factory functions if that's a better fit for this codebase's existing
conventions — check how app/dependencies/auth.py already does DI for
get_current_user and follow the same pattern for consistency).

Task:
1. Convert the module-level `_repo`/`_redis_client` singletons in
   lead_service.py and widget_service.py into dependency-provider
   functions usable via FastAPI's Depends().
2. Update the router signatures in leads.py and widgets.py to accept
   these as injected dependencies rather than calling module-level
   getter functions internally.
3. Preserve existing external behavior exactly — this is a structural
   change only, no behavior change. Existing tests should continue to
   pass without modification wherever they test behavior; ONLY tests
   that directly assert on the internal singleton mechanism (if any)
   should need updating, and those updates should be minimal.
4. This is a genuine refactor with real blast radius across two router
   modules — go module by module. Do lead_service.py + leads.py first as
   one logical commit, run the full suite, confirm green, THEN do
   widget_service.py + widgets.py as a second commit. Do not do both at
   once.
5. If at any point a test breaks in a way that suggests the refactor
   changed real behavior (not just the injection mechanism), STOP —
   revert that specific change and report it rather than forcing a test
   update to match new behavior.

HARD RULES:
- Two commits, strictly sequenced as described above (lead path, then
  widget path), each with its own full-suite verification before moving
  to the next.
- AGENTS.md pre-commit guardrail before each commit — this is exactly
  the kind of larger commit where scope creep has bitten this project
  before (see 2715feb's history). Check git diff --cached --stat
  carefully.
- Run the full test suite using the CURRENT .github/workflows/ci.yml
  command (read it fresh, do not assume it matches an earlier report in
  this conversation). Paste literal output after EACH commit, not just
  at the end.
- Verify every specific claim against actual output.

Update docs/reviews/m1-architecture.md: mark both global-singleton Tier
C items "Fixed in commit <hash1>/<hash2>", describing the DI pattern
adopted and citing app/dependencies/auth.py as the precedent followed.

Report back: both commit hashes with --stat, literal test output after
each commit, and confirmation no behavior changed (only the injection
mechanism).
```

---

## Recommended order and rationale

| Order | Milestone | Why here |
|---|---|---|
| 1 | M17 | Zero code risk (docs only); finalizes decisions M18-M20 build on; shrinks the Tier C list immediately |
| 2 | M18 | Small, additive, closes a real (if minor) production hardening gap |
| 3 | M19 | Small, additive, no behavior change to existing fail-open design |
| 4 | M20 | Largest blast radius — run last, once the other three are verified and merged |

After M20, the only Tier C items that should remain open are the ones
explicitly deferred (dual-repo dedup) or rejected (naming conventions) in
M17 — both intentionally left as-is, not oversights.rgest blast radius — run last, once the other three are verified and merged |

After M20, the only Tier C items that should remain open are the ones
explicitly deferred (dual-repo dedup) or rejected (naming conventions) in
M17 — both intentionally left as-is, not oversights.