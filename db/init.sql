CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    done BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks(done);

CREATE TABLE IF NOT EXISTS scraped_books (
    id SERIAL PRIMARY KEY,
    url VARCHAR(500) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    price NUMERIC(10,2),
    availability VARCHAR(100),
    rating INTEGER,
    description TEXT,
    category VARCHAR(200),
    upc VARCHAR(50),
    image_url VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scraped_books_category ON scraped_books(category);
CREATE INDEX IF NOT EXISTS idx_scraped_books_url ON scraped_books(url);

CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    file_path VARCHAR(500),
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_reports_job_id ON reports(job_id);

-- ============================================================
-- Widgets — configurable embed widget owned by a tenant
-- ============================================================
CREATE TABLE IF NOT EXISTS widgets (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL,
    name        VARCHAR(200) NOT NULL,
    domain      VARCHAR(500) NOT NULL,
    config      JSONB NOT NULL DEFAULT '{}',
    js_version  INTEGER NOT NULL DEFAULT 1,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_widgets_tenant ON widgets(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_widgets_domain ON widgets(tenant_id, domain);

-- ============================================================
-- Leads — form submissions from widgets
-- ============================================================
CREATE TABLE IF NOT EXISTS leads (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    widget_id           UUID NOT NULL REFERENCES widgets(id) ON DELETE CASCADE,
    tenant_id           UUID NOT NULL,
    form_data           JSONB NOT NULL,
    ip_address          INET NOT NULL,
    user_agent          TEXT,
    referer             TEXT,
    fingerprint         VARCHAR(64) NOT NULL,
    geo_country         VARCHAR(100),
    geo_city            VARCHAR(200),
    geo_region          VARCHAR(200),
    geo_isp             VARCHAR(200),
    geo_provider        VARCHAR(50),
    spam_score          REAL DEFAULT 0.0,
    spam_reasons        JSONB,
    honeypot_triggered  BOOLEAN NOT NULL DEFAULT FALSE,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_widget ON leads(widget_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_tenant ON leads(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_leads_spam ON leads(spam_score);
CREATE INDEX IF NOT EXISTS idx_leads_fingerprint ON leads(fingerprint, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_honeypot ON leads(honeypot_triggered) WHERE honeypot_triggered = FALSE;

-- ============================================================
-- Rate Limits — persistent audit trail for rate-limit decisions
-- ============================================================
CREATE TABLE IF NOT EXISTS rate_limits (
    id           BIGSERIAL PRIMARY KEY,
    ip_address   INET NOT NULL,
    widget_id    UUID REFERENCES widgets(id) ON DELETE CASCADE,
    scope        VARCHAR(30) NOT NULL,
    endpoint     VARCHAR(50) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    count        INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_rate_limits_lookup ON rate_limits(ip_address, endpoint, scope, window_start);
