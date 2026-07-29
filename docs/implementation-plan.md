# Embeddable Widget & Lead-Capture Platform — Implementation Plan (v2)

*FlyRank Backend AI — Week 9 Capstone*

**Changelog from v1**: fixed origin-validation bypass, moved payload-size enforcement before body parsing, fully specified 3-tier rate limiting, resolved honeypot storage contradiction, unified re-enrich to `POST`, unified CORS description, fixed milestone parallelization vs. dependency graph mismatch, wired the idempotency fingerprint into the pipeline, added widget.js cache-busting, reordered geo provider chain.

---

## Table of Contents

1. [Existing Architecture Analysis](#1-existing-architecture-analysis)
2. [Folder Structure](#2-folder-structure)
3. [Database Design](#3-database-design)
4. [API Design](#4-api-design)
5. [Embed System](#5-embed-system)
6. [Submission Pipeline](#6-submission-pipeline)
7. [Background Jobs — RQ Integration](#7-background-jobs--rq-integration)
8. [Security](#8-security)
9. [Geo Enrichment](#9-geo-enrichment)
10. [Dashboard APIs](#10-dashboard-apis)
11. [Testing Strategy](#11-testing-strategy)
12. [Implementation Roadmap](#12-implementation-roadmap)
13. [Git Plan](#13-git-plan)
14. [Risks & Mitigations](#14-risks--mitigations)
15. [Summary](#15-summary)

---

## 1. Existing Architecture Analysis

### Reusable Modules

| Module | How to Reuse |
|--------|--------------|
| `app/main.py` | Lifespan pattern, router inclusion, exception handlers, Redis async client management |
| `app/database.py` | asyncpg pool management, `is_postgres_enabled()` check, connection lifecycle |
| `app/queue.py` | Redis sync connection, RQ queue creation, job hash CRUD (`create_job`, `update_job`, `get_job`), idempotency key support, TTL patterns, retry configuration |
| `app/worker.py` | Worker entry point — add new queue names to watched queues |
| `app/dependencies/auth.py` | `get_current_user` — Supabase JWT validation, reuse for all dashboard endpoints |
| `app/repositories/protocol.py` | Repository Protocol pattern — replicate for `WidgetRepository` and `LeadRepository` |
| `app/repositories/postgres_repo.py` | asyncpg query patterns, parameterized SQL, connection acquisition — reuse as template |
| `app/repositories/report_repo.py` | Dual-support pattern (SQLite fallback for dev) — adapt for leads |
| `app/services/report_worker.py` | RQ worker lifecycle pattern (STARTED → FINISHED/FAILED, retries, alert) |
| `app/services/alert.py` | Failure alert stub — extend for enrichment failures |
| `app/routers/reports.py` | Public file download pattern — reuse for widget.js delivery |
| Docker services | `db` (PostgreSQL 16), `redis` (Redis 7), `app` — all already available, no new services needed |
| `tests/conftest.py` | `_FakeRedis`, `_FakeQueue`, `TestClient`, mock fixtures — extend for widget/lead mocks |

### Existing Infrastructure Ready for Use

- **Redis**: Already available with sync + async clients. Used for widget config cache, tiered rate-limit counters, submission-fingerprint dedup, enrichment job tracking, geo-by-IP cache.
- **RQ**: Two queues (`ai-jobs`, `report-jobs`) already exist. Add `enrichment-jobs` queue for async geo/spam enrichment.
- **PostgreSQL**: Tables already managed via `db/init.sql`. Add `widgets`, `leads`, `rate_limits` tables.
- **Docker Compose**: No new services needed. All components (app, db, redis) already configured.
- **Authentication**: Supabase JWT already validated in `get_current_user`. Widget owners authenticate via same mechanism.
- **CORS**: Not currently configured — must be added specifically for this feature (see §5.5 / §8.1 for the single, consistent design).

---

## 2. Folder Structure

```
app/
├── embed/                          # NEW: embeddable widget package
│   ├── __init__.py
│   ├── router.py                   # Public widget endpoints
│   ├── service.py                  # Embed business logic, snippet generation
│   ├── widget_js.py                # widget.js dynamic generation (versioned/cache-busted)
│   └── dependencies.py             # Origin validation, rate limit deps
├── leads/                          # NEW: lead capture package
│   ├── __init__.py
│   ├── router.py                   # Public submit + dashboard lead endpoints
│   ├── service.py                  # Lead pipeline orchestration
│   ├── worker.py                   # RQ enrichment worker
│   ├── spam.py                     # Spam detection heuristics + honeypot handling
│   ├── geo.py                      # Geo enrichment provider chain
│   ├── fingerprint.py              # NEW: submission fingerprint (dedup / idempotency)
│   ├── dependencies.py             # Widget ownership verification, rate limit checks
│   ├── models.py                   # Pydantic schemas for leads
│   └── repository.py               # LeadRepository
├── widgets/                        # NEW: widget management dashboard
│   ├── __init__.py
│   ├── router.py                   # Dashboard widget CRUD endpoints
│   ├── service.py                  # Widget management business logic
│   ├── models.py                   # Pydantic schemas for widgets
│   └── repository.py               # WidgetRepository
├── middleware/                     # NEW
│   ├── __init__.py
│   ├── cors.py                     # Static CORS + per-widget origin validation dependency
│   └── body_limit.py               # NEW: ASGI-layer request body size cap (runs before parsing)
├── dependencies/                   # EXTEND
│   └── auth.py                     # (unchanged, reuse as-is)
├── main.py                         # EXTEND: add new routers, CORSMiddleware, BodyLimitMiddleware
├── queue.py                        # EXTEND: add ENRICHMENT_QUEUE_NAME, enrichment job helpers
├── database.py                     # EXTEND: add enrichment table DDL if needed
db/
└── init.sql                        # EXTEND: add widgets, leads, rate_limits tables
tests/
├── conftest.py                     # EXTEND: add widget/lead fixtures
├── embed/
│   ├── test_router.py
│   ├── test_service.py
│   └── test_widget_js.py
├── leads/
│   ├── test_router.py
│   ├── test_service.py
│   ├── test_worker.py
│   ├── test_spam.py
│   ├── test_geo.py
│   ├── test_fingerprint.py         # NEW
│   └── test_repository.py
├── widgets/
│   ├── test_router.py
│   ├── test_service.py
│   └── test_repository.py
└── middleware/
    ├── test_cors.py
    └── test_body_limit.py          # NEW
```

---

## 3. Database Design

### Table: `widgets`

**Purpose**: Each row is a configurable embed widget owned by a tenant (user). Stores branding, form fields, and allowed origins.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | |
| `tenant_id` | `UUID` | `NOT NULL` | Supabase user ID |
| `name` | `VARCHAR(200)` | `NOT NULL` | Display name for dashboard |
| `domain` | `VARCHAR(500)` | `NOT NULL` | Allowed origin, e.g. `https://myshop.com` or wildcard `https://*.myshop.com` |
| `config` | `JSONB` | `NOT NULL DEFAULT '{}'` | Fields: `{"brand_color":"#000","button_text":"Get Quote","fields":["name","email","phone"],"success_message":"Thanks!","honeypot_field":"_hp_a3f9"}` |
| `js_version` | `INTEGER` | `NOT NULL DEFAULT 1` | Bumped on every `PUT`; used for widget.js cache-busting (§5.4) |
| `active` | `BOOLEAN` | `NOT NULL DEFAULT TRUE` | Soft disable |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | |

**Indexes**:
- `PRIMARY KEY (id)`
- `CREATE INDEX idx_widgets_tenant ON widgets(tenant_id)` — dashboard listing
- `CREATE UNIQUE INDEX idx_widgets_domain ON widgets(tenant_id, domain)` — one widget per domain per tenant

> **Note**: `config.honeypot_field` replaces a plain boolean `honeypot: true`. The field *name* itself is the randomized secret (see §8.5), so it must be stored, not just a flag.

---

### Table: `leads`

**Purpose**: Every form submission from a widget. Enriched asynchronously with geo and spam data.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | |
| `widget_id` | `UUID` | `NOT NULL REFERENCES widgets(id) ON DELETE CASCADE` | |
| `tenant_id` | `UUID` | `NOT NULL` | Denormalized for query performance |
| `form_data` | `JSONB` | `NOT NULL` | The submitted form fields |
| `ip_address` | `INET` | `NOT NULL` | |
| `user_agent` | `TEXT` | | |
| `referer` | `TEXT` | | |
| `fingerprint` | `VARCHAR(64)` | `NOT NULL` | SHA-256 of `widget_id + ip + normalized(form_data)`, used for dedup (§6, §8.9) |
| `geo_country` | `VARCHAR(100)` | | Populated by enrichment worker |
| `geo_city` | `VARCHAR(200)` | | |
| `geo_region` | `VARCHAR(200)` | | |
| `geo_isp` | `VARCHAR(200)` | | |
| `geo_provider` | `VARCHAR(50)` | | Which provider succeeded |
| `spam_score` | `REAL` | `DEFAULT 0.0` | 0.0 = clean, 1.0 = definitely spam |
| `spam_reasons` | `JSONB` | | Array of reasons if flagged |
| `honeypot_triggered` | `BOOLEAN` | `NOT NULL DEFAULT FALSE` | See §8.5 — these rows ARE stored, just excluded from default dashboard views |
| `status` | `VARCHAR(20)` | `NOT NULL DEFAULT 'pending'` | `pending`, `enriched`, `failed` |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | |

**Indexes**:
- `PRIMARY KEY (id)`
- `CREATE INDEX idx_leads_widget ON leads(widget_id, created_at DESC)` — dashboard lead list for a widget
- `CREATE INDEX idx_leads_tenant ON leads(tenant_id, created_at DESC)` — cross-widget dashboard
- `CREATE INDEX idx_leads_status ON leads(status) WHERE status = 'pending'` — enrichment worker poll
- `CREATE INDEX idx_leads_spam ON leads(spam_score)` — spam filtering
- `CREATE INDEX idx_leads_fingerprint ON leads(fingerprint, created_at DESC)` — dedup window lookups
- `CREATE INDEX idx_leads_honeypot ON leads(honeypot_triggered) WHERE honeypot_triggered = FALSE` — default dashboard queries filter this out cheaply

---

### Table: `rate_limits`

**Purpose**: Persistent audit trail for rate-limit decisions. Redis is the primary enforcement store (hot path); this table is written asynchronously / best-effort for audit and for the DB-fallback mode if Redis is unavailable (see §8.3, §14.4).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `BIGSERIAL` | `PRIMARY KEY` | |
| `ip_address` | `INET` | `NOT NULL` | |
| `widget_id` | `UUID` | `REFERENCES widgets(id) ON DELETE CASCADE` | Nullable for global (cross-widget, per-IP) limits |
| `scope` | `VARCHAR(30)` | `NOT NULL` | One of `global_ip`, `widget_ip`, `widget_global` — see §8.3 |
| `endpoint` | `VARCHAR(50)` | `NOT NULL` | e.g. `submit` |
| `window_start` | `TIMESTAMPTZ` | `NOT NULL` | Start of the current window |
| `count` | `INTEGER` | `NOT NULL DEFAULT 1` | |

**Indexes**:
- `CREATE INDEX idx_rate_limits_lookup ON rate_limits(ip_address, endpoint, scope, window_start)` — fast lookup
- No unique constraint — upsert pattern

---

### Migration Strategy

Add new DDL at the end of `db/init.sql`. All tables use `CREATE TABLE IF NOT EXISTS`. No destructive changes to existing tables.

---

## 4. API Design

### 4.1 Public Endpoints (Unauthenticated — CORS-enabled)

CORS design (applies to all endpoints in this section, stated once here instead of repeated inconsistently): `CORSMiddleware` is configured with `allow_origins=["*"]` so any browser can *load* these endpoints, but `POST /submit` additionally runs an **application-layer origin check** (§8.2) against the widget's registered `domain` before accepting the write. Reads (`config`, `widget.js`) are intentionally origin-agnostic since they expose no tenant data beyond public branding.

---

#### `GET /public/widget/{widget_id}/widget.js`

**Purpose**: Serve the dynamic embed script.

| Attribute | Value |
|-----------|-------|
| Method | `GET` |
| Path | `/public/widget/{widget_id}/widget.js?v={js_version}` |
| Auth | None |
| CORS | `Access-Control-Allow-Origin: *` |
| Cache | `Cache-Control: public, max-age=31536000, immutable` (version-qualified, see §5.4) |

**Response**: `Content-Type: application/javascript`

Returns a self-invoking function that:
1. Creates an iframe or injects a floating button
2. Fetches config from `/public/widget/{widget_id}/config`
3. Renders the form
4. On submit, POSTs to `/public/widget/{widget_id}/submit`

**Status codes**:
- `200` — widget.js served
- `404` — widget not found or inactive
- `410` — widget deleted

---

#### `GET /public/widget/{widget_id}/config`

**Purpose**: Return widget configuration for the widget.js script. Cached aggressively.

| Attribute | Value |
|-----------|-------|
| Method | `GET` |
| Path | `/public/widget/{widget_id}/config` |
| Auth | None |
| CORS | `Access-Control-Allow-Origin: *` |

**Response Schema**:
```json
{
  "widget_id": "uuid",
  "brand_color": "#000",
  "button_text": "Get a Quote",
  "fields": ["name", "email", "phone"],
  "success_message": "Thanks!",
  "honeypot_field": "_hp_a3f9"
}
```

**Status codes**:
- `200` — config returned
- `404` — widget not found

**Cache strategy**: Redis key `widget:config:{widget_id}` with 5-minute TTL. On miss, query DB, cache, return.

---

#### `POST /public/widget/{widget_id}/submit`

**Purpose**: Receive a lead submission.

| Attribute | Value |
|-----------|-------|
| Method | `POST` |
| Path | `/public/widget/{widget_id}/submit` |
| Auth | None (origin-validated) |
| Body limit | **50KB, enforced at the ASGI middleware layer before the body is read into Pydantic** (§8.6) |

**Request Schema**:
```json
{
  "form_data": {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1234567890",
    "message": "Interested in your services"
  },
  "_hp_a3f9": "",
  "referer": "https://myshop.com/contact"
}
```

- `form_data` — required, object, max 50KB total
- honeypot field — key name comes from the widget's cached `honeypot_field`; optional string, must be empty
- `referer` — optional string, max 500 chars

**Response Schema** (201):
```json
{
  "success": true,
  "message": "Thank you for your submission",
  "lead_id": "uuid"
}
```

**Status codes**:
- `201` — accepted
- `400` — validation error
- `403` — origin mismatch
- `404` — widget not found
- `413` — payload too large (rejected at middleware, before parsing)
- `429` — rate limited (any of the three tiers in §8.3)

**Error cases**:
- Honeypot filled → row IS stored with `honeypot_triggered = true`, spam-analytics-only; response is still `200`/`201` fake-success so the bot gets no signal (see §8.5)
- Rate limit exceeded → `429` with `Retry-After` header
- Origin mismatch → `403`
- Payload > 50KB → `413`, rejected before any parsing occurs
- Duplicate fingerprint within dedup window → `201` with the *original* `lead_id` returned (idempotent-looking to the client), no new row inserted (§6 step 9, §8.9)

---

### 4.2 Authenticated Endpoints (Dashboard — Bearer Token)

---

#### `GET /widgets`

List all widgets for the authenticated user.

| Attribute | Value |
|-----------|-------|
| Method | `GET` |
| Path | `/widgets` |
| Auth | `Bearer <token>` |
| Query | `?search=&active=&page=1&page_size=20` |

**Response**: Paginated list of widgets.

**Status codes**: `200`, `401`

---

#### `POST /widgets`

Create a new widget.

**Request Schema**:
```json
{
  "name": "My Contact Form",
  "domain": "https://myshop.com",
  "config": {
    "brand_color": "#2563eb",
    "button_text": "Get a Quote",
    "fields": ["name", "email", "phone"],
    "success_message": "Thanks! We'll be in touch."
  }
}
```

`honeypot_field` is **server-generated** (random per widget) and never accepted from the client — see §8.5.

**Validations**:
- `name`: 1–200 chars
- `domain`: valid URL with protocol; wildcard subdomain form `https://*.example.com` also accepted
- `config.fields`: array of strings, 1–20 items, each 2–50 chars
- `config.brand_color`: valid hex color
- `config.button_text`: 1–100 chars
- `config.success_message`: 1–500 chars

**Status codes**: `201`, `400`, `401`, `409` (domain already used)

---

#### `GET /widgets/{widget_id}`

Widget detail.

**Status codes**: `200`, `401`, `403` (not owner), `404`

---

#### `PUT /widgets/{widget_id}`

Update widget configuration. Same schema as POST, all fields optional. Bumps `js_version` and invalidates both cache keys (§5.4).

**Status codes**: `200`, `400`, `401`, `403`, `404`

---

#### `DELETE /widgets/{widget_id}`

Soft-delete (sets `active = FALSE`). Hard-delete after 30 days (cron job).

**Status codes**: `204`, `401`, `403`, `404`

---

#### `GET /widgets/{widget_id}/leads`

Paginated leads for a specific widget.

| Query | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | |
| `page_size` | int | 20 | Max 100 |
| `search` | str | | Search form_data JSONB |
| `status` | str | | `pending`, `enriched`, `failed` |
| `spam_min` | float | | Filter spam_score >= |
| `spam_max` | float | | Filter spam_score <= |
| `include_honeypot` | bool | `false` | Include honeypot-triggered rows (excluded by default) |
| `date_from` | date | | |
| `date_to` | date | | |
| `sort_by` | str | `created_at` | `created_at`, `spam_score` |
| `sort_order` | str | `desc` | |

**Status codes**: `200`, `401`, `403`, `404`

---

#### `GET /widgets/{widget_id}/leads/{lead_id}`

Single lead detail.

**Status codes**: `200`, `401`, `403`, `404`

---

#### `GET /widgets/{widget_id}/stats`

Statistics for a widget.

**Response**:
```json
{
  "total_leads": 1250,
  "today": 12,
  "this_week": 78,
  "this_month": 320,
  "avg_spam_score": 0.05,
  "honeypot_blocked": 340,
  "top_countries": [
    {"country": "United States", "count": 500},
    {"country": "United Kingdom", "count": 200}
  ],
  "leads_over_time": [
    {"date": "2026-07-20", "count": 25},
    {"date": "2026-07-21", "count": 30}
  ]
}
```

**Status codes**: `200`, `401`, `403`, `404`

---

#### `GET /widgets/{widget_id}/export`

Export leads as CSV.

**Query**: `?format=csv` (default: csv), `?date_from=&date_to=`

**Response**: `Content-Type: text/csv`, `Content-Disposition: attachment; filename="widget_{id}_leads.csv"`

---

#### `POST /widgets/{widget_id}/leads/{lead_id}/re-enrich`

Manually re-trigger geo enrichment for a lead whose status is `failed`. **`POST`, not `GET`** — this mutates state (enqueues a job), so it must not be a safe/idempotent-cacheable verb.

**Status codes**: `202` (re-enqueued), `401`, `403`, `404`, `409` (already `enriched`/in-progress)

---

#### `GET /dashboard/stats`

Aggregate statistics across all widgets for the tenant.

Same shape as per-widget stats but summed across all widgets.

---

## 5. Embed System

### 5.1 Widget Lifecycle

```
1. User creates widget via POST /widgets (Dashboard)
2. System generates widget_id (UUID) + random honeypot_field name
3. User gets embed snippet from dashboard
4. User pastes snippet into their website <head>
5. Visitor loads merchant page → widget.js loads
6. widget.js fetches config → renders form
7. Visitor submits → POST to /public/widget/{widget_id}/submit
8. Server processes submission pipeline
9. Server returns success/failure
10. Dashboard shows lead after enrichment
```

### 5.2 Embed Snippet Generation

Generated by `embed/service.py`. The snippet returned in the dashboard:

```html
<script
  src="https://api.flyrank.com/public/widget/{widget_id}/widget.js?v={js_version}"
  data-widget-id="{widget_id}"
  defer
></script>
```

Also available as a direct copy button in the dashboard UI. The `?v=` query param is what makes cache-busting work (§5.4) — the dashboard must always render the *current* `js_version` in the snippet after any config change.

### 5.3 Widget.js Loading Behavior

```
On DOMContentLoaded:
  1. Find all script tags with [data-widget-id]
  2. For each:
     a. Check if already rendered (idempotency)
     b. Fetch GET /public/widget/{widget_id}/config
     c. If widget_id not found / inactive → silently no-op
     d. Inject:
        - <link> for inter font (optional)
        - <style> for widget CSS
        - <div> for floating button + modal overlay
        - OR <div> for inline form (configurable)
     e. Attach event listeners
     f. On submit:
        - Validate required fields client-side
        - POST form_data + honeypot field (name from config) to /public/widget/{widget_id}/submit
        - Show success/error message (no redirect)
```

### 5.4 Cache Strategy

| Data | Cache Key | TTL / Invalidation |
|------|-----------|-------------------|
| Widget config | `widget:config:{id}` | 300s TTL. On `PUT` → explicit `DEL` (don't rely on TTL alone) |
| Widget.js | Served at a **versioned URL** `widget.js?v={js_version}`. Browser caches it `immutable` for a year, keyed by URL — no invalidation needed because a config change bumps `js_version`, producing a new URL. Old versions simply age out of browser cache naturally. The Redis copy (`widget:js:{id}:{js_version}`) uses the same key scheme, so stale entries are never served after an update. |
| Rate limiter (3 tiers) | `ratelimit:{scope}:{key}:{endpoint}` | 60s TTL per tier, see §8.3 |
| Submission fingerprint | `submission:fp:{fingerprint}` → `lead_id` | 5 min TTL (dedup window, not 24h — see §8.9 rationale) |
| Geo-by-IP | `geo:ip:{ip}` | 24h TTL — cuts provider calls for repeat visitors/shared IPs |

This replaces the v1 design where both browser and Redis caches shared one TTL and a `PUT` could leave stale JS in visitors' browsers for up to an hour — the version-in-URL approach makes that class of bug impossible rather than bounding it.

### 5.5 CORS Strategy

Add `CORSMiddleware` to `app/main.py` for the public endpoints only (dashboard endpoints don't need permissive CORS — they're called from FlyRank's own dashboard origin, or server-to-server):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
)
```

This wildcard is intentional and safe **only because** `POST /submit` is additionally gated by application-layer origin validation (§8.2) — CORS alone never authorizes the write. `GET config` / `GET widget.js` don't need origin gating since they return no tenant-private data.

---

## 6. Submission Pipeline

```
Visitor Browser
    │
    ▼
[1] POST /public/widget/{widget_id}/submit
    │
    ▼
[2] ASGI Body-Size Middleware Check          ← moved before parsing (was step 7 in v1)
    │  └─ 413 immediately if Content-Length > 50KB; body is never read into memory
    ▼
[3] Request Schema Validation (Pydantic)
    │  └─ 400 if invalid
    ▼
[4] Widget Exists & Active? (cached config lookup)
    │  └─ 404 if not found / inactive
    ▼
[5] Origin Validation (exact host match / wildcard subdomain match — §8.2)
    │  └─ 403 if Origin's host doesn't match widget.domain
    ▼
[6] Rate Limit Check — all 3 tiers (Redis, §8.3)
    │  └─ 429 if any tier exceeded, Retry-After set from the tightest tier
    ▼
[7] Honeypot Check (field name from widget config)
    │  └─ If filled → compute spam_reasons=["honeypot"], spam_score=1.0,
    │     honeypot_triggered=true, STILL INSERT the row (for analytics/audit),
    │     then return 200 fake success without enqueuing enrichment
    ▼
[8] Fingerprint Computation & Dedup Check (Redis, §8.9)
    │  └─ If seen within 5-min window → return 201 with original lead_id, skip insert
    ▼
[9] Spam Pre-Check (Synchronous heuristics, §8.4)
    │  └─ Computes spam_score, spam_reasons (skipped if honeypot already set it)
    ▼
[10] Insert Lead into PostgreSQL (status='pending')
    │
    ▼
[11] Enqueue Enrichment Job (RQ "enrichment-jobs" queue) — skipped for honeypot rows
    │
    ▼
[12] Return 201 { success: true, lead_id }
    │
    ▼
[13] Background Worker Runs:
    │  a. Check geo:ip:{ip} cache first
    │  b. Set status = 'enriched'
    │  c. Geo enrich IP (provider chain) if not cached
    │  d. Update geo_country, geo_city, geo_region, geo_isp, geo_provider
    │  e. If all providers fail → status = 'failed', log alert
    │
    ▼
[14] Dashboard queries leads (including enriched geo data, honeypot rows filtered by default)
```

---

## 7. Background Jobs — RQ Integration

### New Queue: `enrichment-jobs`

Define in `app/queue.py`:

```python
ENRICHMENT_QUEUE_NAME = "enrichment-jobs"
ENRICHMENT_REDIS_KEY_PREFIX = "enrichment_job:"

def create_enrichment_job(lead_id: str) -> str:
    # Use same pattern as create_job() / create_report_job()
    # Stores enrichment_job:<uuid> hash in Redis
    # Enqueues to ENRICHMENT_QUEUE_NAME with retry config
```

### Worker Configuration

In `app/worker.py`, add `ENRICHMENT_QUEUE_NAME` to the watched queues:

```python
QUEUES = ["ai-jobs", "report-jobs", "enrichment-jobs"]
```

### Worker Function: `app/leads/worker.py`

```python
def run_enrichment_job(lead_id: str):
    # 1. Set status = STARTED
    # 2. Fetch lead from DB
    # 3. Check geo:ip:{lead.ip_address} Redis cache first
    # 4. If cache miss, call geo_enrich(lead.ip_address) — provider chain
    # 5. Cache successful result at geo:ip:{ip} for 24h
    # 6. If success → update lead with geo data, status = FINISHED
    # 7. If all providers fail → retry or FAILED
    # 8. Same retry pattern: Retry(max=3, interval=[10, 60, 300])
    # 9. Same alert pattern on final failure
```

### Idempotency

- `lead_id` is the enrichment-job idempotency key. If enrichment already completed, skip.
- Check `lead.status == 'enriched'` before running.
- This is separate from the *submission*-level fingerprint dedup in §8.9, which prevents duplicate rows in the first place.

### Failure Handling

- 3 retries with escalating delay (10s, 60s, 300s)
- After 3 failures → status = `failed`, geo fields remain null
- `send_alert("Enrichment failed for lead {lead_id}")`
- Manual re-enrichment: `POST /widgets/{widget_id}/leads/{lead_id}/re-enrich`

---

## 8. Security

### 8.1 CORS Policy

- `CORSMiddleware` with `allow_origins=["*"]` for public widget endpoints only (§5.5)
- Application-level origin validation against `widget.domain` gates the actual write (`POST /submit`)
- Authenticated dashboard endpoints don't get permissive CORS — restrict to the dashboard's own origin, or skip CORS entirely if only called server-side

### 8.2 Origin Validation (`embed/dependencies.py`)

The v1 version of this check (`origin.startswith(config["domain"])`) is a **bypassable string-prefix match** — `https://myshop.com.evil.com` passes because it starts with `https://myshop.com`. Fixed version parses both URLs and compares hosts:

```python
from urllib.parse import urlparse

async def validate_origin(request: Request, widget_id: UUID) -> bool:
    origin_header = request.headers.get("origin") or request.headers.get("referer", "")
    if not origin_header:
        return False  # reject missing Origin on POST — see §14.3

    config = await embed_service.get_widget_config(widget_id)
    if not config:
        return False

    request_host = urlparse(origin_header).hostname or ""
    allowed = urlparse(config["domain"]).hostname or ""

    if allowed.startswith("*."):
        # wildcard subdomain: *.myshop.com matches foo.myshop.com and myshop.com
        base = allowed[2:]
        return request_host == base or request_host.endswith("." + base)

    return request_host == allowed  # exact host match, no substring/prefix logic
```

Key fix: comparison is on the **parsed hostname**, never on the raw string, so `myshop.com.evil.com` no longer matches `myshop.com`.

### 8.3 Rate Limiting

**Algorithm**: Sliding-window counter, enforced as **three independent tiers checked together** in step 6 of the pipeline — all three must pass.

| Tier | Redis Key | Window | Max Requests |
|------|-----------|--------|--------------|
| Global per IP | `ratelimit:global_ip:{ip}:submit` | 60s | 100 |
| Per widget per IP | `ratelimit:widget_ip:{widget_id}:{ip}:submit` | 60s | 30 |
| Per widget globally | `ratelimit:widget_global:{widget_id}:submit` | 60s | 1000 |

**Implementation** — all three tiers use the same `INCR` + `EXPIRE` primitive, pipelined into a single Redis round trip:

```python
async def check_rate_limits(ip: str, widget_id: str, window: int = 60) -> tuple[bool, int]:
    keys_and_limits = [
        (f"ratelimit:global_ip:{ip}:submit", 100),
        (f"ratelimit:widget_ip:{widget_id}:{ip}:submit", 30),
        (f"ratelimit:widget_global:{widget_id}:submit", 1000),
    ]
    pipe = redis_client.pipeline()
    for key, _ in keys_and_limits:
        pipe.incr(key)
    counts = await pipe.execute()

    # set TTL only on first hit of each key (avoid resetting the window)
    for (key, _), count in zip(keys_and_limits, counts):
        if count == 1:
            await redis_client.expire(key, window)

    for (key, limit), count in zip(keys_and_limits, counts):
        if count > limit:
            return False, window  # Retry-After = window (simplification; could compute exact TTL)
    return True, 0
```

**Fallback if Redis is unavailable**: fail open with an in-process approximate limiter (see §14.4) rather than blocking all submissions — availability > perfect enforcement for this endpoint.

**Bypass hardening**: combine the IP-based tiers above with fingerprint-based detection (§8.9) so simple IP rotation doesn't fully defeat rate limiting — a rotated-IP flood still trips the `widget_global` tier and the spam heuristics.

### 8.4 Spam Protection (`leads/spam.py`)

Synchronous heuristics applied before storage (skipped if honeypot already flagged the row):

| Check | Score Addition | Description |
|-------|---------------|-------------|
| All fields identical | +0.3 | Same value in name, email, message |
| URL in message | +0.2 | Detects link spam |
| Non-ASCII avalanche | +0.2 | Cyrillic/latin mixed gibberish |
| Phone pattern mismatch | +0.1 | Phone field doesn't match regional pattern |
| Email domain blacklist | +0.4 | Free disposable domains check |
| IP reputation (future) | TBD | DNSBL integration |

**Threshold**: ≥ 0.5 → mark as spam, store with `spam_reasons`.
Spam leads (score-based) are stored and shown by default with a badge; honeypot-triggered leads are stored but hidden by default (`include_honeypot=false`) — these are two distinct concepts, no longer conflated.

### 8.5 Honeypot (`leads/spam.py`)

- An invisible form field, hidden via CSS, whose **name is randomly generated per widget** at creation time and stored in `widgets.config.honeypot_field` (e.g. `_hp_a3f9`) — not a fixed name like `_website` that bots can pattern-match across every FlyRank widget.
- Served as part of the cached config response so the client-side script knows which field to render-and-hide.
- If the field contains any value → bot detected. The row **is inserted** (`honeypot_triggered = true`, `spam_score = 1.0`) so it's available for spam analytics/ML training and audit, consistent with how score-based spam is handled (§8.4) — this replaces the v1 rule of silently discarding the submission, which contradicted the schema having a `honeypot_triggered` column in the first place.
- No enrichment job is enqueued for these rows (not worth the geo lookup).
- Response to the bot is still `200`/`201` fake success — detection is never revealed to the client.

### 8.6 Payload Limits

- **Enforced at the ASGI middleware layer, before the body is read or handed to Pydantic** — this is the fix for the v1 ordering bug where a large body was fully parsed before being rejected:

```python
# app/middleware/body_limit.py
class BodyLimitMiddleware:
    def __init__(self, app, max_bytes: int = 50_000):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length and int(content_length) > self.max_bytes:
            response = JSONResponse({"detail": "Payload too large"}, status_code=413)
            return await response(scope, receive, send)

        # also guard against missing/spoofed Content-Length by capping actual bytes received
        received = 0
        async def limited_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > self.max_bytes:
                raise HTTPException(status_code=413, detail="Payload too large")
            return message

        return await self.app(scope, limited_receive, send)
```

- Individual field max length: 2000 chars (enforced in Pydantic, after the size gate)

### 8.7 Input Validation (`leads/models.py`)

- All string fields trimmed and sanitized (strip HTML tags)
- Email validated with regex
- Phone validated with E.164 pattern (basic)
- URL fields validated with `validators.url`

### 8.8 Tenant Isolation

- All widget operations scoped to `tenant_id = current_user.id`
- All lead queries JOIN on `widgets.tenant_id` filter
- `get_current_user` provides authenticated user ID
- Repository methods always include `tenant_id` in WHERE clause

### 8.9 Submission Fingerprint & Dedup (`leads/fingerprint.py`)

New in v2 — the v1 doc referenced a `submission:{fingerprint}` cache key in its table but never implemented it. Now wired into the pipeline:

```python
import hashlib, json

def compute_fingerprint(widget_id: str, ip: str, form_data: dict) -> str:
    normalized = json.dumps(form_data, sort_keys=True)
    raw = f"{widget_id}:{ip}:{normalized}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

- **Purpose**: prevent double-charges/double-rows from double-clicks, retried requests, or naive scripted floods repeating the exact same payload — not a general spam filter (that's §8.4).
- **Window**: 5 minutes (short — this is anti-duplicate, not anti-abuse; a legitimate user resubmitting the same form 10 minutes later should get a new row).
- On a hit within the window, the pipeline returns the *original* `lead_id` with a normal success response rather than erroring, so retried client requests look idempotent.

---

## 9. Geo Enrichment (`leads/geo.py`)

### Provider Fallback Chain

Reordered from v1: `ip-api.com`'s 45/min limit is **shared globally across all FlyRank traffic**, not per-caller, so putting it first or second risks throttling enrichment for every tenant during a burst. `ipapi.co`'s 1000/day is also global-shared but far more headroom for typical capstone-scale traffic; `ipinfo.io` (token-based, 50k/month) is the most generous and most reliable, so it's promoted ahead of `ip-api.com`.

```
[1] ipapi.co (ipapi.co/{ip}/json/)
    │  Free: 1000/day (global to your account), no key needed
    │  Timeout: 3s
    ├─ Success → return {country, city, region, isp, provider: "ipapi"}
    │
    └─ Failure (timeout/error/rate-limit)
          │
          ▼
[2] ipinfo.io (ipinfo.io/{ip}?token={TOKEN})
    │  Free: 50k/month, requires token in .env
    │  Timeout: 3s
    ├─ Success → return {country, city, region, isp, provider: "ipinfo"}
    │
    └─ Failure (timeout/error/rate-limit)
          │
          ▼
[3] ip-api.com (ip-api.com/json/{ip})
    │  Free: 45/min GLOBAL (not per-caller) — last resort only
    │  Timeout: 3s
    ├─ Success → return {country, city, region, isp, provider: "ip-api"}
    │
    └─ Failure → return None (all providers exhausted)
```

A 24h `geo:ip:{ip}` Redis cache (§5.4) sits in front of this whole chain and is checked by the worker before calling any provider — this is the biggest lever against exhausting the shared quotas, since repeat visitors and shared corporate/ISP IPs get served from cache.

### Timeout Strategy

- Each provider gets exactly one attempt with 3s timeout
- Uses `asyncio.wait_for(provider_call, timeout=3.0)`
- Total max latency: 9s (but typically completes on first provider in <500ms, or instantly on cache hit)

### Failure Strategy

- If all 3 providers fail → lead status = `failed`, geo fields remain NULL
- `send_alert("Geo enrichment failed for lead {lead_id}: all providers exhausted")`
- The lead is still visible in the dashboard with missing geo data
- Manual retry via `POST /widgets/{widget_id}/leads/{lead_id}/re-enrich`

### Circuit Breaker (Optional Enhancement)

- Track consecutive failures per provider in Redis
- After 5 consecutive failures → skip provider for 5 minutes
- Reset on success

---

## 10. Dashboard APIs

All dashboard endpoints are under `/widgets` and protected by `Depends(get_current_user)`.

### 10.1 Widget Management

| Method | Path | Description |
|--------|------|--------------|
| `GET` | `/widgets` | List widgets (paginated, searchable) |
| `POST` | `/widgets` | Create widget |
| `GET` | `/widgets/{id}` | Widget detail |
| `PUT` | `/widgets/{id}` | Update widget config (bumps `js_version`) |
| `DELETE` | `/widgets/{id}` | Soft-delete widget |
| `GET` | `/widgets/{id}/embed` | Get embed snippet HTML |
| `GET` | `/widgets/{id}/copy` | Return raw `<script>` tag |

### 10.2 Lead Dashboard

| Method | Path | Description |
|--------|------|--------------|
| `GET` | `/leads` | Cross-widget lead list |
| `GET` | `/leads/stats` | Aggregate stats |
| `GET` | `/widgets/{id}/leads` | Per-widget lead list |
| `GET` | `/widgets/{id}/leads/{lead_id}` | Lead detail |
| `POST` | `/widgets/{id}/leads/{lead_id}/re-enrich` | Manual re-enrichment (was incorrectly `GET` in v1) |
| `GET` | `/widgets/{id}/export` | Export CSV |
| `DELETE` | `/widgets/{id}/leads/{lead_id}` | Delete a lead |
| `POST` | `/widgets/{id}/leads/batch-delete` | Batch delete by IDs |

### 10.3 Statistics Design

Statistics are computed from the `leads` table using aggregate SQL queries:

```sql
-- Today's count (excludes honeypot rows)
SELECT COUNT(*) FROM leads
WHERE widget_id = $1 AND tenant_id = $2
  AND created_at >= CURRENT_DATE
  AND honeypot_triggered = FALSE;

-- Top countries
SELECT geo_country, COUNT(*) as count
FROM leads
WHERE widget_id = $1 AND tenant_id = $2 AND geo_country IS NOT NULL
GROUP BY geo_country
ORDER BY count DESC
LIMIT 10;

-- Leads over time (last 30 days)
SELECT DATE(created_at) as date, COUNT(*) as count
FROM leads
WHERE widget_id = $1 AND tenant_id = $2
  AND created_at >= NOW() - INTERVAL '30 days'
  AND honeypot_triggered = FALSE
GROUP BY DATE(created_at)
ORDER BY date;
```

Cache stats in Redis for 5 minutes. Invalidate on new lead submission (best-effort).

### 10.4 Pagination

All list endpoints follow the same pattern:

```python
class PaginationParams:
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
```

Response shape:
```json
{
  "items": [...],
  "total": 1250,
  "page": 1,
  "page_size": 20,
  "pages": 63
}
```

### 10.5 Search

Leads search uses PostgreSQL JSONB queries:

```sql
WHERE form_data->>'name' ILIKE '%search_term%'
   OR form_data->>'email' ILIKE '%search_term%'
   OR form_data->>'message' ILIKE '%search_term%'
```

Or use `@@` tsvector if full-text search is needed (Phase 2).

---

## 11. Testing Strategy

### Test Matrix

| Category | File | What to Test | Count |
|----------|------|--------------|-------|
| **Unit — Models** | `tests/widgets/test_models.py` | WidgetCreate validation, WidgetResponse serialization, config field validation, wildcard domain acceptance | 9 |
| | `tests/leads/test_models.py` | LeadSubmit validation, field length, email regex, payload size | 8 |
| **Unit — Spam** | `tests/leads/test_spam.py` | Honeypot detection (row stored, not discarded), URL spam scoring, field-identity spam, email blacklist, threshold logic, empty form_data | 11 |
| **Unit — Geo** | `tests/leads/test_geo.py` | Provider 1 success, fallback chain (new order), all providers fail, timeout handling, cache hit skips provider call, circuit breaker (if implemented), provider response parsing, empty IP | 11 |
| **Unit — Fingerprint** | `tests/leads/test_fingerprint.py` | Same payload within window dedups, same payload after window creates new row, different IP doesn't dedup, different form_data doesn't dedup | 6 |
| **Unit — Widget JS** | `tests/embed/test_widget_js.py` | JS generation, config embedding, versioned URL / cache-busting on `js_version` bump, script tag format, caching headers, missing widget returns 404 | 8 |
| **Repository** | `tests/widgets/test_repository.py` | Create, get by id, get by tenant, update (js_version bump), delete (soft), list paginated, search by name, domain uniqueness | 13 |
| | `tests/leads/test_repository.py` | Create lead, get by id, list by widget, list by tenant excluding honeypot by default, include_honeypot flag, search, filter by status/spam/date, pagination, CSV export query | 15 |
| **Service** | `tests/widgets/test_service.py` | Create with validation, honeypot_field auto-generation, update config, soft delete, duplicate domain error, inactive widget handling | 9 |
| | `tests/leads/test_service.py` | Full submission pipeline, honeypot branch (stored, fake success), spam high branch, dedup branch, enrichment enqueue skipped on honeypot, rate limit exceeded (each of 3 tiers) | 13 |
| | `tests/embed/test_service.py` | Config caching, config missing, snippet generation with version param, origin validation exact + wildcard | 8 |
| **Router — Public** | `tests/embed/test_router.py` | GET widget.js 200, 404, 410; GET config 200, 404, cached; POST submit 201, 400, 404, 429, 413; CORS headers present; OPTIONS preflight | 14 |
| **Router — Dashboard** | `tests/widgets/test_router.py` | CRUD 200/201/204, 401 without auth, 403 wrong tenant, 404 not found, 409 duplicate domain, pagination, search | 15 |
| | `tests/leads/test_router.py` | List 200, detail 200, 403 wrong tenant, 404, stats 200 (honeypot excluded), export CSV 200, batch delete 204, re-enrich POST 202/409, filtering params | 13 |
| **Background Jobs** | `tests/leads/test_worker.py` | Enrichment success, cache-hit path, enrichment all-fail, retry cycle, idempotent re-run, alert on failure, update lead status | 9 |
| **Security** | `tests/middleware/test_cors.py` | Origin matches domain exactly, subdomain-suffix bypass rejected (`myshop.com.evil.com`), wildcard domain matches subdomain, missing origin rejected on POST, wildcard CORS on GET, preflight OPTIONS | 9 |
| | `tests/middleware/test_body_limit.py` | Under limit passes, over Content-Length rejected pre-parse, spoofed/missing Content-Length still capped by streamed byte count, exactly-at-limit passes | 5 |
| | `tests/leads/test_rate_limit.py` | Each tier independently blocks, all tiers pass together, window resets, per-IP isolation, per-widget isolation, Redis failure fails open | 9 |
| **Integration** | `tests/test_e2e_widget.py` | Full flow: create widget → get config → submit lead → poll enrichment → verify enriched data; honeypot flow end-to-end; duplicate submission flow end-to-end | 7 |

**Total: ~175 tests**

### Testing Infrastructure Reuse

| Existing Fixture | How to Extend |
|-----------------|---------------|
| `_FakeRedis` | Add rate-limit-tier / cache / fingerprint mock methods |
| `_FakeQueue` | Add enrichment queue mock |
| `client` (TestClient) | Reuse as-is |
| `sample_*_data` | Add `sample_widget_data`, `sample_lead_data` fixtures |
| `mocker` (pytest-mock) | Reuse for external API mocks (geo providers) |

---

## 12. Implementation Roadmap

### Milestone 1: Database Schema & Migrations

**Effort**: 2 hours

**Deliverables**:
- `db/init.sql` updated with `widgets` (incl. `js_version`), `leads` (incl. `fingerprint`), `rate_limits` (incl. `scope`) tables
- `app/database.py` verified with new tables (postgres pool startup)
- Manual verification: `docker-compose up` → tables created

**Dependencies**: None

---

### Milestone 2: Widget CRUD — Repository + Service + Router

**Effort**: 4 hours

**Deliverables**:
- `app/widgets/repository.py` — WidgetRepository with full CRUD + pagination + search
- `app/widgets/models.py` — WidgetCreate, WidgetUpdate, WidgetResponse Pydantic schemas
- `app/widgets/service.py` — WidgetService with validation, domain uniqueness, honeypot-field auto-generation, `js_version` bump on update
- `app/widgets/router.py` — Full widget management REST API
- Registered in `app/main.py`

**Tests**: Repository unit tests + router unit tests

**Dependencies**: Milestone 1

---

### Milestone 3: Public Embed Endpoints

**Effort**: 3 hours

**Deliverables**:
- `app/embed/router.py` — `GET /public/widget/{id}/config`, `GET /public/widget/{id}/widget.js`
- `app/embed/service.py` — Config fetching with Redis caching, versioned widget.js generation
- `app/embed/widget_js.py` — JavaScript template rendering with config injection
- `app/middleware/cors.py` — CORS middleware added
- `app/embed/dependencies.py` — Fixed origin-validation function (§8.2)

**Tests**: Router unit tests for config and widget.js endpoints, caching behavior, error codes

**Dependencies**: Milestone 2

> **Can run in parallel with Milestone 2** if two engineers are available — both only depend on M1 (the schema). The dependency graph below reflects this fork/join instead of a strict chain.

---

### Milestone 4: Lead Capture Submission

**Effort**: 5 hours *(+1h vs. v1 for fingerprint + body-limit middleware)*

**Deliverables**:
- `app/leads/models.py` — LeadSubmit, LeadResponse Pydantic schemas
- `app/leads/repository.py` — LeadRepository with create, list, search, filter
- `app/leads/fingerprint.py` — Fingerprint computation + Redis dedup check
- `app/middleware/body_limit.py` — ASGI-layer payload size enforcement
- `app/leads/service.py` — Submission pipeline (body-limit → validate → widget lookup → origin → rate limit ×3 → honeypot → fingerprint → spam → store)
- `app/leads/spam.py` — Honeypot detection (store-with-flag, not discard), spam scoring heuristics
- `app/leads/dependencies.py` — 3-tier rate limit checker, origin validator
- `app/leads/router.py` — `POST /public/widget/{id}/submit` endpoint
- Registered in `app/main.py`

**Tests**: Spam unit tests, fingerprint unit tests, submission pipeline tests, rate limit tests (all 3 tiers), body-limit tests, router tests

**Dependencies**: Milestone 3

---

### Milestone 5: Geo Enrichment Background Jobs

**Effort**: 3 hours

**Deliverables**:
- `app/leads/geo.py` — Provider chain (ipapi → ipinfo → ip-api, reordered per §9), 24h geo-by-IP cache
- `app/leads/worker.py` — RQ worker for enrichment: cache check → geo enrich → update lead
- `app/queue.py` — `ENRICHMENT_QUEUE_NAME`, `create_enrichment_job` helper
- `app/worker.py` — Add `enrichment-jobs` to watched queues
- `POST /widgets/{id}/leads/{lead_id}/re-enrich` manual endpoint

**Tests**: Geo chain unit tests (mock external APIs), cache-hit test, worker lifecycle tests, re-enrich endpoint test

**Dependencies**: Milestone 4

---

### Milestone 6: Lead Dashboard APIs

**Effort**: 3 hours

**Deliverables**:
- `app/leads/router.py` — Extend with authenticated dashboard endpoints:
  - `GET /widgets/{id}/leads` (paginated, searchable, filterable, `include_honeypot` toggle)
  - `GET /widgets/{id}/leads/{lead_id}`
  - `GET /widgets/{id}/stats`
  - `GET /widgets/{id}/export`
  - `GET /leads` (cross-widget)
  - `GET /leads/stats` (aggregate)
  - `DELETE` and batch delete
- `app/leads/service.py` — Extend with stats queries, CSV generation, batch ops

**Tests**: Router tests for all lead dashboard endpoints, stats computation tests, CSV export tests

**Dependencies**: Milestone 5

---

### Milestone 7: Security Hardening

**Effort**: 2 hours

**Deliverables**:
- Origin-validation edge case sweep (empty Origin, malformed URLs, punycode)
- Rate limit persistence to DB (optional, async best-effort write to `rate_limits`)
- IP blacklist support (future: DNSBL)
- Audit logging for all submission attempts (success + blocked, including honeypot/fingerprint-dedup branches)

**Tests**: Security-focused tests (CORS bypass attempts, rate limit edge cases, payload limits, injection attempts)

**Dependencies**: Milestone 6

---

### Milestone 8: Testing Completion & CI

**Effort**: 3 hours

**Deliverables**:
- Full test matrix coverage (~175 tests)
- `tests/conftest.py` extended with widget/lead fixtures
- CI pipeline in `.github/workflows/ci.yml` runs new test suites
- Coverage target: ≥ 90% for new code

**Tests**: Comprehensive (this milestone is about completing the test suite)

**Dependencies**: Milestones 2–7 (all feature code complete)

---

### Dependency Graph (corrected — M2/M3 now shown as parallel, matching the text)

```
                 ┌─→ M2 (Widget CRUD) ───┐
M1 (DB Schema) ──┤                       ├─→ M4 (Lead Submission)
                 └─→ M3 (Embed Endpoints)┘        │
                                                   ▼
                                          M5 (Geo Enrichment)
                                                   │
                                                   ▼
                                          M6 (Lead Dashboard)
                                                   │
                                                   ▼
                                          M7 (Security Hardening)
                                                   │
                                                   ▼
                                          M8 (Testing & CI)
```

M4 needs both M2 (widget lookups) and M3 (origin/config caching helpers), so it waits for the join, not just M3.

---

## 13. Git Plan

### Branch Name

```
feature/embed-widget-lead-capture
```

### Commit Plan

| # | Commit Message | Milestone |
|---|---------------|-----------|
| 1 | `feat(db): add widgets, leads, rate_limits tables` | M1 |
| 2 | `feat(widgets): implement widget CRUD repository, service, and dashboard router` | M2 |
| 3 | `feat(embed): add public widget config and widget.js endpoints with versioned caching` | M3 |
| 4 | `feat(embed): add CORS middleware and origin validation` | M3 |
| 5 | `feat(leads): implement submission pipeline with body-limit middleware, validation, and spam detection` | M4 |
| 6 | `feat(leads): add 3-tier rate limiting and fingerprint dedup for public submit endpoint` | M4 |
| 7 | `feat(leads): implement geo enrichment provider chain and RQ worker` | M5 |
| 8 | `feat(leads): add enrichment-jobs queue to worker.py` | M5 |
| 9 | `feat(dashboard): add lead list, detail, stats, export, and batch delete endpoints` | M6 |
| 10 | `feat(security): harden origin validation, audit logging` | M7 |
| 11 | `test: add comprehensive tests for widgets, embed, leads, and security` | M8 |
| 12 | `chore(ci): enable new test suites in CI pipeline` | M8 |

### Pull Request Strategy

- Single feature branch `feature/embed-widget-lead-capture`
- One PR per milestone (7 PRs total) if the review surface is large
- Alternatively: 2–3 thematic PRs:
  - **PR 1**: "Widget management + Embed endpoints" (M1, M2, M3)
  - **PR 2**: "Lead capture + Geo enrichment" (M4, M5)
  - **PR 3**: "Dashboard + Security + Tests" (M6, M7, M8)
- Each PR must pass CI (all tests + lint)
- Merge via squash-merge to keep `main` history clean

---

## 14. Risks & Mitigations

### 14.1 Architectural Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Widget config cache invalidation race | Stale config served after widget update | Explicit `DEL` on PUT (not TTL-only); TTL caps stale window at 5min regardless |
| Widget.js browser-cache staleness | Old JS served to repeat visitors after update | **Solved structurally** via versioned URL (§5.4) rather than bounded — no invalidation needed |
| Enrichment worker falls behind under load | Leads show `pending` status for too long | Monitor queue depth; scale workers via horizontal pod autoscaling; add dead-letter queue |
| Origin validation bypass via subdomain-suffix spoofing | Unauthorized submissions accepted from a lookalike domain | Fixed: hostname-exact / wildcard-suffix comparison, not string prefix (§8.2) |
| Congestion on `enrichment-jobs` delays real-time enrichment | Priority inversion for high-volume tenants | Use separate queue per tenant (future); or route to priority queue |

### 14.2 Performance Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| 3-tier rate limiter adds Redis round trips | Slight latency per submission | Pipelined into one round trip (§8.3), not 3 sequential calls |
| Geo enrichment adds 3–9s latency per lead | Submission response delayed | Geo enrichment is **async** (RQ background job). Submission returns instantly. 24h IP cache further cuts provider calls. |
| Dashboard stats queries on large lead tables | Slow page loads | Add materialized view for stats (refreshed every 5 min); use aggregated Redis counters |
| JSONB search on `form_data` | Full table scan on search | Add GIN index on `form_data` if search performance degrades |
| Large request bodies consuming memory before rejection | Memory pressure / DoS | **Fixed**: body-limit middleware rejects by `Content-Length` before parsing, and caps streamed bytes even if `Content-Length` is absent or spoofed (§8.6) |

### 14.3 Security Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Origin header spoofing | Unauthorized submissions accepted | Origin required on POST (missing → reject, was previously ambiguous); exact-host / wildcard-suffix match, not prefix match |
| Honeypot field name predictable | Bots learn to skip it | Randomized per-widget field name, stored server-side, never client-chosen |
| Rate limiter bypass via IP rotation | DDoS submission attack | 3-tier limiting (a widget-global cap catches rotation that individual per-IP limits miss) + fingerprint dedup on repeated identical payloads |
| Malicious JavaScript injection in form_data | XSS on dashboard | Strip HTML tags from all form_data values; use safe rendering in frontend |
| Tenant can view another tenant's leads | Data breach | Every query includes `WHERE tenant_id = current_user.id`; repository methods enforce tenant isolation |
| Honeypot rows silently dropped, losing audit trail | Under-counting bot traffic, contradicts schema | **Fixed**: rows now stored with `honeypot_triggered=true`, hidden from default dashboard view only |

### 14.4 Scalability Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Single Redis instance for rate limiting | SPOF | Redis Sentinel or cluster; **fail-open** to an in-memory approximate limiter if Redis is down (explicitly specified now, not just implied) |
| PostgreSQL connection pool exhaustion | App unavailability | Pool size tuned; enrichment worker uses separate pool with lower max_connections |
| High submission volume spikes | DB write contention | Batch insert buffer (Redis list → periodic flush); or use PgBouncer for connection pooling |
| Geo provider API rate limits | Enrichment failures for all leads | Reordered chain to lead with the highest-quota providers (§9); 24h geo-by-IP cache is the primary defense; rotate API keys; degrade gracefully |

---

## 15. Summary

### What Needs to Be Built

| Component | Files | Lines (Est.) |
|-----------|-------|-------------|
| DB Schema (init.sql) | 1 | ~70 |
| Widget Repository | 1 | ~120 |
| Widget Service | 1 | ~110 |
| Widget Router | 1 | ~100 |
| Widget Models | 1 | ~60 |
| Embed Router | 1 | ~80 |
| Embed Service | 1 | ~130 |
| Widget JS Generator | 1 | ~90 |
| CORS Middleware | 1 | ~40 |
| Body-Limit Middleware | 1 | ~40 |
| Lead Repository | 1 | ~210 |
| Lead Models | 1 | ~80 |
| Lead Fingerprint | 1 | ~30 |
| Lead Service (pipeline) | 1 | ~230 |
| Lead Router (public + dashboard) | 1 | ~210 |
| Spam Detection | 1 | ~110 |
| Geo Enrichment | 1 | ~160 |
| Enrichment Worker | 1 | ~90 |
| Queue Extension | 1 | ~30 |
| Worker Extension | 1 | ~10 |
| Main.py Extension | 1 | ~35 |
| Tests (~18 files) | 18 | ~1750 |
| **Total** | **~37 files** | **~3695 lines** |

### Key Design Decisions (v2)

1. **No new services** — Reuses existing PostgreSQL, Redis, RQ, Docker. Zero infrastructure changes.
2. **Async geo enrichment** — Submission always returns instantly (201). Geo data populated via background worker, with a 24h IP cache in front of the provider chain.
3. **Application-layer origin validation, not string prefix matching** — exact-host / wildcard-suffix comparison closes the subdomain-spoofing bypass present in v1.
4. **Body size enforced before parsing** — ASGI middleware layer, not a late Pydantic-adjacent check.
5. **Three-tier Redis rate limiting**, pipelined into one round trip, with an explicit fail-open fallback.
6. **Honeypot and score-based spam are both stored, never silently dropped** — honeypot rows are hidden from the default dashboard view rather than discarded, resolving the v1 contradiction with the `honeypot_triggered` column.
7. **Submission fingerprint dedup** actually implemented (v1 only mentioned the cache key), with a short 5-minute window scoped to anti-duplicate, not anti-abuse.
8. **Widget.js cache-busting via versioned URL** rather than a TTL race between browser and Redis caches.
9. **Re-enrichment is `POST`**, consistently, since it mutates state.
10. **M2/M3 parallelization** is now reflected correctly in the dependency graph.

All components integrate into the existing project. No new Docker services, no new external infrastructure, no new authentication system. Every component reuses established patterns (FastAPI lifespan, asyncpg, Redis caching, RQ background jobs, Supabase auth, Repository pattern, Pytest fixtures).