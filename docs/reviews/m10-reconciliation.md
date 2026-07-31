# M10.reconcile — Coverage Evidence for Batches A, B, C

All coverage numbers below were captured by running the CI test suite at each commit state (`git checkout <hash>` + `pytest` with `--cov=app --cov-report=term-missing`). Pre-existing DB failures (`test_db_schema.py`) excluded from pass counts.

---

## Batch A — `2d37940` (M10a: Postgres-gated modules)

### Per-module coverage deltas (parent `0d9c5c7` → `2d37940`)

| Module | Before | After | Delta |
|--------|--------|-------|-------|
| `services/scraped_book_service.py` | 38% (13/21) | **100%** | +62 |
| `services/widget_service.py` | 95% (3: 8-10, 88) | **98%** (1: 88) | +3 |
| `main.py` | 98% (2: 40-41) | **100%** | +2 |
| `core/supabase.py` | 88% (2: 13-14) | **88%** (2: 13-14) | 0 |
| `core/worker.py` | 74% (8: 34-35, 41-46, 50) | **100%** | +26 |
| **Aggregate** | **88%** (310 miss) | **91%** (231 miss) | +3 |

Side-effect improvements: `middleware/body_limit.py` 95→100%, `services/report_service.py` 82→100%, `services/task_service.py` 90→100%, `dependencies/embed.py` 96→100%.

### Source-change confirmation

Only `app/core/worker.py:49` changed — added `# pragma: no cover` on `if __name__ == "__main__":`. All other `app/` files untouched. Confirmed by `git diff 0d9c5c7..2d37940 -- app/`.

### Bugs found

None.

### Literal pytest output

```
2 failed, 701 passed in 44.30s
```

---

## Batch B — `651bed0` (M10b: error/exception paths)

### Per-module coverage deltas (parent `2d37940` → `651bed0`)

| Module | Before | After | Delta |
|--------|--------|-------|-------|
| `dependencies/leads.py` | 96% (2: 26-27) | **100%** | +4 |
| `services/geo_service.py` | 94% (6: 89-91, 117-119) | **100%** | +6 |
| `services/lead_service.py` | 99% (2: 209-210) | **100%** | +1 |
| `services/lead_worker.py` | 92% (4: 31, 57, 101-102) | **96%** (2: 101-102) | +4 |
| `routers/auth.py` | 92% (5: 56-59, 76) | **100%** | +8 |
| **Aggregate** | **91%** (231 miss) | **92%** (214 miss) | +1 |

`lead_worker.py:101-102` pre-existing silent-except branch left uncovered per scope.

### Source-change confirmation

Zero `app/` files changed. Only 3 test files modified. Confirmed by `git diff 2d37940..651bed0 -- app/`.

### Bugs found

None.

### Literal pytest output

```
2 failed, 710 passed in 43.01s
```

---

## Batch C — `3961d63` (M10c: edge cases)

### Per-module coverage deltas (parent `651bed0` → `3961d63`)

| Module | Before | After | Delta |
|--------|--------|-------|-------|
| `models/widget.py` | 96% (2: 37, 41) | **100%** | +4 |
| `routers/leads.py` | 99% (1: 226) | **100%** | +1 |
| `routers/reports.py` | 90% (3: 40, 47, 58) | **97%** (1: 47) | +7 |
| `services/widget_service.py` | 98% (1: 88) | **100%** | +2 |
| `scrapers/cleaner.py` | 65% | **65%** | 0 |
| **Aggregate** | **92%** (214 miss) | **92%** (208 miss) | 0 |

**cleaner.py note**: 4 null-field tests were added (description, category, upc, image_url whitespace-only inputs) covering lines 55, 57, 59, 61. These are validated at HEAD (99% overall, `tests/scrapers/` in CMD). The 0% delta at this commit reflects that the CI command at M10c did not yet include `tests/scrapers/` — added in M10d.

**routers/reports.py:47** — normpath defence-in-depth branch; unreachable via HTTP router (Starlette normalizes `..` before routing). Pre-existing gap.

### Source-change confirmation

Zero `app/` files changed. Only 5 test files modified. Confirmed by `git diff 651bed0..3961d63 -- app/`.

### Bugs found

None. Widget model validator tests revealed that Pydantic `model_validator(mode="after")` catches `ValueError` internally — test expectations were adjusted to match actual behaviour; no source changes required.

### Literal pytest output

```
2 failed, 714 passed in 44.29s
```

---

## Cross-batch summary

| Metric | Batch A | Batch B | Batch C |
|--------|---------|---------|---------|
| Commit | `2d37940` | `651bed0` | `3961d63` |
| `app/` files changed | 1 (pragmatic only) | 0 | 0 |
| Test files modified | 8 (+302 lines) | 3 (+173 lines) | 5 (+125 lines) |
| Tests passed | 701 | 710 | 714 |
| Coverage | 88→91% | 91→92% | 92→92% |
| Bugs found | None | None | None |

No bugs were found or silently fixed across A, B, C. The only source change across all three commits is the single `# pragma: no cover` annotation on `app/core/worker.py:49`. Every other change under these commits is in `tests/` only.
