# Verification Follow-Up — Item 1 Reconciliation

## 1. Reconcile the M1 summary against actual git history

### Full commit timeline for `app/core/queue.py` and `tests/test_background_jobs.py`

```
git log --oneline --all --format="%h %ad %s" --date=format:"%Y-%m-%d %H:%M:%S" -- app/core/queue.py tests/test_background_jobs.py
```

```
2715feb 2026-07-29 08:19:19 fix: apply tier-A formatting fixes (isort, black, ruff --fix)
4c494b7 2026-07-26 08:52:23 feat(leads): implement geo enrichment provider chain and RQ worker with re-enrich endpoint
5392970 2026-07-26 07:57:43 feat(leads): implement submission pipeline with body-limit middleware, validation, and spam detection
64b6862 2026-07-26 07:36:55 refactor: flatten widgets/ and embed/ modules into main app structure
bd1ffd0 2026-07-26 01:45:48 test: add comprehensive background job tests
```

### Which commits correspond to the M1 session?

M1 ("Milestone 1 — Architecture & Code Quality Audit") was a **read-only audit**. The M1 review document (`docs/reviews/m1-architecture.md`) was created in commit `86cd95a` (2026-07-29, the HEAD commit) along with M2-M5 docs. It contains no code changes.

The M1 audit was performed on the codebase at a state corresponding to the feature commits from July 26 — specifically the commits up to and including `4c494b7` (where `reset_connection()` and `get_enrichment_job()` were actively implemented). The M1 doc lists these functions as findings at `queue.py:44` and `queue.py:239` respectively, confirming they existed in the codebase when M1 reviewed it.

There is **no code-change commit for M1**. M1 was strictly a read-only review. The review docs were committed as a batch in `86cd95a`.

### Did M1 touch `app/core/queue.py` or `tests/test_background_jobs.py`?

**No.** M1 has no code-commits. Confirmed:

```
git show 86cd95a -- app/core/queue.py tests/test_background_jobs.py
```

Returns nothing (no output). The M1 review doc itself was committed in `86cd95a`, but it only added the markdown file under `docs/reviews/` — it touched neither source nor test files.

### Was the M1 summary's claim accurate?

**No. The claim was inaccurate.**

The M1 summary claimed that `reset_connection()` and `get_enrichment_job()` were "already deleted from queue.py" before M1 touched anything. This is false:

- Both functions were **introduced and fully implemented** in earlier commits:
  - `reset_connection()`: introduced in `6353db0` (2026-07-26), updated in `fb4a1fa` (added `_report_queue`) and `4c494b7` (added `_enrichment_queue`)
  - `get_enrichment_job()`: introduced in `4c494b7` (2026-07-26) with a full implementation body (Redis hgetall, JobResponse construction)

- Both functions were **removed in `2715feb`** (2026-07-29, the M6 formatting commit), **not before M1**.

- M1 was read-only — it never "removed" anything. The M1 doc correctly lists them as findings (unused functions with test references), which is consistent with them still existing in the code at review time.

The claim that they were "already deleted from queue.py" before M1 contradicts the actual git history.

---

## 2. Does the re-enrich endpoint's 409 logic depend on `get_enrichment_job()`?

### Current implementation (`app/services/lead_service.py:436-452`)

```python
async def re_enrich_lead(lead_id: str, widget_id: str, tenant_id: str) -> dict:
    from app.core.queue import create_enrichment_job

    repo = _get_or_create_repo()
    lead = await repo.get_by_id(lead_id)
    if lead is None or str(lead.widget_id) != widget_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    if lead.status in ("enriched", "pending"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lead status is '{lead.status}', can only re-enrich 'failed' leads",
        )

    create_enrichment_job(lead_id)
    return {"status": "re-enqueued", "lead_id": lead_id}
```

### Does it check `get_enrichment_job()` / Redis?

**No.** The 409 check uses only the lead's `status` field from the SQLite/Postgres database. It checks `lead.status in ("enriched", "pending")`. It does **not** call `get_enrichment_job()` or any Redis-based job-status lookup.

Previously, in commit `4c494b7`, the function existed in the router (`app/routers/leads.py`) and called into `lead_service.re_enrich_lead` which also only checked DB status. The `get_enrichment_job()` function was created alongside it but was never wired into the re-enrich logic — it was created as a general-purpose query function for enrichment job status, but the re-enrich endpoint never used it.

### Tests for the 409 case

```python
# tests/leads/test_router.py:176-222

def test_409_if_already_enriched(self, client, created_widget):
    # Sets up a lead with status="enriched"
    resp = client.post(f"/widgets/{created_widget.id}/leads/{lead_id}/re-enrich")
    assert resp.status_code == 409

def test_409_if_in_flight_pending(self, client, created_widget):
    # Sets up a lead with status="pending"
    resp = client.post(f"/widgets/{created_widget.id}/leads/{lead_id}/re-enrich")
    assert resp.status_code == 409
```

**Test run output (current HEAD `86cd95a`):**

```
pytest tests/leads/test_router.py::TestReEnrichLead -v --tb=short
```

```
tests/leads/test_router.py::TestReEnrichLead::test_202_re_enqueues_failed_lead PASSED
tests/leads/test_router.py::TestReEnrichLead::test_409_if_already_enriched   PASSED
tests/leads/test_router.py::TestReEnrichLead::test_409_if_in_flight_pending  PASSED
tests/leads/test_router.py::TestReEnrichLead::test_404_lead_not_found        PASSED
tests/leads/test_router.py::TestReEnrichLead::test_404_widget_not_found      PASSED
```

5/5 passed.

### Is "in-flight" detection actually implemented?

**Partially, via DB status.** The `"pending"` status is designed to represent "in-flight" — it is set when an enrichment job starts. The current implementation detects "in-flight" by checking `lead.status == "pending"`, which is set by the worker when it begins processing.

However, there is a **race-condition gap**: between when `create_enrichment_job()` enqueues the RQ job and when the worker picks it up and sets `lead.status = "pending"`, the lead's DB status is still its previous value (e.g., `"failed"`). If `re_enrich_lead` is called during this window, it would pass the 409 check and create a duplicate enrichment job. This gap is inherent to the DB-status-based approach — a Redis-based job-liveness check via `get_enrichment_job()` could close it, but was never implemented.

The plan (`docs/implementation-plan.md` §10.2 / §4.2) specifies `409` for "already `enriched`/in-progress" without mandating a specific detection mechanism. The current DB-status approach satisfies the spec for the happy path but has the race condition noted above. `get_enrichment_job()` was never used by this endpoint at any point in the codebase's history.

---

## 3. Was there a broken test-suite window between `2715feb` and `0d0ec02`?

### Pre-deletion state

At `2715feb` (the M6 formatting commit), `SPAM_THRESHOLD` was **removed from `app/services/spam_service.py`**:

```bash
git show 2715feb:app/services/spam_service.py | Select-String -Pattern "SPAM_THRESHOLD"
# → (no output — already deleted)

git show 2715feb^:app/services/spam_service.py | Select-String -Pattern "SPAM_THRESHOLD"
# → SPAM_THRESHOLD = 0.5
```

But `tests/leads/test_spam.py` **still referenced it**:

```bash
git show 2715feb:tests/leads/test_spam.py | Select-String -Pattern "SPAM_THRESHOLD"
# → from app.services.spam_service import score_submission, SPAM_THRESHOLD
# → assert score >= SPAM_THRESHOLD
# → assert score < SPAM_THRESHOLD
```

The fix came in `0d0ec02` (two commits later), where `SPAM_THRESHOLD` was replaced with the literal `0.5`:

```bash
git show 0d0ec02:tests/leads/test_spam.py | Select-String -Pattern "SPAM_THRESHOLD"
# → (no output — fixed)
```

### Test run at `2715feb`

A worktree was created at `2715feb` and the test file was run:

```
git worktree add C:\Users\pc\AppData\Local\Temp\verify-2715feb 2715feb

python -m pytest tests/leads/test_spam.py -v --tb=short
```

```
ImportError while importing test module 'tests/leads/test_spam.py':
    from app.services.spam_service import score_submission, SPAM_THRESHOLD
E   ImportError: cannot import name 'SPAM_THRESHOLD' from 'app.services.spam_service'
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

**Full suite at `2715feb`:**

```
python -m pytest tests/leads/ tests/widgets/ tests/models/ tests/middleware/
tests/repositories/ tests/routers/ tests/services/ tests/test_background_jobs.py
tests/test_db_schema.py tests/test_e2e_widget.py tests/test_lead_worker.py
tests/test_report_worker.py tests/test_worker.py tests/test_main.py tests/embed/
--ignore=tests/test_e2e.py --ignore=tests/test_ai_e2e.py -v --tb=short
```

```
collected 578 items / 1 error
ERROR collecting tests/leads/test_spam.py
    ImportError: cannot import name 'SPAM_THRESHOLD' from 'app.services.spam_service'
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

**The suite did NOT pass at `2715feb`.** The `test_spam.py` file fails at import time because it imports `SPAM_THRESHOLD` which no longer exists in `spam_service.py`. The entire test suite cannot even start collection — it crashes on this single ImportError. The window was fully broken/red until `0d0ec02` landed.

### Cleanup

```
git worktree remove C:\Users\pc\AppData\Local\Temp\verify-2715feb
```

---

## Summary Statuses

1. **CONCERN CONFIRMED** — M1 summary claim that `reset_connection()` and `get_enrichment_job()` were "already deleted from queue.py" before M1 is false. Both functions were fully implemented and existed in the codebase throughout M1. They were only removed in M6's formatting commit `2715feb`, which post-dates M1. M1 was a read-only audit with no code changes.

2. **CONCERN CONFIRMED** — The 409 logic does not use `get_enrichment_job()` / Redis. It relies solely on `lead.status` from the database (`"enriched"` / `"pending"`). `get_enrichment_job()` was created alongside the enrichment feature but was never wired into the re-enrich endpoint at any point. There is a race-condition window between job enqueue and status update where duplicate enrichment jobs could be created.

3. **CONCERN CONFIRMED** — `SPAM_THRESHOLD` was removed from `app/services/spam_service.py` in `2715feb` but `tests/leads/test_spam.py` still imported it, causing an ImportError that blocks collection of the entire test suite. The suite was fully broken (cannot even start) until `0d0ec02` (two commits later) removed the test references.
