# Milestone 12.3 — CI syntax fix & M12 report verification

## 1. CI `\\` syntax test

**Committed (0791bdd) `\\` — BROKEN.**

Git Bash execution of the exact committed YAML content:
```
python -m pytest \\        ← line 1: "python -m pytest \" → pytest gets `\` as a file arg
  tests/embed/ \\          ← line 2: tries to execute tests/embed/ as a program → "Is a directory"
  tests/leads/ \\          ← line 3: same
  ...
```
Each line became a **separate shell command** because `\\` at end of line in bash produces a literal `\` and the newline is NOT escaped. The CI runner would exit immediately on the first failure.

**Fix applied** — reverted all `\\` to `\` in commit `60c234e`. Verified the corrected command produces:

```
======================= 2 failed, 844 passed in 44.70s ========================
```

The 2 failures are `test_tables_exist` / `test_indexes_exist` (Postgres not running locally) — same as the M12 report.

**Corrected diff** (vs. 0791bdd):
```diff
-          python -m pytest \\
+          python -m pytest \
             tests/embed/ \
             tests/leads/ \
             tests/widgets/ \
             tests/middleware/ \
             tests/models/ \
             tests/repositories/ \
             tests/routers/ \
-            tests/scrapers/ \\
+            tests/scrapers/ \
             tests/services/ \
             ...  (same for all 21 continuation lines)
```

---

## 2. M12 "13 tests added" — line-by-line match

### Commit 19663c9 — Category 2 (CORS) — `tests/middleware/test_cors.py` (3 tests)

| Claimed in commit message | Grepped from diff | Match |
|---|---|---|
| `test_cors_on_submit_success` | `+ def test_cors_on_submit_success` | ✓ |
| `test_preflight_headers_include_allow_headers_and_max_age` | `+ def test_preflight_headers_include_allow_headers_and_max_age` | ✓ |
| `test_preflight_with_disallowed_method_returns_400` | `+ def test_preflight_with_disallowed_method_returns_400` | ✓ |

### Commit 16fcc4b — Categories 1+3 (Validation + Rate Limiting) — `tests/leads/test_router.py` (10 tests)

| Claimed in commit message | Grepped from diff | Match |
|---|---|---|
| `test_malformed_json_body` | `+ def test_malformed_json_body` | ✓ |
| `test_empty_body_rejected` | `+ def test_empty_body_rejected` | ✓ |
| `test_invalid_widget_id_format` | `+ def test_invalid_widget_id_format` | ✓ |
| `test_path_traversal_widget_id` | `+ def test_path_traversal_widget_id` | ✓ |
| `test_missing_content_type` | `+ def test_missing_content_type` | ✓ |
| `test_xml_content_type_rejected` | `+ def test_xml_content_type_rejected` | ✓ |
| `test_empty_form_data_dict_rejected` | `+ def test_empty_form_data_dict_rejected` | ✓ |
| `test_429_retry_after_header` | `+ def test_429_retry_after_header` | ✓ |
| `test_window_reset_after_retry_after_expires` | `+ def test_window_reset_after_retry_after_expires` | ✓ |
| `test_rate_limit_takes_precedence_over_dedup` | `+ def test_rate_limit_takes_precedence_over_dedup` | ✓ |

**All 13 match 1:1. No discrepancies.**

---

## 3. "844 passed, 2 failed" — fresh run

Re-ran the full suite (excluding E2E) on the fixed command. Literal tail output:

```
======================= 2 failed, 844 passed in 44.70s ========================
```

Matches the M12 report exactly.

---

## Summary

| Item | Status |
|---|---|
| CI `\\` breakage confirmed? | **Yes** — each line becomes a separate command |
| CI fix committed? | **Yes** — `60c234e` reverts `\\` to `\` |
| 13 test functions match 1:1? | **Yes** — no discrepancies |
| "844 passed, 2 failed" matches? | **Yes** |
| Fabricated finding (`TestOriginValidationViaSubmit` / `RUF012`)? | **Never existed** — the earlier M12 report cited a non-existent class and rule code |
