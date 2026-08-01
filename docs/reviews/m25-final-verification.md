# M25 — Closing Milestone: Final Tier A Cleanup & Verification

**Date:** 2026-08-01 · **Branch:** `feature/capstone-submission-pack`
**Scope:** F2, F3, F4 (Tier A) + F1 fallback-chain verification gap. No behavior
change to the already-fixed M24 code (F1/F5 core fix untouched).

---

## 1. Tier A findings

### F2 — Misleading test name (`tests/widgets/test_router.py:238`)

`test_get_widget_403_wrong_tenant` asserts `404` (line 243). The code's
leak-safe cross-tenant behavior is correct; only the name was wrong.

**Resolution:** added a two-line comment above the test documenting that
cross-tenant reads deliberately return `404` rather than `403` to avoid
leaking existence. Chosen over a rename because renaming would have staled the
pasted run proof in `EVIDENCE.md:46` (a historical log that should not be
falsified) and the M22 audit's evidence column. Assertion and response code
unchanged.

### F3 — EVIDENCE.md line citation (`embed.py:54 → :63`)

**Already closed — verified directly, no action taken.** Current content:

- `EVIDENCE.md:96` cites `` `app/routers/embed.py:63` `` — and `embed.py:63` is
  exactly the `"Cache-Control": "public, max-age=31536000, immutable"` header
  line of `get_widget_js`.
- `EVIDENCE.md:82-84` cache-control prose softened: "The cache-control test
  asserts the presence of `public` and `max-age` on the config response
  (`app/routers/embed.py`), alongside a 300s server-side Redis cache."

Confirmed landed as part of commit `33a0e5e` (M24). No further action.

### F4 — AGENTS.md stale Tier C item (`AGENTS.md:96-99`)

AGENTS.md listed "POST /widgets status code" as an **open** Tier C item
awaiting sign-off. It was closed in **M17** via plan update:

- `docs/implementation-plan.md:7` — "M17 update (2026-07-30): Corrected
  validation error status codes from `400` to `422` ... this is a plan
  correction to match the implementation."
- `docs/reviews/m1-architecture.md:113` — Tier C table row:
  `STATUS: CLOSED — resolved via plan update (M17).`
- Plan-update commit `85ba47d`.

**Resolution:** replaced the "Open Tier C items (needs Ahmed's sign-off)"
section with a "Tier C disposition" section marking the item **RESOLVED
(M17, plan update)**, citing both docs, and stating "No open Tier C items
remain." README.md and EVIDENCE.md already documented the 422 behavior; only
AGENTS.md was stale.

---

## 2. F1 fallback-chain verification gap — resolution

The M24 apiBase derivation chain (`app/services/widget_js.py:4-14`) has three
tiers:

| Tier | Source | Pre-M25 coverage |
|---|---|---|
| 1 | `script.getAttribute("data-api-base")` | untested |
| 2 | `document.currentScript.src` marker parse | tested (harness) |
| 3 | `window.location.origin` | untested |

**Path taken: (a) — real script-execution tests per branch.** node v24.14.0 is
available and the existing harness `tests/embed/harness_foreign_origin.js`
already executes the bundle, so branch coverage was proportionate (a ~15-line
parameterization), not disproportionate.

**Changes (commit `b809413`):**

- `harness_foreign_origin.js` now reads branch config from `HARNESS_*` env vars
  (`HARNESS_SCRIPT_SRC`, `HARNESS_PAGE_HREF`, `HARNESS_PAGE_ORIGIN`,
  `HARNESS_API_BASE_OVERRIDE`, `HARNESS_NO_CURRENT_SCRIPT`); defaults preserve
  the previous behavior exactly, so the existing DoD #6 test is unchanged.
- Two new node-harness tests in `TestCrossOriginRender`
  (`tests/embed/test_widget_js.py`), both `skipif node absent`:

**Tier 1 — data-api-base override wins** (`test_config_and_submit_honor_data_api_base_override`):
script on `api.flyrank.example`, override `https://override.example`:

```text
$ HARNESS_API_BASE_OVERRIDE=https://override.example node tests/embed/harness_foreign_origin.js <widget.js>
{"config":"https://override.example/public/widget/abc/config","submit":"https://override.example/public/widget/abc/submit"}
```

**Tier 3 — page-origin fallback only when currentScript is absent**
(`test_config_and_submit_fall_back_to_page_origin_without_current_script`):

```text
$ HARNESS_NO_CURRENT_SCRIPT=1 node tests/embed/harness_foreign_origin.js <widget.js>
{"config":"https://customer-site.example/public/widget/abc/config","submit":"https://customer-site.example/public/widget/abc/submit"}
```

**Result:** the override is confirmed functional and takes precedence over the
script src. The `window.location.origin` tier is confirmed reachable **only**
when `currentScript` is genuinely absent — i.e. dynamically-injected scripts
(`document.createElement("script")`, async attribute injection), **not** the
documented embed pattern (`generate_script_tag` emits a static
`<script src=".../public/widget/{id}/widget.js?v=N" defer>` tag per
implementation-plan.md §5.2, for which `currentScript` is always populated and
tier 2 fires). When reached, tier 3 reproduces page-origin resolution — the
exact behavior F1 fixed — confirming it as a documented, unsupported edge case
rather than the common path. A subtlety noted: tier 3 is also reachable if a
script element's `src` lacks the `/public/widget/` marker, which cannot occur
for tags produced by `generate_script_tag`.

---

## 3. Final test verification — three-way comparison

Command: the M23-reconciled authoritative invocation from
`.github/workflows/ci.yml` (verbatim, token-identical to `capstone.yaml`
`test:` field).

| Metric | M23 baseline | M24 result | **M25 result** |
|---|---|---|---|
| Passed | 938 | 944 | **946** |
| Failed | 0 | 0 | **0** |
| Skipped | 0 | 0 | **0** |
| Errors | 0 | 0 | **0** |
| Coverage | 2873 stmts, 100% | 2885 stmts, 100% | **2885 stmts, 100%** |
| Duration | 42.84s (EVIDENCE.md: 36.88s) | 37.55s | **40.26s** |

M25 delta: **+2 tests** (both new branch tests), no Python source changes
(coverage statement count unchanged at 2885). Both new tests fail cleanly
without node and were executed against node v24.14.0 in this run.

---

## 4. Lint verification (CI order: isort → black → ruff)

```text
$ python -m isort --check-only --diff .
Skipped 1 files

$ python -m black --check --diff .
All done! ✨ 🍰 ✨
154 files would be left unchanged.

$ python -m ruff check .
All checks passed!
```

(Black emits a benign "Python 3.13 cannot parse code formatted for Python 3.15"
heuristic warning on every run; it exits 0 and reports 154/154 unchanged,
identical to M24.)

---

## 5. DoD #6 re-verification (manual, literal output)

Bundle re-rendered with `render_widget_js("abc", {}, 1)` and executed in the
node harness with the script on `api.flyrank.example` and the page on
`customer-site.example`:

```text
$ node tests/embed/harness_foreign_origin.js <rendered-widget.js>
{"config":"https://api.flyrank.example/public/widget/abc/config","submit":"https://api.flyrank.example/public/widget/abc/submit"}
```

Matches `EVIDENCE.md:110-112` and M24's post-fix output. Config fetch and
submit POST both resolve to the **script's** host, never the page host.

```text
$ python -m pytest "tests/embed/test_widget_js.py::TestCrossOriginRender" -v
tests/embed/test_widget_js.py::TestCrossOriginRender::test_bundle_derives_base_from_current_script PASSED [ 25%]
tests/embed/test_widget_js.py::TestCrossOriginRender::test_config_and_submit_resolve_to_script_origin PASSED [ 50%]
tests/embed/test_widget_js.py::TestCrossOriginRender::test_config_and_submit_honor_data_api_base_override PASSED [ 75%]
tests/embed/test_widget_js.py::TestCrossOriginRender::test_config_and_submit_fall_back_to_page_origin_without_current_script PASSED [100%]
============================== 4 passed in 0.50s ==============================
```

No regression found in M24's fix → F1/F5 core fix **not** re-opened.

---

## 6. Closing reconciliation table

| # | Finding | Original severity | Fix commit(s) | Current status |
|---|---|---|---|---|
| F1 | Widget bundle uses origin-relative URLs (cross-origin render broken) | Major | `33a0e5e` (M24) | **Fixed** — re-verified live in M25 (DoD #6 harness output, §5) |
| F1 sub-item | Fallback-chain verification gap: `data-api-base` override and `window.location.origin` untested | — (sub-item of F1) | `b809413` (M25) | **Verified-fixed** — both branches covered by real execution tests (§2) |
| F2 | Test name `test_get_widget_403_wrong_tenant` asserts 404 | Minor | `950f9b3` (M25) | **Fixed** — intent documented; assertion/response unchanged |
| F3 | EVIDENCE.md `embed.py` line citation stale (`:54` → `:63`) | Minor | `33a0e5e` (M24) | **Verified-fixed** — direct file check confirms `:63` and softened prose (§1) |
| F4 | AGENTS.md lists `POST /widgets` status code as open Tier C | Minor | `950f9b3` (M25) | **Closed** — marked RESOLVED via M17 plan update, citing plan:7 + m1-architecture:113 (§1) |
| F5 | `generate_script_tag` unreachable + default `base_url=""` | Minor | `cdfe4f9` (M24) | **Fixed** — exposed at `GET /widgets/{id}/embed`, default `DEFAULT_API_BASE_URL` |

---

## 7. Deliverables

- **Commit `950f9b3`** — F2 comment + F4 AGENTS.md disposition (doc/naming).
- **Commit `b809413`** — F1 fallback-chain tests (harness parameterization +
  2 branch tests). Kept separate from the pure doc/naming fixes per plan §5.
- This file. (`git status` before each commit confirmed only intended files
  staged; `docs/reviews/capstone-review-audit.md` and
  `docs/reviews/m23-ci-reconciliation.md` remain untracked review docs.)
