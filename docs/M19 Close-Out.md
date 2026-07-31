# M19 Close-Out — All 4 Items Resolved

## Item 1 — Pre-Commit Guardrail Output

Both captured live in the conversation (not reconstructed). Re-verified via `git show --stat`.

**Commit `c3a96e3`** (Part 1 — Repository Protocols):
```
 app/repositories/lead_repo.py                   |  3 ++-
 app/repositories/postgres_widget_repo.py        |  3 ++-
 app/repositories/protocol.py                    |  8 +++++---
 app/repositories/widget_repo.py                 |  3 ++-
 tests/repositories/test_protocol_conformance.py | 21 +++++++++++++++++++++
 5 files changed, 32 insertions(+), 6 deletions(-)
```
Guardrail: `git status` confirmed only those 5 files staged — no coverage artifacts, no docs, no logs.

**Commit `a7f9ed2`** (Part 2 Correction — LRU eviction, supersedes `7f58e08`):
```
 app/dependencies/leads.py      | 20 ++++++++++++--------
 tests/leads/test_rate_limit.py | 35 ++++++++++++++++++++++++++++++++++-
 2 files changed, 46 insertions(+), 9 deletions(-)
```
Guardrail: `git status` confirmed only those 2 files staged.

(Original `7f58e08` commit's guardrail was also captured live, but its clear-on-overflow approach was superseded by `a7f9ed2`.)

---

## Item 2 — Bounding Strategy: LRU Eviction

**What changed:** `_in_process_limits` is now an `OrderedDict` (was `defaultdict(list)`). On overflow, oldest entries are popped via `popitem(last=False)` — `O(overage)`. The `7f58e08` clear-on-overflow approach is superseded.

**Tradeoff documented inline** in `app/dependencies/leads.py:52-54`:
```python
# LRU eviction: pop oldest entries (insertion order = access order).
# This preserves rate-limit state for recently-active IPs.
```

**Test coverage of the critical scenario:**

| Test | What it proves |
|------|---------------|
| `test_fails_open_and_bounded` | Dict never exceeds `_MAX_IN_PROCESS_KEYS` |
| `test_new_ip_still_rate_limited_after_lru_eviction` | A fresh IP after eviction builds up to its limit correctly |
| `test_over_limit_ip_stays_blocked_after_lru_eviction` | **An IP that was over its limit before eviction stays blocked after** — its per-widget key (`ratelimit:widget_ip:victim:widget-v:submit`, limit 30) was recently accessed and survived eviction; the victim remains rate-limited |

The third test addresses the key concern directly: it blocks `10.0.0.1` on widget `victim-w`, fills the bound-12 dict with other keys past overflow, then asserts the victim is still blocked. The mechanism: the victim's widget-IP limit key (surviving eviction as a recently-accessed entry) still shows count ≥ 30, so `_check_in_process` returns the 60s window immediately.

**Fail-open behavior unchanged:** `test_redis_down_fails_open` and `test_redis_down_in_process_blocks_after_limit` both pass.

---

## Item 3 — Before/After of m1-architecture.md Table Changes

**Repository-protocol row (line 98):**

Before (from `git show da096e8^:docs/reviews/m1-architecture.md`):
```
| `app/repositories/protocol.py` | `TaskRepository` protocol exists but
`LeadRepository` and `WidgetRepository` don't implement it | C | Plan §1.1 mandates
Repository Protocol pattern for all repos. `LeadRepository` and `WidgetRepository`
are concrete classes without protocol conformance. Schema change risk if enforced. |
```

After:
```
| `app/repositories/protocol.py` | `TaskRepository` protocol exists but
`LeadRepository` and `WidgetRepository` don't implement it | C | **FIXED in commit
`c3a96e3`** — renamed to `LeadRepositoryProtocol`/`WidgetRepositoryProtocol` with
`@runtime_checkable`. `LeadRepository`, `WidgetRepository`, and
`PostgresWidgetRepository` now inherit from their respective protocols.
3 conformance tests added. |
```

**Unbounded-growth row (line 102 — new row):**

Not present before (added by M19). After:
```
| `app/dependencies/leads.py:31` | `_in_process_limits` dict grows unbounded
under sustained Redis outage — no eviction mechanism | C | **FIXED in commit
`a7f9ed2`** — added `_MAX_IN_PROCESS_KEYS = 10_000` bound with LRU-oldest eviction
using `OrderedDict`/`popitem(last=False)`. Recently accessed keys survive; the
global reset risk of a full clear is avoided. 3 tests added (bounded dict, fresh-IP
rate limiting after eviction, over-limit IP stays blocked after eviction). |
```

Both rows cite the specific approach taken and the commit hash.

---

## Item 4 — Tier C Count Arithmetic

**Claim from M19 Report: "Tier C count → 20" was wrong.** Correct count is **19**.

| Source | Count |
|--------|-------|
| Tier C table rows (lines 98-113) | 16 |
| Re-tiered from B (in B table, counted in C total): tenant_id (CLOSED), report_repo (DEFERRED), task_service (DEFERRED) | 3 |
| **Total** | **19** |

The original M17/M18 summary said "19" — that count was 15 table rows + 3 re-tiered. M19 adds 1 new table row (unbounded growth), making it 16 + 3 = **19**.

**Remaining open:** 2 items (not 1 as originally claimed):
1. Global singletons (`lead_service.py:25-43`, `widget_service.py:36-41`)
2. Process-local limits (`leads.py:31` — the original finding that the dict is single-process, not the unbounded-growth sub-finding which is now fixed)

Corrected in commit `b057695`.

---

## Test Suite

Full CI command (from `.github/workflows/ci.yml`):
```
python -m pytest tests/embed/ tests/leads/ tests/widgets/ tests/middleware/
tests/models/ tests/repositories/ tests/routers/ tests/scrapers/ tests/services/
tests/test_main.py tests/test_background_jobs.py tests/test_db_schema.py
tests/test_e2e_widget.py tests/test_lead_worker.py tests/test_report_worker.py
tests/test_worker.py --ignore=tests/test_e2e.py --ignore=tests/test_ai_e2e.py
--cov=app --cov-report=term-missing --tb=short -v
```

**Result: 886 passed, 2 failed (pre-existing Postgres ConnectionRefused), 1 xfailed, 2628 stmts / 99% coverage, 0 new uncovered lines. M19 close-out complete.**

## Commit Log

| Hash | Description |
|------|-------------|
| `c3a96e3` | Repository protocols (LeadRepositoryProtocol, WidgetRepositoryProtocol + conformance) |
| `a7f9ed2` | LRU-oldest eviction in fallback dict (supersedes `7f58e08` clear-on-overflow) |
| `b057695` | Correct m1-architecture.md: count 20→19, LRU approach, 2 remaining open items |
