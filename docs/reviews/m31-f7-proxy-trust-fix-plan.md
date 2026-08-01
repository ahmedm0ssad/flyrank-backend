# M31 — F7 Fix + Live Verification: Env-Gated Client-IP Resolver (Proxy Trust)

**Status**: COMPLETE — design → implemented → live-verified (run A/B)
**Date**: 2026-08-01
**Branch**: `feature/capstone-submission-pack`
**Commits**: `5697b6c` (fix) · `6b27022` (test) · `ff4a9d4` (docs/plan)
**Baseline reference**: M30 — F7 still Tier C; 947 passed / 100% coverage mocked.
**Decision scope**: Fixed by the user. Implement an **app-level client-IP resolver** that honors
`X-Forwarded-For` **only** when `TRUSTED_PROXY_CIDRS` is set. No compose topology change,
no uvicorn flag change. Default (unset/empty) preserves the current direct-peer behavior —
**secure by default**.

---

## 1. The finding (F7, Tier C — escalated to a fix per user decision)

`app/services/lead_service.py:104`:

```python
ip = request.client.host if request.client else "unknown"
```

This single value drives, in order:

1. **Rate limiting** — `app/dependencies/leads.py:71` `check_rate_limits(ip, widget_id)` builds
   all three tier keys (`global_ip:{ip}:submit` @100, `widget_ip:{widget_id}:{ip}:submit` @30,
   `widget_global:{widget_id}:submit` @1000) from it (lines 12–16). Called at
   `lead_service.py:136`.
2. **Fingerprint + dedup** — `compute_fingerprint(widget_id, ip, body.form_data)` at
   `lead_service.py:164` (`app/services/fingerprint_service.py:9`).
3. **Stored `lead.ip_address`** — passed to `repo.create(...)` at `lead_service.py:189`.
4. **Geo enrichment** — `lead_worker` later calls `geo_service.geo_enrich(lead.ip_address)`
   (`app/services/geo_service.py:130`); a private IP returns bogon/empty data.

Because `request.client.host` is the **direct TCP peer** and uvicorn runs without
`--proxy-headers`, `X-Forwarded-For` is ignored end-to-end. Every M27/M29/M30 live submit
sent with `X-Forwarded-For: 8.8.8.8` stored `172.18.0.1` (the docker gateway).

**Side effects of one wrong IP** (confirmed live, all attributable to this one line):

- All external traffic shares one per-IP rate-limit bucket (`172.18.0.1`), so a single
  widget visitor can burn the global-IP tier for everyone behind the gateway.
- Fingerprint dedup collides across distinct visitors behind the same gateway.
- Geo enrichment resolves a private IP → `geo_country/city/region/isp` stay null while
  `geo_provider:"ipinfo"` is written (M30 §7 artifact).
- Audited leads (`app.audit.submission`) record the gateway, not the caller.

**Root cause** (not the header parsing): uvicorn's `--proxy-headers` trust only applies to
peers in `--forwarded-allow-ips` (default `127.0.0.1`), which never matches the docker
gateway. Dockerfile `CMD` is `uvicorn app.main:app --host 0.0.0.0 --port 8000`
(Dockerfile:13). So the header never reaches a trust path at all.

---

## 2. Design decision — env-gated app-level trust

### The crux

In the current compose topology there is **no real proxy**. Every external client's direct
peer is the gateway `172.18.0.1`. That makes the two "obvious" fixes security holes:

- **Trust XFF unconditionally** — any client can send `X-Forwarded-For: 1.2.3.4` and take
  over another IP's rate-limit/fingerprint state. Open spoofing.
- **Trust the docker subnet (`172.18.0.0/16`) in production** — the compose gateway is the
  docker *bridge*, not an edge proxy; it does **not** sanitize headers, so a container
  guest can forge XFF. In a real deployment the equivalent is trusting an IP range you do
  not fully control. Not safe as a default.

### The decision

An **app-level resolver** `get_client_ip(request)` that honors `X-Forwarded-For` **only when
`TRUSTED_PROXY_CIDRS` is set**:

- `TRUSTED_PROXY_CIDRS` unset or empty (default) → return `request.client.host`
  unchanged. Behavior identical to today; nothing to deploy wrong.
- `TRUSTED_PROXY_CIDRS` set (comma-separated CIDRs, e.g. `10.0.0.0/8,192.168.1.0/24`)
  → parse `X-Forwarded-For` right-to-left, skip entries inside the trusted CIDRs, return
  the first untrusted hop; fall back to `request.client.host`.
- Resolver lives in **`app/dependencies/client_ip.py`** — matches the existing
  `app/dependencies/` convention for request-derived concerns (`embed.py`, `leads.py`).

No compose change, no uvicorn flag, no `--forwarded-allow-ips` reasoning. One helper,
called from the single line that owns the IP (`lead_service.py:104`).

---

## 3. Helper spec (`app/dependencies/client_ip.py`)

### Public surface

```python
def get_client_ip(request: Request) -> str:
```

Always returns a non-empty `str` (falls back to `request.client.host`, then `"unknown"`).

### Trusted-CIDR parsing (module-level, parsed once)

```python
_TRUSTED_PROXY_CIDRS: tuple[IPv4Network | IPv6Network, ...]

def _load_trusted_cidrs() -> tuple[IPv4Network | IPv6Network, ...]:
    raw = os.getenv("TRUSTED_PROXY_CIDRS", "").strip()
    if not raw:
        return ()
    nets = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            # misconfigured CIDR: log + skip rather than crash at startup
            ...
    return tuple(nets)
```

- Parsed at import time into a tuple (cheap; `ipaddress` is in the stdlib).
- A malformed entry is logged and skipped — a bad value must not take the app down, and
  must not broaden trust to "everything".

### The algorithm (right-to-left, standard RFC 7239-style walking)

1. Direct peer = `request.client.host if request.client else None`.
2. If `_TRUSTED_PROXY_CIDRS` is empty → return direct peer (or `"unknown"`).
3. `xff = request.headers.get("x-forwarded-for", "")`. If empty → return direct peer.
4. Split `xff` on `,`, strip each token, drop empty tokens.
5. Validate each candidate with `ipaddress.ip_address(...)`; **invalid entries are skipped**
   (never returned, never trusted) — prevents header injection of junk values.
6. Walk the list **right-to-left** (rightmost is the closest hop to us):
   - If the hop is inside any trusted CIDR → it is a proxy hop; continue left.
   - The **first hop NOT inside any trusted CIDR** → this is the true client; return it.
7. If every hop is trusted (or no untrusted hop found) → return the direct peer (defensive:
   never synthesize a value that was not in the header).

### Notes

- Only the *last* (leftmost-surviving) untrusted entry is used — `X-Forwarded-For` may be
  forged further left, but the right-most untrusted hop adjacent to a trusted proxy is the
  best available signal, and the trusted list bounds what a client can fake.
- `IPv4`/`IPv6` both work via `ipaddress` (`IPv6` from a 2001:db8::/32 trust example).
- Returns strings suitable for `LeadResponse.ip_address: str` (no asyncpg object concern —
  this is pre-storage).

### Call site change (`app/services/lead_service.py:104`)

```python
ip = request.client.host if request.client else "unknown"
```
becomes
```python
from app.dependencies.client_ip import get_client_ip

ip = get_client_ip(request)
```

That is the **entire** application change. Rate-limit keys, fingerprint, stored
`ip_address`, and geo all inherit the fix because they all read this one `ip`.

---

## 4. Security stance (why this is safe)

1. **Secure by default.** Empty `TRUSTED_PROXY_CIDRS` = today's exact behavior. No operator
   action = no behavior change = no regression surface in the current compose topology.
2. **Trust is explicit and scoped.** You only honor XFF when you have declared the exact
   CIDRs of proxies you control (`nginx`/`caddy`/LB/VPC). Header only survives as far as
   the last untrusted hop.
3. **The proxy-must-overwrite-XFF caveat (documented, not enforced).** This resolver trusts
   the header from a trusted proxy. It is the **operator's contract** that any listed proxy
   must:
   - `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` (append the direct
     peer), and
   - **strip/overwrite any incoming `X-Forwarded-For` from the untrusted client** so the
     client cannot inject an address into the trusted portion of the chain.
   The right-to-left + CIDR-skip algorithm is the defense-in-depth; the overwrite is the
   contract. If a proxy violates the contract, a client *inside the trusted path* could
   influence the resolved IP — the standard failure mode for *all* XFF trust models,
   including uvicorn's `--proxy-headers`.
4. **No broad trust.** We never trust `172.18.0.0/16` in production defaults; that is only
   used in the dev-verification run (§7) as a simulated trusted proxy to prove the fix.

---

## 5. Test plan

### 5a. Unit tests for the resolver — new `tests/leads/test_client_ip.py`

Placed under `tests/leads/` (not `tests/dependencies/`) so they are collected by the CI pytest
path — `tests/dependencies/` is not in `.github/workflows/ci.yml`'s path list, and without CI
collection the new `app/dependencies/client_ip.py` trust-on branches would drop CI coverage
below 100%. `tests/leads/` is the CI-collected directory adjacent to the submit flow that
consumes the resolver.

Pure-function tests, no DB/Redis. Build fake `Request`-like objects (mirror the `FakeRequest`
pattern in `tests/leads/test_service.py:12`), setting `client.host` and headers.

| Case | `TRUSTED_PROXY_CIDRS` | XFF header | direct peer | Expected result |
|---|---|---|---|---|
| Trust off (default, empty) | unset/`""` | `8.8.8.8` | `172.18.0.1` | `172.18.0.1` (XFF ignored) |
| Trust off, no client | unset/`""` | `8.8.8.8` | `None` | `"unknown"` |
| Single proxy, XFF | `10.0.0.0/8` | `8.8.8.8, 10.0.0.1` | `10.0.0.1` | `8.8.8.8` (skip trusted hop) |
| No XFF | `10.0.0.0/8` | `""` | `10.0.0.1` | `10.0.0.1` |
| All hops trusted | `10.0.0.0/8` | `10.0.0.2, 10.0.0.1` | `10.0.0.1` | `10.0.0.1` (defensive fallback) |
| Invalid tokens skipped | `10.0.0.0/8` | `not-an-ip, 8.8.8.8, 10.0.0.1` | `10.0.0.1` | `8.8.8.8` |
| IPv6 | `2001:db8::/32` | `2001:db8:0:1::5, 2001:db8::10` | `2001:db8::10` | `2001:db8:0:1::5` |
| Multi-proxy chain | `10.0.0.0/8,172.16.0.0/12` | `203.0.113.7, 172.16.5.1, 10.0.0.1` | `10.0.0.1` | `203.0.113.7` |
| Misconfigured CIDR tolerated | `bogus/33,10.0.0.0/8` | `8.8.8.8, 10.0.0.1` | `10.0.0.1` | `8.8.8.8` (bogus skipped, trust still on) |

Use `monkeypatch.setenv("TRUSTED_PROXY_CIDRS", ...)` **and** re-import/reload the module
(or expose an injectable loader) so the module-level parsed tuple reflects the case.
Simplest deterministic approach: have `get_client_ip` call the loader with an explicit
parameter, or make `_load_trusted_cidrs` accept a string override for testability. Plan
preference: `get_client_ip(request, trusted_cidrs: str | None = None)` where `None` reads
the env — keeps the prod call one-arg while making all unit cases explicit.

### 5b. One router-level stored-IP test — new `tests/leads/test_router.py` case

`TestSubmitLead::test_trusted_proxy_xff_stores_forwarded_ip`:

- monkeypatch `TRUSTED_PROXY_CIDRS=172.18.0.0/16` (the compose gateway as a *simulated
  trusted proxy* — exactly the dev verification scenario).
- `TestClient` direct peer is `127.0.0.1` (httpx default); set
  `headers={"X-Forwarded-For": "8.8.8.8", "Origin": "https://myshop.com"}`.
- Assert `201`, then read the stored lead (`repo._leads[...]` via `lead_service._get_or_create_repo()`)
  and assert `ip_address == "8.8.8.8"`.

This is the single end-to-end (service+repo) proof that the resolver is actually wired into
`submit_lead`, and that the stored `ip_address` (→ geo input) follows XFF.

### 5c. Existing suite impact

No existing test asserts a client IP, and with `TRUSTED_PROXY_CIDRS` empty in the test env
(`tests/conftest.py` does not set it) behavior is unchanged. The 947-test suite is expected
to stay green with **zero edits** — full CI regression is 947 → 947 + new tests (§8).

---

## 6. Live verification plan (pre/post, dev stack only)

Stack: `docker compose up --build -d` (app 8000, db 5432, redis 6380), seed widget
`e335f32a-b224-49f8-ae64-5a32359726f4` (tenant `87df1c59-...`, domain `https://demo.example.com`,
honeypot `_hp_mq5pzh`), host worker with `$env:DATABASE_URL` / `$env:REDIS_URL` overrides,
JWT at `%TEMP%\opencode\m29_token.txt`. **Never print/commit `.env` secrets or `IPINFO_TOKEN`.**

### Pre-fix (already proven in M27/M29/M30 — cited, not re-run)

Every submit with `X-Forwarded-For: 8.8.8.8` stored `ip_address:"172.18.0.1"`,
`geo_provider:"ipinfo"`, geo fields null.

### Post-fix run A — trust ON (dev verification only)

1. `docker compose up --build -d` with `TRUSTED_PROXY_CIDRS=172.18.0.0/16` in the app
   service env (or host-env for a host-run app). This treats the docker gateway as a
   simulated trusted proxy — never a production value.
2. `POST /public/widget/{seed}/submit`, `X-Forwarded-For: 8.8.8.8`, Origin
   `https://demo.example.com` → expect **201**.
3. `GET /widgets/{seed}/leads` (Bearer) → expect `ip_address:"8.8.8.8"`.
4. Distinct per-IP buckets: fire 2–3 submits with the **same** XFF IP from the API directly
   (bypassing Redis host-side limits is fine — the *key shape* is what is proven); confirm
   rate-limit Redis keys now contain `8.8.8.8` not `172.18.0.1` (`redis-cli -p 6380
   KEYS 'ratelimit:*'`).
5. Worker completes enrichment on `8.8.8.8` → expect geo to resolve (ipinfo:
   country `US`, city populated) while `geo_provider:"ipinfo"`.
6. Clean up via batch-delete → 204; stop host worker; `docker compose down`.

### Post-fix run B — trust OFF (default safety proof)

7. Revert `TRUSTED_PROXY_CIDRS` to unset/empty (rebuild/restart).
8. Repeat the same submit with `X-Forwarded-For: 8.8.8.8` → expect stored
   `ip_address:"172.18.0.1"` again, geo null. **This proves the default remains the
   direct-peer behavior** — nothing broke, and the feature is inert until an operator opts in.

### Pass criteria

- Run A: stored IP = `8.8.8.8`, per-IP rate-limit buckets distinct, geo resolves to US.
- Run B: stored IP = `172.18.0.1` (direct peer), confirming secure-by-default.

---

## 7. Env/documentation updates

### `.env.example`

```bash
# Comma-separated CIDRs of proxies you trust to set X-Forwarded-For.
# LEAVE EMPTY to keep the direct TCP peer as the client IP (secure default).
# Only set this when the app is behind a reverse proxy that overwrites XFF.
TRUSTED_PROXY_CIDRS=
```

### `AGENTS.md`

- Add `TRUSTED_PROXY_CIDRS` to the documented env vars (with the security contract:
  empty = direct peer; set only behind a proxy that overwrites XFF).
- Note the resolver location (`app/dependencies/client_ip.py`) and that it feeds
  rate-limit keys, fingerprint, stored IP, and geo — one resolver, all side effects.
- Add the live-verification note (run A/B in §6) to the M-series live-test lore.

### Ruff/isort/black

- `client_ip.py` needs no per-file ignores: broad `except ValueError` on CIDR parse is a
  plain `ValueError`, not `BLE001`; the intent is documented in the module docstring, not
  via `# noqa` where avoidable. If a `S110`-style best-effort is introduced, follow the
  existing `pyproject.toml` per-file-ignore pattern (`app/core/database.py`, etc.).
- `isort` profile `black`, `black` line length 88 — new file formatted per repo convention.

---

## 8. CI regression expectation

Verbatim pytest invocation from `.github/workflows/ci.yml`:

```
962 passed in 57.48s
TOTAL ... 2938 statements, 0 missing → 100% coverage
```

**Verified post-fix: 947 → 962 passed / 0 failed / 100% coverage** — 14 unit tests in
`tests/leads/test_client_ip.py` + 1 router test in `tests/leads/test_router.py`
(`app/dependencies/client_ip.py` 41/41). `tests/repositories/test_postgres_lead_repo_live.py` remains
auto-ignored via `pyproject.toml` `addopts` (unchanged). The pytest command in `ci.yml` is
**byte-for-byte unchanged**; if it ever diverges from AGENTS.md, `ci.yml` is authoritative.
Full lint trio (`isort --check-only --diff .`, `black --check --diff .`, `ruff check .`)
passes on the whole repo. Plain `pytest` adds the live-E2E files (`tests/test_e2e.py`, always
CI-excluded): 1020 passed, the 11 E2E failures are the pre-existing live-Supabase
`access_token` dependency, not regressions.

---

## Live verification (executed, dev stack, run A/B)

Stack: `docker compose up --build -d` (app 8000 / db 5432 / redis host port 6380), seed
widget `e335f32a-...`, host worker on all three queues with host-side
`$env:DATABASE_URL`/`$env:REDIS_URL`. JWT at `%TEMP%\opencode\m29_token.txt` had **expired**
by this run, so stored-IP and geo evidence was read directly from Postgres (psql) instead of
the dashboard API — equally authoritative, and cleanup used the same `DELETE` path (the M-series
batch-delete API was unavailable without a valid token).

### Run A — `TRUSTED_PROXY_CIDRS=172.18.0.0/16` (simulated trusted proxy)

Container env confirmed `TRUSTED_PROXY_CIDRS=172.18.0.0/16`; new resolver code confirmed live
in the image. Three submits, all `X-Forwarded-For` honored:

| # | XFF sent | HTTP | stored `ip_address` | status / geo_provider | geo country / city / region / isp |
|---|---|---|---|---|---|
| 1 | `8.8.8.8` | 201 | **`8.8.8.8`** | enriched / ipinfo | US / Mountain View / California / AS15169 Google LLC |
| 2 | `8.8.8.8` | 201 | **`8.8.8.8`** | enriched / ipinfo | US / Mountain View / California / AS15169 Google LLC |
| 3 | `9.9.9.9` | 201 | **`9.9.9.9`** | enriched / ipinfo | US / Ashburn / Virginia / AS19281 Quad9 |

Rate-limit keys (Redis db 0) are **distinct per XFF IP** — pre-fix they were all
`172.18.0.1`:

```
ratelimit:global_ip:8.8.8.8:submit = 2
ratelimit:global_ip:9.9.9.9:submit = 1
ratelimit:widget_ip:{seed}:8.8.8.8:submit = 2
ratelimit:widget_ip:{seed}:9.9.9.9:submit = 1
ratelimit:widget_global:{seed}:submit = 3
```

**Pass criteria met:** stored IP = XFF value; per-IP rate-limit buckets distinct; geo resolves
to US for the public IP (the pre-fix null-geo artifact is gone).

### Run B — `TRUSTED_PROXY_CIDRS=` (empty, secure default)

Two submits sent with `X-Forwarded-For: 8.8.8.8`; both stored **`172.18.0.1`** (the direct TCP
peer / docker gateway), and rate-limit keys reverted to the single shared bucket:

```
ratelimit:global_ip:172.18.0.1:submit
ratelimit:widget_ip:{seed}:172.18.0.1:submit
```

Geo fields all **null** (`geo_country/city/region/isp`) with `geo_provider:"ipinfo"`,
`status:"enriched"` — the exact pre-fix F7 artifact (private IP → bogon), confirming the
default preserves prior behavior and the feature is inert until an operator opts in.

### Environment notes (F7-unrelated)

- RQ 2.10 `SimpleWorker` on Windows does **not** auto-requeue jobs parked in the
  `rq:scheduled:*` registry. Run A's lead #1 hit a transient provider outage (ipapi.co 429 on
  all three providers), was "scheduled for retry", and stayed parked; it was re-queued
  manually via `rq.registry.ScheduledJobRegistry.requeue` and then enriched from the geo
  cache. The other five jobs completed on first attempt. Pre-existing worker behavior, not
  touched by this fix.
- `worker.log` contained ipinfo URLs carrying the `IPINFO_TOKEN` query value — **not
  reproduced here** and deleted with the log at cleanup, matching M30's practice.

### Cleanup

- All verification leads deleted (psql) → 0 remaining; seed widget intact.
- Host worker stopped; `worker.log`/`worker.err` removed; pid file removed.
- `docker compose down` (DB volume retained). `.env` left with `TRUSTED_PROXY_CIDRS=`
  (empty secure default).

---

## 9. Commits (executed)

Per the M28/M30 pattern (one fix commit, one test commit, one docs commit; pre-commit
guardrail `git status` + `git diff --cached --stat`, never stage `.env`):

1. **`5697b6c` `fix(leads): resolve client IP from trusted X-Forwarded-For when TRUSTED_PROXY_CIDRS set (F7)`**
   — `app/dependencies/client_ip.py` (new) + `app/services/lead_service.py:104` call-site
   swap + `.env.example` `TRUSTED_PROXY_CIDRS` entry.
2. **`6b27022` `test(leads): unit tests for client-IP resolver + trusted-XFF stored-IP router test (F7)`**
   — `tests/leads/test_client_ip.py` (new, 14 tests) + one case in `tests/leads/test_router.py`.
3. **`ff4a9d4` `docs(reviews): add M31 F7 proxy-trust fix plan`** — this file, plus AGENTS.md
   env documentation. Live run A/B evidence recorded in this report.

---

## 10. F7 disposition

| ID | Description | Tier | Disposition |
|---|---|---|---|
| F7 | X-Forwarded-For ignored; client IP = direct TCP peer (172.18.0.1 docker gateway) → shared rate-limit bucket, colliding fingerprints, null geo | C (flag) | **CLOSED** — env-gated resolver (`app/dependencies/client_ip.py`), secure-by-default; mocked suite 962/100% and live run A/B proof (§Live verification): trust on → XFF IP stored + per-IP buckets + geo US; trust off (default) → direct peer + shared bucket + null geo restored. |

Resolution recorded here: the design decision requested for this Tier C item was **env-gated
trust** (no uvicorn flag, no compose topology change). Sign-off for the disposition lives in
this row; the live run A/B evidence is the closure proof.

---

## 11. Out of scope (explicit)

- No compose topology change (no edge proxy service added).
- No uvicorn `--proxy-headers` / `--forwarded-allow-ips` change.
- No trust of the docker subnet by default.
- No change to rate-limit tiers, fingerprint algorithm, or geo providers — only the IP fed
  into them.
