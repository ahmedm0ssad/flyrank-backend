# M28 — F6 Fix + Live-Postgres Coverage for PostgresLeadRepository

**Status**: COMPLETE
**Date**: 2026-08-01
**Branch**: `feature/capstone-submission-pack`
**Commits**: `e8a39fc` (fix) · `1d05657` (live test suite) · (this report, docs)
**Baseline reference**: M25 — 946 passed / 0 failed / 100% coverage.

---

## 1. Root cause (confirmed by full-file read)

`app/repositories/postgres_lead_repo.py:63` passed `row["ip_address"]` directly into
`LeadResponse.ip_address: str`. asyncpg returns an `IPv4Address`/`IPv6Address` object for
an `INET` column, so Pydantic raised `ValidationError` on **every** lead write and read
against real Postgres (submit, get/list, update, export). The in-memory repo used by the
entire mocked suite stores plain strings, so 946 passing tests / 100% coverage never
exercised the conversion.

The M27 live traceback (reproduced here) was:

```
File "/app/app/repositories/postgres_lead_repo.py", line 121, in create
File "/app/app/repositories/postgres_lead_repo.py", line 58, in _row_to_response
pydantic_core._pydantic_core.ValidationError: 1 validation error for LeadResponse
  Input should be a valid string [type=string_type, input_value=IPv4Address('172.18.0.1'), input_type=IPv4Address]
```

---

## 2. Full asyncpg → Pydantic field-conversion audit

Every row-mapping function was checked, not just the one field. Column types are from
`db/init.sql`.

### `app/repositories/postgres_lead_repo.py` — `_row_to_response` (all 16 fields)

| Field | Column type | asyncpg returns | Model expects | Verdict |
|---|---|---|---|---|
| `id` | UUID | `uuid.UUID` | `UUID` | OK — accepted |
| `widget_id` | UUID | `uuid.UUID` | `UUID` | OK |
| `tenant_id` | UUID | `uuid.UUID` | `UUID` | OK |
| `form_data` | JSONB | `dict` (or `str`) | `dict` | OK — `_parse_json` handles both |
| **`ip_address`** | **INET** | **`IPv4Address`/`IPv6Address`** | **`str`** | **F6 — fixed** |
| `user_agent` | TEXT | `str` | `str\|None` | OK |
| `referer` | TEXT | `str` | `str\|None` | OK |
| `fingerprint` | VARCHAR(64) | `str` | `str` | OK |
| `geo_country/city/region/isp/provider` | VARCHAR | `str\|None` | `str\|None` | OK |
| `spam_score` | REAL | `float` | `float` | OK |
| `spam_reasons` | JSONB | `list\|None` (or `str`) | `list[str]\|None` | OK — `_parse_json` |
| `honeypot_triggered` | BOOLEAN | `bool` | `bool` | OK |
| `status` | VARCHAR(20) | `str` | `str` | OK |
| `created_at` / `updated_at` | TIMESTAMPTZ | `datetime` (tz-aware) | `datetime` | OK |

### `app/repositories/postgres_widget_repo.py` — `_row_to_response` and `get_by_id_raw`

- `id`/`tenant_id` (UUID → `UUID`): OK.
- `config` (JSONB → `dict`): OK — guarded by `isinstance(row["config"], dict) else json.loads`.
- `get_by_id_raw` returns a raw `dict` (not a Pydantic model): `config` string is
  JSON-decoded; no validation surface.
- `name`/`domain` (str), `js_version` (int), `active` (bool), `created_at` (datetime): OK.

### `app/repositories/postgres_repo.py` (tasks) — `TaskResponse(**dict(row))`

Only `SERIAL`/`VARCHAR`/`BOOLEAN`/`TIMESTAMPTZ` columns — no INET/JSONB/UUID objects. OK.

**Audit conclusion: only `ip_address` needed a row-mapping fix.** However, running the
new live suite immediately exposed a *second* live-only defect in the same file (see §4),
so the fix commit covers both.

---

## 3. The fix

### F6 — `postgres_lead_repo.py:63` (row mapping)
```diff
-            ip_address=row["ip_address"],
+            ip_address=str(row["ip_address"]),
```
`str()` is the identity for the plain-string FakeRows used by the mocked suite, so no
mocked test changes were needed. It also covers IPv6 (`str(IPv6Address("2001:db8::1"))`).

### F8 — `postgres_lead_repo.py:389` (geo placeholder binding, found by the new suite)
`update_status(..., geo_country=..., ...)` built `updated_at = $3` **and**
`geo_country = COALESCE($3, geo_country)`, binding `$3` to both a timestamptz and a text
value. asyncpg rejects that with `AmbiguousParameterError` on a real server:
```diff
-                    f"{column} = COALESCE(${len(geo_params) + 3}, {column})"
+                    f"{column} = COALESCE(${len(geo_params) + 4}, {column})"
```
The first geo value is `$4` (after `$1`=id, `$2`=status, `$3`=updated_at). The mocked
test only asserted `fetchrow` was awaited — the SQL never ran, so this never surfaced.

The Pydantic model was **not** loosened; both translations happen at the repository
boundary as required.

---

## 4. Proof: the new suite fails pre-fix, passes post-fix

Same file, same real Postgres, only the fix stashed away:

```
$ git stash push -- app/repositories/postgres_lead_repo.py

pre-fix  →  14 failed, 5 passed
  failures are the F6 signature, e.g.:
  pydantic_core._pydantic_core.ValidationError: 1 validation error for LeadResponse
    Input should be a valid string [type=string_type, input_value=IPv4Address('203.0.113.60'),
    input_type=IPv4Address]
  (14 of the 19 tests fail because every create/read path hits _row_to_response)

$ git stash pop

post-fix →  19 passed in 9.98s
```

This is the confirmation the milestone required — the suite demonstrably catches F6 (and
would have caught F8 as `AmbiguousParameterError` pre-fix, which the 3-failure diagnostic
run showed before the placeholder fix).

---

## 5. New live-Postgres test suite

`tests/repositories/test_postgres_lead_repo_live.py` — **19 tests**, real asyncpg, no mocks.

- Reassigns `app.core.database.DATABASE_URL` at import (conftest sets it `""`), default
  `postgresql://flyrank:flyrank_pass@127.0.0.1:5432/flyrank`, override
  `FLYRANK_TEST_DATABASE_URL`.
- Per-test fixture creates a parent `widgets` row (leads has an FK to `widgets.id`), and
  tears down by deleting the widget (cascade) + closing the pool.
- Coverage (every public method + edge paths):
  - `create` all-fields, IPv4 round-trip, **IPv6 round-trip**, `unknown` → `0.0.0.0` sentinel
  - `get_by_id` hit + miss
  - `list_by_widget` total/pagination, filters (search, status, spam range, date range, sort), honeypot default-exclude + include
  - `list_by_tenant`
  - `update_status` plain, with geo extras, miss
  - `delete` hit + miss, `batch_delete` selected + empty
  - `get_stats`, `get_tenant_stats`, `get_export_data`
- Excluded from the default and CI runs via `pyproject.toml`:
  `addopts = "--ignore=tests/test_db_schema.py --ignore=tests/repositories/test_postgres_lead_repo_live.py"`.
  Verified: `tests/repositories/` collects **170** with addopts, **189** without
  (170 + 19 live) — the live file is correctly skipped by CI, and runs when passed
  explicitly with `-o addopts=""`.
- AGENTS.md "Testing quirks" documents the suite and how to run it.

---

## 6. Live-Postgres suite output (standalone)

```
$ python -m pytest tests/repositories/test_postgres_lead_repo_live.py -o addopts="" -v

...collected 19 items
test_create_returns_lead_with_all_expected_fields PASSED
test_create_ipv6_address_round_trips_as_string PASSED
test_create_invalid_ip_uses_sentinel PASSED
test_get_by_id_returns_none_for_missing PASSED
test_list_by_widget_returns_items_and_total PASSED
test_list_by_widget_applies_filters_and_pagination PASSED
test_list_by_widget_excludes_honeypot_by_default PASSED
test_list_by_widget_includes_honeypot_when_requested PASSED
test_list_by_tenant_returns_items_and_total PASSED
test_update_status_updates_status_and_returns_updated PASSED
test_update_status_with_geo_extras PASSED
test_update_status_returns_none_for_missing PASSED
test_delete_returns_true_and_removes PASSED
test_delete_returns_false_for_missing PASSED
test_batch_delete_removes_selected PASSED
test_batch_delete_empty_returns_zero PASSED
test_get_stats_returns_expected_shape PASSED
test_get_tenant_stats_returns_expected_shape PASSED
test_get_export_data_returns_model_dumps PASSED
============================= 19 passed in 10.79s =============================
```

---

## 7. M27 submit repro — now 201 (was 500)

Same request that returned `500 Internal Server Error` in M27, run against the rebuilt
compose stack after the fix:

```
REQUEST
POST http://localhost:8000/public/widget/e335f32a-b224-49f8-ae64-5a32359726f4/submit
Headers: Origin: https://demo.example.com | X-Forwarded-For: 8.8.8.8 | Content-Type: application/json
Body: {"form_data":{"name":"Probe4 User","email":"probe4@example.com","phone":"+15550004004"},"referer":"https://demo.example.com/probe4"}

RESPONSE
HTTP/1.1 201 Created
date: Sat, 01 Aug 2026 04:59:46 GMT
server: uvicorn
content-length: 107
content-type: application/json
access-control-allow-origin: *

{"success":true,"message":"Thank you for your submission","lead_id":"13e775a3-0dd3-4fd7-b170-9f17400cfa7a"}
```

The previously-500 read path is also restored: `GET /widgets/{seed}/leads` (Bearer)
returned **200** with the stored lead (`ip=172.18.0.1`, `status=pending`).

---

## 8. Mocked-suite regression — CI command

Verbatim pytest invocation from `.github/workflows/ci.yml`:

```
946 passed in 57.80s
TOTAL ... 2885 statements, 0 missing → 100% coverage
```

**946 passed / 0 failed / 100% coverage** — exactly matches the M25 baseline, with the
live suite correctly excluded from collection (verified, see §5).

---

## 9. F7 carried forward — unchanged, still Tier C

F7 is M27's X-Forwarded-For finding (there labeled F2): `lead_service.py:104` uses
`request.client.host`, and uvicorn runs without `--proxy-headers`, so client IP is always
the direct TCP peer. Confirmed again in this milestone's repro: the submit sent with
`X-Forwarded-For: 8.8.8.8` stored `ip_address = 172.18.0.1` (the docker gateway).

**Not fixed, tier unchanged.** Fixing proxy-header trust requires a decision about which
proxies are trusted — a security-relevant design choice, per plan §1 a Tier C item
(flag only, Ahmed's call). Consequences in the current compose-only deployment: all
external visitors share one per-IP rate-limit bucket, and geo enrichment resolves a
private/reserved IP (providers return nothing). This becomes a Tier B blocker only when
deploying behind a real reverse proxy.

---

## 10. Cleanup

- Batch-deleted the M28 repro lead via `POST /widgets/{seed}/leads/batch-delete` → 204.
- Live-suite fixture removes its own widget/leads each test; verified via psql:
  `seed_leads=0`, `live_test_leads=0`, `live_test_widgets=0`.
- `docker compose down` (DB volume retained); working tree clean apart from the M27 report
  doc (still intentionally untracked).

---

## 11. Findings summary

| ID | Description | Tier | Disposition |
|---|---|---|---|
| F6 | asyncpg `IPv4Address`/`IPv6Address` → `LeadResponse.ip_address: str` → 500 on every live lead write/read | B | **FIXED** (`e8a39fc`) — `str(row["ip_address"])` at repo boundary |
| F8 | `update_status` geo extras bind `$3` to both timestamptz and text → asyncpg `AmbiguousParameterError` live | B | **FIXED** (`e8a39fc`) — geo placeholders start at `$4` |
| F7 | X-Forwarded-For not honored; client IP = direct TCP peer | C | Carried forward, **not fixed** — proxy-trust is a design decision for Ahmed |

**Beyond the one field:** the audit confirmed only `ip_address` needed a conversion fix,
but the new live suite surfaced one additional real defect (F8) in the same method that
the mocked tests could never execute.
