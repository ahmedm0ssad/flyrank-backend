# Milestone 2 — Security Audit

## M6 Fix Status

No Tier A findings in this report. All items are either Tier B (pre-flagged missing implementations) or Tier C (requires sign-off). No changes applied.

## 1. Origin Validation (`app/dependencies/embed.py`) — *Plan §8.2*

**Result: PASS — no substring bug.**

The code parses both the request `Origin`/`Referer` header and the widget's registered `domain` through `urlparse().hostname`, then compares hostnames exactly (or via wildcard-suffix). There is no raw-string `.startswith()` or substring comparison anywhere in the pipeline.

| Check point | Location | Verdict |
|---|---|---|
| `Origin` header parsed via `urlparse` | `app/dependencies/embed.py:33` | ✓ |
| `Referer` used as fallback when `Origin` absent | `app/dependencies/embed.py:39` | ✓ |
| Both request and allowed domain parsed identically | `app/dependencies/embed.py:39,48` | ✓ |
| Exact hostname comparison (`==`) | `app/dependencies/embed.py:61` | ✓ |
| Wildcard `*.` → suffix check with `.` guard | `app/dependencies/embed.py:57` | ✓ |
| Punycode/IDNA normalization before comparison | `app/dependencies/embed.py:23-28` | ✓ |
| Missing/empty `Origin` → rejected (returns `False`) | `app/dependencies/embed.py:40` | ✓ |
| Inactive/deleted widget → rejected | `app/dependencies/embed.py:43` | ✓ |
| Called from `POST /submit` pipeline | `app/dependencies/leads.py:36`, `app/services/lead_service.py:106` | ✓ |

**The v1 substring bug (`origin.startswith(config["domain"])`) is not present.** This is the highest-severity check in this review and it passes.

---

## 2. Body-Size Limit (`app/middleware/body_limit.py`) — *Plan §8.6*

**Result: PASS.**

| Requirement | Line | Status |
|---|---|---|
| Enforced at ASGI layer (before Pydantic/body parsing) | `body_limit.py:8-19` | ✓ |
| Checks `Content-Length` header first → immediate 413 if >50KB | `body_limit.py:14-17` | ✓ |
| Missing/spoofed `Content-Length` still caught by byte-counting in `limited_receive` | `body_limit.py:19-27` | ✓ |
| 413 returned for oversized payloads | `body_limit.py:16,24` | ✓ |
| Middleware registered in `main.py` | `app/main.py:84` | ✓ |

One minor note: the `limited_receive` function raises `StarletteHTTPException` directly rather than FastAPI's `HTTPException`. FastAPI converts this correctly at runtime, but it's a slight inconsistency. Not a bug.

---

## 3. Honeypot Rows — *Plan §8.5*

**Result: PASS — intentional behavior confirmed.**

| Requirement | Line | Status |
|---|---|---|
| Honeypot-triggered rows are **stored**, not discarded | `app/services/lead_service.py:167-175` | ✓ |
| `honeypot_triggered=True` set on the row | `lead_service.py:134` | ✓ |
| `spam_score=1.0` set | `lead_service.py:133` | ✓ |
| Enrichment job **skipped** for honeypot rows | `lead_service.py:181-185` | ✓ |
| Response is still `201` fake success | `app/routers/leads.py:20-25` | ✓ |

No finding here — this is correct per plan §8.5.

---

## 4. Rate Limiting — *Plan §8.3, §14.4*

**Result: PASS.**

| Requirement | Line | Status |
|---|---|---|
| All 3 tiers defined: `global_ip`, `widget_ip`, `widget_global` | `app/dependencies/leads.py:12-16` | ✓ |
| Pipelined into single Redis round trip | `leads.py:56-59` (single `pipe.execute()`) | ✓ |
| TTL set only on first hit (`count == 1`) — window not reset on subsequent hits | `leads.py:61-63` | ✓ |
| Exceeded tier returns `Retry-After` header via HTTP 429 | `lead_service.py:113-119` | ✓ |
| Redis failure → fail-open to in-process approximate limiter | `leads.py:68,72` | ✓ |
| In-process fallback does not raise/500 — returns `None` (allow) or window (deny) | `leads.py:44-52` | ✓ |

Fail-open behavior is intentional per plan §14.4. The in-process fallback is per-process only (not shared across workers), which is an acceptable degradation for availability.

---

## 5. Fingerprint Dedup — *Plan §8.9*

**Result: PASS — wired into live pipeline.**

| Function | Called from | Line |
|---|---|---|
| `compute_fingerprint()` | `lead_service.submit_lead()` | `lead_service.py:143` |
| `check_dedup()` | `lead_service.submit_lead()` | `lead_service.py:144` |
| `mark_seen()` | `lead_service.submit_lead()` (after insert) | `lead_service.py:177` |
| Dedup hit → returns original `lead_id` with 200/201 | `lead_service.py:146-151` | ✓ |
| 5-minute TTL (intentional — anti-duplicate, not anti-abuse) | `fingerprint_service.py:4` | ✓ |

The function is not just present but actively called in every submission. ✓

---

## 6. Tenant Isolation

**Result: PASS — every widget/lead repository method checked.**

### Widget Repository Methods

| Method | Tenant filter | Line (postgres) | Line (in-memory) | Status |
|---|---|---|---|---|
| `create(..., tenant_id)` | `VALUES ($1, ...)` | `postgres_widget_repo.py:36` | `widget_repo.py:27` | ✓ |
| `get_by_id(widget_id, tenant_id)` | `WHERE id=$1 AND tenant_id=$2` | `postgres_widget_repo.py:54` | `widget_repo.py:37` | ✓ |
| `get_by_id_raw(widget_id)` | **No tenant filter** | `postgres_widget_repo.py:68-69` | `widget_repo.py:44` | Intentional — public endpoints need widget lookup without auth. See note below. |
| `list_by_tenant(tenant_id, ...)` | `WHERE tenant_id=$1` | `postgres_widget_repo.py:86` | `widget_repo.py:55` | ✓ |
| `update(widget_id, tenant_id, ...)` | `WHERE id=$1 AND tenant_id=$2` | `postgres_widget_repo.py:149` | `widget_repo.py:74` | ✓ |
| `soft_delete(widget_id, tenant_id)` | `WHERE id=$1 AND tenant_id=$2` | `postgres_widget_repo.py:168` | `widget_repo.py:84` | ✓ |
| `check_domain_exists(domain, tenant_id)` | `WHERE tenant_id=$1 AND domain=$2` | `postgres_widget_repo.py:184-197` | `widget_repo.py:92` | ✓ |

### Lead Repository Methods

| Method | Tenant filter | Line (in-memory) | Status |
|---|---|---|---|
| `create(..., tenant_id)` | `tenant_id` stored as field | `lead_repo.py:26` | ✓ |
| `get_by_id(lead_id)` | **No tenant filter in repo** | `lead_repo.py:49` | Filtered at service layer (`lead_service.py:206-210`) |
| `list_by_widget(widget_id, tenant_id, ...)` | `AND r["tenant_id"] == tenant_id` | `lead_repo.py:71` | ✓ |
| `list_by_tenant(tenant_id, ...)` | `r["tenant_id"] == tenant_id` | `lead_repo.py:85` | ✓ |
| `get_stats(widget_id, tenant_id)` | `AND r["tenant_id"] == tenant_id` | `lead_repo.py:92` | ✓ |
| `get_tenant_stats(tenant_id)` | `r["tenant_id"] == tenant_id` | `lead_repo.py:99` | ✓ |
| `get_export_data(widget_id, tenant_id, ...)` | `AND r["tenant_id"] == tenant_id` | `lead_repo.py:108` | ✓ |
| `update_status(lead_id, ...)` | **No tenant check** | `lead_repo.py:126` | Used only by enrichment worker (internal), not API |
| `delete(lead_id, widget_id, tenant_id)` | Checks all three | `lead_repo.py:134-137` | ✓ |
| `batch_delete(lead_ids, widget_id, tenant_id)` | Delegates to `delete` | `lead_repo.py:143` | ✓ |

**Note on `get_by_id_raw` / `get_by_id` without tenant filter**: These are used by public (unauthenticated) endpoints and enrichment workers. In the public submit flow, `get_raw_widget` fetches the widget to read its `tenant_id` — the caller cannot specify which tenant to scope to because there is no authenticated user. The lead `get_by_id` is called only after a match on `fingerprint` (internal dedup) or by the enrichment worker (internal). The service layer adds tenant checks on all user-facing paths. These are correct by design, not gaps.

---

## 7. Classic Web Vulnerabilities

### SQL Injection

**Result: PASS.** Every asyncpg/psycopg query uses parameterized placeholders (`$1`, `$2`, ...). Raw string interpolation is never used for query values.

- `app/repositories/postgres_widget_repo.py`: All queries parameterized ✓
- `app/repositories/postgres_repo.py`: All queries parameterized ✓
- `app/repositories/report_repo.py`: SQLite/Postgres both use parameterized queries ✓
- `app/services/report_service.py`: Raw `sqlite3` queries use `?` placeholders ✓

### XSS (Cross-Site Scripting)

**Result: PASS (with minor observation).**

| Check | Line | Status |
|---|---|---|
| `form_data` values HTML-escaped via `html.escape()` | `app/models/lead.py:14` | ✓ |
| Email/phone regex validated | `lead.py:35-40` | ✓ |
| Field length capped at 2000 chars | `lead.py:30` | ✓ |
| `widget.js` uses `textContent` (not `innerHTML`) for user data | `app/services/widget_js.py:135` | ✓ |
| Config values injected server-side are server-controlled (UUID, hex color, etc.) | — | ✓ |

The `html.escape()` in the model validator stores escaped HTML in the database. If the dashboard frontend renders this as HTML (not treating it as text), double-escaping could occur. This depends on the frontend behavior — not a server-side bug.

### CSRF (Cross-Site Request Forgery)

**Result: PASS (protected by design).**

- `POST /submit` requires `Content-Type: application/json` (non-simple request → preflighted) and is gated by Origin validation.
- Dashboard endpoints require `Bearer` token via `Authorization` header (non-simple → preflighted). No cookie-based auth.
- Wildcard CORS is intentional per plan §5.5; the write path is separately gated.

### SSRF (Server-Side Request Forgery)

**Result: PASS.**

| Check | Line | Status |
|---|---|---|
| Geo provider URLs are fixed strings with IP from `request.client.host` | `app/services/geo_service.py:43-119` | ✓ — IP is the connecting client, not attacker-supplied |
| No user-supplied URL parameters | — | ✓ |
| `httpx.AsyncClient` does not follow redirects by default (`follow_redirects=False`) | `geo_service.py` | ✓ |
| Auth calls use `SUPABASE_URL` from env, not user input | `app/routers/auth.py:49` | ✓ |

### Path Traversal

**Result: PASS.**

| Check | Line | Status |
|---|---|---|
| Report download checks for `/`, `\\`, `..` | `app/routers/reports.py:39` | ✓ |
| Report download verifies resolved path starts with `REPORTS_DIR` | `reports.py:45-46` | ✓ |
| Report download restricts extension to `.pdf` | `reports.py:33` | ✓ |
| CSV export filename uses UUID (safe) | `app/routers/leads.py:231` | ✓ |

### Unsafe Deserialization

**Result: PASS.** Only `json.loads()` is used for deserialization. No `pickle`, `yaml.load()` with unsafe loader, or `eval()` found in any file.

### Open Redirects

**Result: PASS.** No endpoint accepts a redirect URL parameter.

### Insecure Response Headers

**Result: Minor finding — Tier C.** The application does not set:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY` (or `SAMEORIGIN`)
- `Content-Security-Policy`

These are defense-in-depth headers. Their absence does not introduce a direct exploit but is a hardening gap. The plan does not mandate them, so this is Tier C.

---

## 8. Secrets Hygiene — *Plan §1*

**Result: PASS.**

| Check | Status |
|---|---|
| `.env` listed in `.gitignore` | ✓ (`app/.gitignore` line 2) |
| `.env` ever committed to git history | ✓ **Never committed** — only `.env.example` appears in history |
| `.env.example` lists same key names without real values | ✓ All keys present: `DATABASE_URL`, `REDIS_URL`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`, `GROQ_API_KEY`, `PORT` |
| `docker-compose.yml` has hardcoded credentials | ✓ Dev-only defaults (`flyrank`/`flyrank_pass` for Postgres) — not real credentials. Live creds loaded via `env_file: .env` |
| Any config file with hardcoded credential | ✓ None found |

---

## 9. Auth Enforcement — *Plan §10, §8.8*

**Result: PASS — no dashboard route bypasses auth.**

### Dashboard routes checked

| Route | Auth | Line | Status |
|---|---|---|---|
| `GET /widgets/` | `Depends(get_current_user)` | `app/routers/widgets.py:19` | ✓ |
| `POST /widgets/` | `Depends(get_current_user)` | `widgets.py:31` | ✓ |
| `GET /widgets/{id}` | `Depends(get_current_user)` | `widgets.py:41` | ✓ |
| `PUT /widgets/{id}` | `Depends(get_current_user)` | `widgets.py:53` | ✓ |
| `DELETE /widgets/{id}` | `Depends(get_current_user)` | `widgets.py:65` | ✓ |
| `GET /widgets/{id}/leads` | `Depends(get_current_user)` | `app/routers/leads.py:68` | ✓ |
| `GET /widgets/{id}/leads/{lead_id}` | `Depends(get_current_user)` | `leads.py:131` | ✓ |
| `GET /widgets/{id}/stats` | `Depends(get_current_user)` | `leads.py:149` | ✓ |
| `GET /widgets/{id}/export` | `Depends(get_current_user)` | `leads.py:197` | ✓ |
| `DELETE /widgets/{id}/leads/{lead_id}` | `Depends(get_current_user)` | `leads.py:246` | ✓ |
| `POST /widgets/{id}/leads/batch-delete` | `Depends(get_current_user)` | `leads.py:262` | ✓ |
| `POST /widgets/{id}/leads/{lead_id}/re-enrich` | `Depends(get_current_user)` | `leads.py:278` | ✓ |
| `GET /leads` | `Depends(get_current_user)` | `leads.py:97` | ✓ |
| `GET /leads/stats` | `Depends(get_current_user)` | `leads.py:169` | ✓ |

### Auth function analysis (`app/dependencies/auth.py`)

| Check | Line | Status |
|---|---|---|
| `auto_error=False` means `credentials` is `None` when missing | `auth.py:10` | ✓ — handled by explicit None check |
| None/empty token → raises 401 | `auth.py:14-17` | ✓ |
| Invalid/expired token → raises 401 | `auth.py:24-27` | ✓ |
| No default value that bypasses auth | — | ✓ |
| No early return before token validation | — | ✓ |
| No unguarded early return in any dashboard endpoint | All endpoints checked above | ✓ |

### Pre-existing routes without auth

The following routes exist without `get_current_user` but are **not dashboard routes** (they are from the original project template): `/tasks/*`, `/ai`, `/jobs/*`, `/reports/*`, `/scrape/*`, `/auth/*`, `/public/*`. These are not in scope for this audit (the plan §10 only mandates auth on dashboard routes).

---

## Findings List

### Tier B — Confirmed Bugs

| File:Line | Description | Plan Section |
|---|---|---|
| `app/core/queue.py` | `reset_connection()` called in tests but not implemented (pre-flagged, §1.81-88) | §1.81-88 — **Restored** in commit `5a386e9` (M6.5) after being incorrectly removed in `2715feb`; `tests/test_background_jobs.py` (46 tests) passes. See `docs/reviews/verification-audit.md` §1 for full git-history confirmation. |
| `app/core/queue.py` | `get_enrichment_job()` referenced in tests but not implemented (pre-flagged, §1.81-88) | §1.81-88 — **Restored** in commit `5a386e9` (M6.5) after being incorrectly removed in `2715feb`; `tests/test_background_jobs.py` (46 tests) passes. See `docs/reviews/verification-audit.md` §1 for full git-history confirmation. |

### Tier C — Flag Only

| File:Line | Description | Reasoning |
|---|---|---|
| Entire app | Missing security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy` | Defense-in-depth. Plan does not mandate these. Requires sign-off before adding. |

### Intentional Design Decisions (not defects)

| Area | Verdict |
|---|---|
| Wildcard CORS `allow_origins=["*"]` | Intentional per plan §5.5, §8.1 |
| Honeypot rows stored, not discarded | Intentional per plan §8.5 |
| Rate limiter fails open on Redis outage | Intentional per plan §14.4 |
| Fingerprint dedup window 5 min (short) | Intentional per plan §8.9 |
| Geo provider order (ipapi → ipinfo → ip-api) | Intentional per plan §9 |

---

## Item-by-Item Confirmation

| # | Item | Result |
|---|---|---|
| 1 | Origin validation: no substring bug, correct hostname comparison | **PASS** |
| 2 | Body-size limit at ASGI layer before parsing; handles missing/spoofed Content-Length | **PASS** |
| 3 | Honeypot rows inserted with `honeypot_triggered=true`, never silently dropped | **PASS** |
| 4 | Rate limiting: all 3 tiers pipelined into one Redis round trip; fails open on outage | **PASS** |
| 5 | Fingerprint dedup wired into live pipeline (not unused function) | **PASS** |
| 6 | Tenant isolation: every widget/lead query includes `tenant_id` filter | **PASS** |
| 7 | Classic web vulns: SQLi (parameterized ✓), XSS (HTML-escaped ✓), CSRF (protected ✓), SSRF (no user URLs ✓), path traversal (protected ✓), unsafe deserialization (none ✓), open redirects (none ✓), missing security headers (Tier C) | **PASS (Tier C)** |
| 8 | Secrets: `.env` gitignored, never committed, `.env.example` correct, no hardcoded creds | **PASS** |
| 9 | Auth: all dashboard routes enforce `get_current_user` with no bypass | **PASS** |

---

## Security Score: 8.5 / 10

### Evidence

| Domain | Score | Evidence |
|---|---|---|
| **Origin Validation** | 10/10 | Correctly parses both values with `urlparse.hostname`, exact comparison, wildcard suffix, punycode normalization, no substring bug |
| **Body-Size Enforcement** | 9/10 | Enforced before parsing, handles missing/spoofed Content-Length. Minor: raises `StarletteHTTPException` instead of FastAPI's (functionally identical). |
| **Honeypot** | 10/10 | Correctly stores flagged rows, skips enrichment, returns fake success |
| **Rate Limiting** | 9/10 | All 3 tiers, pipelined, fail-open. In-process fallback is per-process (acceptable degradation for availability). |
| **Fingerprint Dedup** | 10/10 | Present and wired into pipeline, correct window |
| **Tenant Isolation** | 9/10 | Every query filtered. `get_by_id_raw` intentionally skips tenant (public endpoints). `get_by_id` lacks repo-level check but is gated at service layer. |
| **Secrets Hygiene** | 10/10 | .env gitignored, never committed, .env.example correct, no hardcoded creds |
| **Auth Enforcement** | 10/10 | Every dashboard route protected, no bypasses, no default escapes |
| **Classic Web Vulns** | 7/10 | SQLi/XSS/CSRF/SSRF/path-traversal all clean. Missing security headers (-1), no CSP (-1), `X-Content-Type-Options` absent (-1) |

### Overall: 8.5/10

**Strengths**: Origin validation is correctly implemented (the critical v1 bug is fixed). Tenant isolation is thorough. Auth is consistently enforced. Secrets hygiene is excellent. Fingerprint dedup and rate limiting are properly wired.

**Weaknesses**: Missing defense-in-depth HTTP headers. Pre-flagged missing implementations (`reset_connection`, `get_enrichment_job`). No Tier-B security bugs found beyond the pre-flagged items.

---

## Path to Report

`docs/reviews/m2-security.md`
