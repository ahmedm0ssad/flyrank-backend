# M19 Verification Close-Out

## Item 1 — LRU Verification

**Direct answer:** The code BEFORE the fix did NOT reorder on every access. `OrderedDict.__setitem__` (i.e. `d[key] = value`) preserves an existing key's position — only `move_to_end()` explicitly moves it. The eviction was FIFO-by-creation-time.

**Fix applied in commit `2f6ce6a`** — added `_in_process_limits.move_to_end(key)` at line 47, immediately after the reassignment and before the early-return:

```python
# leads.py:43-50
for key, limit in keys_and_limits:
    timestamps = _in_process_limits.get(key, [])
    timestamps = [t for t in timestamps if now - t < window]
    _in_process_limits[key] = timestamps
    _in_process_limits.move_to_end(key)         # ← added
    if len(timestamps) >= limit:
        return window
    timestamps.append(now)
```

This fires on every single request through the in-process path, whether the IP is under its limit (normal pass) or over it (early return). Even a rate-limited IP has its keys moved to end on every blocked attempt.

**General-case test added** — `test_lru_recent_access_survives_eviction`:
1. Create key A early (inserted first → oldest)
2. Fill the bound-12 dict to capacity with 3 other callers (9 keys)
3. **Access key A again** — `move_to_end` moves it to the protected end
4. Flood with 2 more callers (6 keys) → eviction kicks out the 11 oldest entries
5. Assert key A still has its accumulated count: 2 existing + 28 loop calls = 30 reach the widget_ip limit; the 31st call is blocked

This proves A survived not because of creation order, but because of the explicit `move_to_end` on re-access.

`test_over_limit_ip_stays_blocked_after_lru_eviction` still passes and demonstrates the same mechanism — the victim's keys were re-accessed on every blocked call and survived.

---

## Item 2 — Process-Local Limits Closed

**Chosen: Option (a).** The in-process fallback being single-process-local is an inherent consequence of using an in-process dict as the Redis-outage fallback. M17 already closed the fail-open behavior itself as intentional per plan §14.4. No milestone has scoped moving it to shared storage. Closed as "Accepted — intentional, inherent to fail-open design (plan §14.4), no further action."

**Commit:** `6345dd1`

**Pre-commit guardrail:**
```
git status → only docs/reviews/m1-architecture.md staged
git diff --cached --stat → 1 file changed, 2 insertions(+), 2 deletions(-)
```

**Before (line 101):**
```
| `app/dependencies/leads.py:31` | Global `_in_process_limits` dict for in-process rate limiting | C | Not thread-safe across workers; only works for single-process dev. Plan §14.4 says rate limiter fails open on Redis outage — this is the fallback, but global dict is process-local. |
```

**After:**
```
| `app/dependencies/leads.py:31` | Global `_in_process_limits` dict for in-process rate limiting | C | **STATUS: CLOSED — accepted, inherent to fail-open design (plan §14.4), no further action.** Being process-local is an inherent consequence of using an in-process dict as the Redis-outage fallback; fixing it would require redesigning where the fallback state lives, which no milestone has scoped. Consistent with M17 closure of the fail-open behavior itself. |
```

**Corrected remaining-open count:** **1** (global singletons `lead_service.py:25-43` / `widget_service.py:36-41`).

---

## Test Suite

Full CI: **887 passed, 2 failed (pre-existing Postgres ConnectionRefused), 1 xfailed, 2629 stmts / 99% coverage. M19 close-out complete.**

## Commit Log

| Hash | Description |
|------|-------------|
| `2f6ce6a` | `move_to_end` on every key access for true LRU eviction |
| `6345dd1` | Close process-local limits as accepted (plan §14.4) |
