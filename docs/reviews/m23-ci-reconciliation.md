# M23 — CI Command Reconciliation

**Purpose.** The M22 capstone audit (`docs/reviews/capstone-review-audit.md`, §8)
labeled its pytest command "exact CI / capstone.yaml invocation." This
milestone re-verifies the underlying claim — `938 passed / 100% coverage /
0 failed` — independently, against the actual authoritative command(s),
because the M22 §8 command differs from the command documented for M4/M8
(`docs/Production readiness milestone prompts .md` M4 block and
`docs/PRODUCTION_READINESS_REPORT.md` §11.1) in two respects: `tests/scrapers/`
is present in the M22 run but absent from M4/M8's recorded command, and
`tests/test_db_schema.py` is absent from the M22 run but present in M4/M8's
recorded command.

**Method.** Read-only investigation of all three command sources plus their git
history, followed by two live test runs (one per candidate command) on the
current working tree. No source, test, or config file was modified; no commit
was created. The only file written is this report.

---

## 1. The commands, verbatim

### 1.1 `capstone.yaml` — `test:` field (lines 11–17, folded scalar)

```yaml
test: >-
  python -m pytest tests/embed/ tests/leads/ tests/widgets/ tests/middleware/
  tests/models/ tests/repositories/ tests/routers/ tests/scrapers/
  tests/services/ tests/test_main.py tests/test_background_jobs.py
  tests/test_e2e_widget.py tests/test_lead_worker.py tests/test_report_worker.py
  tests/test_worker.py --ignore=tests/test_e2e.py --ignore=tests/test_ai_e2e.py
  --cov=app --cov-report=term-missing --tb=short -v
```

### 1.2 `.github/workflows/ci.yml` — `Test with pytest` `run:` step (lines 41–64)

```yaml
      - name: Test with pytest
        run: |
          python -m pytest \
            tests/embed/ \
            tests/leads/ \
            tests/widgets/ \
            tests/middleware/ \
            tests/models/ \
            tests/repositories/ \
            tests/routers/ \
            tests/scrapers/ \
            tests/services/ \
            tests/test_main.py \
            tests/test_background_jobs.py \
            tests/test_e2e_widget.py \
            tests/test_lead_worker.py \
            tests/test_report_worker.py \
            tests/test_worker.py \
            --ignore=tests/test_e2e.py \
            --ignore=tests/test_ai_e2e.py \
            --cov=app \
            --cov-report=term-missing \
            --tb=short \
            -v
```

### 1.3 M4/M8 documented command (M4 block, lines 199–219; reproduced verbatim in `PRODUCTION_READINESS_REPORT.md` §11.1, lines 277–284)

```text
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

---

## 2. Verdict: same command or different, and which is authoritative

**`capstone.yaml` and `.github/workflows/ci.yml` are the SAME command.** The
YAML folded scalar (§1.1) and the backslash-continued `run:` block (§1.2)
normalize to the identical token sequence. Verified programmatically against
`HEAD`:

```text
CAPSTONE_NORM: python -m pytest tests/embed/ tests/leads/ tests/widgets/ tests/middleware/
  tests/models/ tests/repositories/ tests/routers/ tests/scrapers/ tests/services/
  tests/test_main.py tests/test_background_jobs.py tests/test_e2e_widget.py
  tests/test_lead_worker.py tests/test_report_worker.py tests/test_worker.py
  --ignore=tests/test_e2e.py --ignore=tests/test_ai_e2e.py --cov=app
  --cov-report=term-missing --tb=short -v
CI_NORM:       [identical token sequence]
EQUAL: True
```

**The M4/M8 documented command is DIFFERENT in exactly two ways:**

| | capstone.yaml / ci.yml | M4/M8 recorded |
|---|---|---|
| `tests/scrapers/` | **present** | absent |
| `tests/test_db_schema.py` | absent | **present** |
| all other paths, ignores, flags | identical | identical |

**Authoritative:** `.github/workflows/ci.yml` at `HEAD` is the live definition
of "CI passing." It reached its current form in commit **`aa01f18`** (2026-07-31
19:39:48 +0300). `capstone.yaml` was created afterward in commit **`007c743`**
(2026-07-31 20:53:46 +0300) with a `test:` field that mirrors the then-current
ci.yml exactly — so capstone.yaml is authoritative **by mirror** and is in sync
today. The M4/M8 recorded command is **stale**: it matches the ci.yml state
*before* `0791bdd` (2026-07-30 09:39:34, which added `tests/scrapers/`) and
*before* `aa01f18` (which removed `tests/test_db_schema.py`). It has therefore
been stale since `0791bdd`, i.e. the `tests/scrapers/` delta predates the
`test_db_schema.py` delta.

**Timeline of the authoritative command (git log, `-- .github/workflows/ci.yml`):**

| Commit | Date | Change |
|---|---|---|
| `b81bfbf` | — | initial workflow |
| `b0358e2` | — | update tests and CI config |
| `0791bdd` | 2026-07-30 09:39:34 | **add** `tests/scrapers/` |
| `60c234e` | — | fix CI syntax (revert `\\` to `\`) |
| `aa01f18` | 2026-07-31 19:39:48 | **remove** `tests/test_db_schema.py`; add `addopts` ignore |
| `007c743` | 2026-07-31 20:53:46 | create `capstone.yaml` (mirrors ci.yml) |

**The M22 §8 command is byte-for-byte the authoritative command** — it is
exactly §1.1/§1.2, including `tests/scrapers/` and excluding
`tests/test_db_schema.py`. Its "exact CI / capstone.yaml invocation" label is
accurate with respect to the *current* ci.yml.

---

## 3. `tests/test_db_schema.py`: deliberate exclusion, not a silent drop

**Verdict: deliberate, documented, and enforced.** The exclusion from the M22
run (and from the authoritative command generally) is not an oversight.

Evidence:

1. **Commit `aa01f18` commit message (verbatim):** *"fix: make CI tests pass on
   FastAPI 0.132+ and Linux — … — Ignore tests/test_db_schema.py on pytest
   (needs live Postgres); align ci.yml and AGENTS.md pytest command
   accordingly."* The diff removes `tests/test_db_schema.py \` from ci.yml and
   adds `addopts = "--ignore=tests/test_db_schema.py"` to `pyproject.toml`.
2. **`pyproject.toml:39`:** `addopts = "--ignore=tests/test_db_schema.py"` —
   the file is ignored at the config level for any bare `pytest` run.
3. **`AGENTS.md:65`:** *"`tests/test_db_schema.py` is **ignored on pytest**
   (`addopts --ignore` in `pyproject.toml`) — needs a live Postgres. Run it
   explicitly … against a running `db` service."*
4. **`capstone.yaml` history:** the file is a single commit (`007c743`); its
   `test:` field has never contained `tests/test_db_schema.py`. There is no
   "left the test path" event to find — it was never listed.
5. **Historical baseline:** `docs/reviews/m4-test-baseline.md:35-49` documents
   that when M4 *did* run this file, both tests failed (no local Postgres) —
   the exact pair reproduced in §4.2 below.

**Was Docker/Postgres live during the M22 run?** This cannot be confirmed after
the fact, and I will not guess. What is determinable: the Docker Desktop daemon
is **not running now** (`docker ps` → engine pipe not found), and it is moot
for the M22 numbers regardless, because `tests/test_db_schema.py` was never
collected in the M22 run (not in the command; and even the config-level ignore
would have been the only guard, though see the nuance in §4.2). Docker state
cannot affect a count of 938 tests that excludes the file.

**M22's exclusion was therefore a deliberate, documented decision** — matching
the authoritative command — not an undocumented silent drop.

---

## 4. Live-run literal output (both candidate commands)

Environment: Windows (win32), Python 3.13.14, `asyncio_mode = "auto"`,
`conftest.py` forces offline mode (`DATABASE_URL=""`, `REDIS_URL=""`,
`is_postgres_enabled` → `False`, `_FakeRedis`/`_FakeQueue`). Working tree
identical to the M22 run (no source changes between M22 and M23).

### 4.1 Candidate A — authoritative (ci.yml ≡ capstone.yaml) — **THE CI COMMAND**

```text
$ python -m pytest tests/embed/ tests/leads/ tests/widgets/ tests/middleware/ \
    tests/models/ tests/repositories/ tests/routers/ tests/scrapers/ \
    tests/services/ tests/test_main.py tests/test_background_jobs.py \
    tests/test_e2e_widget.py tests/test_lead_worker.py tests/test_report_worker.py \
    tests/test_worker.py --ignore=tests/test_e2e.py --ignore=tests/test_ai_e2e.py \
    --cov=app --cov-report=term-missing --tb=short -v

... 938 tests, all PASSED, zero F (failure) / E (error) / s (skip) markers ...

TOTAL                                       2873      0   100%
============================ 938 passed in 42.84s =============================
```

- Collected: **938** · Passed: **938** · Failed: **0** · Skipped: **0** ·
  Errors: **0** · Coverage: **TOTAL 2873 0 100%** · Duration: **42.84s**.
- Scrapers modules under `app/scrapers/` all report **100%** (cleaner 55/55,
  parser 88/88, pipeline 43/43, session 95/95) — they are exercised by the
  `tests/scrapers/` tests included in this command.

### 4.2 Candidate B — M4/M8 documented command (adds `tests/test_db_schema.py`, drops `tests/scrapers/`)

```text
$ python -m pytest tests/embed/ tests/leads/ tests/widgets/ tests/middleware/ \
    tests/models/ tests/repositories/ tests/routers/ tests/services/ \
    tests/test_main.py tests/test_background_jobs.py tests/test_db_schema.py \
    tests/test_e2e_widget.py tests/test_lead_worker.py tests/test_report_worker.py \
    tests/test_worker.py --ignore=tests/test_e2e.py --ignore=tests/test_ai_e2e.py \
    --cov=app --cov-report=term-missing --tb=short -v

tests/test_db_schema.py::TestDBSchema::test_tables_exist FAILED          [ 93%]
tests/test_db_schema.py::TestDBSchema::test_indexes_exist FAILED         [ 93%]

tests\test_db_schema.py:25: in test_tables_exist
    raise last_error or exceptions.TargetServerAttributeNotMatched(
E   ConnectionRefusedError: [WinError 1225] The remote computer refused the network connection
tests\test_db_schema.py:44: in test_indexes_exist
    raise last_error or exceptions.TargetServerAttributeNotMatched(
E   ConnectionRefusedError: [WinError 1225] The remote computer refused the network connection

app\scrapers\cleaner.py     55     19    65%   13, 17-18, 23, 29, 33-35, 43-44, 55, 57, 59, 61, 77-81
app\scrapers\parser.py      88     80     9%   18-66, 70-119, 123-131
app\scrapers\pipeline.py    43     35    19%   23-75
app\scrapers\session.py     95     71    25%   22-26, 29-43, 46-65, 68-75, 79, 84-101, 104-117, 120-125, 128
TOTAL                                       2873    205    93%

======================= 2 failed, 820 passed in 47.01s ========================
```

- Collected: **822** · Passed: **820** · Failed: **2** · Skipped: **0** ·
  Errors: **0** · Coverage: **TOTAL 2873 205 93%** · Duration: **47.01s**.

**The two failures are exactly the M4-baseline known failures**
(`docs/reviews/m4-test-baseline.md:42-49`): `TestDBSchema::test_tables_exist`
and `TestDBSchema::test_indexes_exist`, both attempting `asyncpg.connect()` to
`postgresql://flyrank:flyrank_pass@127.0.0.1:5432/flyrank` with no Postgres
running. These are **not new regressions**; they are the documented
environment-dependent pair (M4 recorded the same pair; the current error text
is `ConnectionRefusedError` rather than M4's `TimeoutError` — same root cause:
no live Postgres).

**Collection nuance (verified live):** an explicitly listed file path takes
precedence over the `--ignore=tests/test_db_schema.py` in `pyproject.toml`
`addopts`. That is why the M4/M8 command collects and fails the file here even
though config-level `pytest` (bare) ignores it. This nuance is why the M4
baseline — which always passed the file explicitly — recorded 2 failures while
bare `pytest` reports 0.

**Side-by-side:**

| Metric | Candidate A (authoritative) | Candidate B (M4/M8 recorded) |
|---|---|---|
| Collected | **938** | 822 |
| Passed | **938** | 820 |
| Failed | **0** | **2** (`test_db_schema.py`, Postgres down) |
| Skipped | 0 | 0 |
| Errors | 0 | 0 |
| Coverage (TOTAL) | **2873 / 0 / 100%** | 2873 / 205 / **93%** |
| Duration | 42.84s | 47.01s |

---

## 5. Cross-check: does `tests/scrapers/` belong in the authoritative command?

**Yes — deliberate scope expansion, not an accident.** `tests/scrapers/` was
never part of the M4 baseline path list because it was not yet in ci.yml at
that time. It was added to CI in commit **`0791bdd`** (2026-07-30 09:39:34) —

> *"Fix CI configuration: add missing tests/scrapers/ to pytest command. This
> restores the complete test suite that was run in M10d, ensuring coverage and
> test count measurements are accurate. Fixes test count regression from 727 to
> expected ~844 baseline (including M12's 13 new tests)."*

The M4 report itself explains its earlier absence:
`docs/reviews/m4-test-baseline.md:297` — *"Scrapers have 0-9% coverage (not in
scope for this review, but drags overall number)."* The tests existed; they
were simply omitted from the CI list, and `0791bdd` restored them. The 118
scraper tests (derived: 938 authoritative − (820 + 2) M4-command = 118, since
the only differences are the two directories) are the entire reason Candidate A
hits 100% coverage while Candidate B drops to 93% (`app/scrapers/*`).
`scrapers/` therefore **belongs** in the authoritative command, and its
inclusion is documented intent.

---

## 6. Reconciled baseline going forward (labeled)

The following is the **reconciled baseline** for "CI passing," valid from
`aa01f18` (2026-07-31 19:39:48) onward and reproduced live on 2026-08-01:

| Metric | Reconciled baseline (authoritative command) |
|---|---|
| Command | `python -m pytest tests/embed/ tests/leads/ tests/widgets/ tests/middleware/ tests/models/ tests/repositories/ tests/routers/ tests/scrapers/ tests/services/ tests/test_main.py tests/test_background_jobs.py tests/test_e2e_widget.py tests/test_lead_worker.py tests/test_report_worker.py tests/test_worker.py --ignore=tests/test_e2e.py --ignore=tests/test_ai_e2e.py --cov=app --cov-report=term-missing --tb=short -v` |
| Collected | **938** |
| Passed | **938** |
| Failed | **0** |
| Skipped | **0** |
| Errors | **0** |
| Coverage | **100%** (`TOTAL 2873 0`) |
| `test_db_schema.py` | Not collected (not in command; config-ignored for bare runs) |
| Requires | No Postgres, no Redis, no network — fully offline (`conftest.py` mocks) |

**Known deviation if you deliberately use the M4/M8 command instead:** 822
collected, 820 passed, **2 failed** (`test_db_schema.py`), **93% coverage** —
the 2 failures are the documented environment-dependent pair, expected only
without a live Postgres; they are the M4 baseline, not a regression.

---

## 7. Confirmation of the M22 claim

**The M22 report's claim — `938 passed / 100% coverage / 0 failed` — HOLDS. It
is confirmed, exactly and independently.**

- The M22 §8 command is **the authoritative command** (identical to current
  `.github/workflows/ci.yml` and `capstone.yaml`). Its label "exact CI /
  capstone.yaml invocation" is accurate for the current CI definition.
- An independent live rerun of that exact command on the identical working
  tree reproduced **`938 passed in 42.84s`** with **`TOTAL 2873 0 100%`** —
  matching the M22 result (`938 passed in 46.75s`, `TOTAL 2873 0 100%`) and
  EVIDENCE.md's recorded `938 passed / 100%`. The only difference is runtime
  (42.84s vs 46.75s), which is machine/load variance, not a count difference.
- The apparent mismatch that motivated this milestone is fully explained: the
  M22 run matched the *current* CI command, while the M4/M8 documented command
  predates two deliberate CI edits (`0791bdd` added `tests/scrapers/`;
  `aa01f18` removed `test_db_schema.py`). It is the M4/M8 recorded command that
  is stale — not the M22 command, and not the M22 numbers.

**Bottom line: `938 passed / 0 failed / 0 skipped / 0 errors / 100% coverage`
is the accurate, authoritative, reproducible state of the suite. The M22
report's numbers are correct; no correction to them is required.**

---

## Appendix — supporting evidence

- `git show 0791bdd` (ci.yml diff): `+ tests/scrapers/ \` added; commit message
  quoted in §5.
- `git show aa01f18` (ci.yml diff): `- tests/test_db_schema.py \` removed;
  `pyproject.toml` gains `addopts = "--ignore=tests/test_db_schema.py"`;
  commit message quoted in §3.
- `git show 60c234e`: CI syntax `\\` → `\` (no path change).
- `git show 007c743:capstone.yaml`: `test:` field identical to ci.yml at the
  time of creation.
- Programmatic equality check (`EQUAL: True`) reproduced in §2.
- `docker ps` at audit time: daemon not reachable (engine pipe not found) —
  no Postgres/Redis containers available locally.
- M4 baseline of the 2 known failures: `docs/reviews/m4-test-baseline.md:35-49`.
- M8's recorded run (`PRODUCTION_READINESS_REPORT.md:277-287`, `312`): used the
  stale command (includes `test_db_schema.py`, omits `scrapers/`), and its 2
  failures resolved only because a Docker Postgres container happened to be
  running — an environment-driven pass, exactly the class of behavior
  `aa01f18` later made impossible by removing the file from CI.

No source, test, or configuration file was modified during this milestone.
