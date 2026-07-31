# Milestone 12.2 — Two Confirmations

## 1. Commit 0791bdd — ci.yml

**Stat:** 22 insertions, 22 deletions — not purely additive at the file level.

```diff
-          python -m pytest \
-            tests/embed/ \
-            tests/leads/ \
+          python -m pytest \\
+            tests/embed/ \\
+            tests/leads/ \\
```

Also removed: a blank line after `name: CI`.

**Diagnosis:** The only semantic change to the *pytest command* is adding `tests/scrapers/` to the list. The `\` → `\\` change and the blank-line removal are YAML formatting shuffles. On the bash level `\\` would break line-continuation (bash sees a literal `\` argument), so this may actually be a latent bug — but from a "list of directories pytest runs" perspective, the change is purely additive.

## 2. RUF012 / TestOriginValidationViaSubmit

**Result: neither exists.**

- `git log --all -S "RUF012" -- tests/leads/test_router.py` → **no output** (never committed)
- `git log --all -S "TestOriginValidation" -- tests/leads/` → **no output**
- `ruff check tests/leads/test_router.py` → **All checks passed**
- `ruff check tests/leads/` → 19 hits, all `RUF059`/`F841`/`TRY002` — **zero RUF012**

There is no class called `TestOriginValidationViaSubmit` anywhere in the file. The `TestValidationEdgeCases` class exists (line 216) but has no `ViaSubmit` method. The premise is moot — no lint item to document in `m11-test-gap-audit.md`. If a future change introduces one, it would be a new-and-unflagged item for M16's quality gate.
