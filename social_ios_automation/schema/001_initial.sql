-- ============================================================
-- Migration 001: initial schema for the automation backend
-- PostgreSQL 14+
-- Run: psql $DATABASE_URL -f 001_initial.sql
-- ============================================================

BEGIN;

-- ── platform accounts ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS platform_accounts (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id        UUID        NOT NULL,                -- FK → models table (external)
    platform        TEXT        NOT NULL,                -- 'fansly','instagram','tiktok','x','reddit'
    account_type    TEXT        NOT NULL DEFAULT 'content', -- 'content','promo'
    username        TEXT        NOT NULL,
    session_file    TEXT,                                -- path to .session_*.json
    device_file     TEXT,                                -- path to device .json
    status          TEXT        NOT NULL DEFAULT 'ok',   -- ok|login_required|limited|paused|disabled
    last_login_check TIMESTAMPTZ,
    limits          JSONB       NOT NULL DEFAULT '{
        "posts_per_day": 3,
        "messages_per_hour": 10,
        "min_pause_seconds": 30
    }',
    auto_modes      JSONB       NOT NULL DEFAULT '{}',   -- {"feed_post": false, "ppv_message": false}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_accounts_model_platform
    ON platform_accounts(model_id, platform, username);

-- ── publish jobs ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS publish_jobs (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key  TEXT        NOT NULL UNIQUE,
    account_id       UUID        NOT NULL REFERENCES platform_accounts(id),
    job_type         TEXT        NOT NULL,   -- feed_post|ppv_message|social_post|proof_screenshot|profile_update|subscribers_message
    status           TEXT        NOT NULL DEFAULT 'queued',
    -- queued|running|awaiting_confirm|published|sent|needs_human|failed|cancelled|removed_by_platform
    payload          JSONB       NOT NULL DEFAULT '{}',
    result           JSONB,
    approvals        JSONB       NOT NULL DEFAULT '[]',  -- [{owner_id, approved_at}]
    approvals_required INT       NOT NULL DEFAULT 1,
    screenshot_path  TEXT,
    external_id      TEXT,       -- post_id / message_id returned by platform
    scheduled_for    TIMESTAMPTZ,
    started_at       TIMESTAMPTZ,
    finished_at      TIMESTAMPTZ,
    error_message    TEXT,
    retry_count      INT         NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_publish_jobs_status ON publish_jobs(status);
CREATE INDEX IF NOT EXISTS ix_publish_jobs_account ON publish_jobs(account_id, status);
CREATE INDEX IF NOT EXISTS ix_publish_jobs_scheduled ON publish_jobs(scheduled_for) WHERE scheduled_for IS NOT NULL;

-- ── publish events (audit trail per job) ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS publish_events (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id      UUID        NOT NULL REFERENCES publish_jobs(id) ON DELETE CASCADE,
    event_type  TEXT        NOT NULL,   -- status_change|approval|screenshot|error|metric_read
    old_status  TEXT,
    new_status  TEXT,
    actor_id    TEXT,        -- owner_id or 'system'
    details     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_publish_events_job ON publish_events(job_id);

-- ── promo videos (A3) ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS promo_videos (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id        UUID        NOT NULL,
    work_item_id    UUID,                   -- FK → plan items (external)
    original_path   TEXT        NOT NULL,
    allowed_platforms JSONB     NOT NULL DEFAULT '[]',  -- ["instagram","tiktok","x"]
    compliance_check BOOLEAN    NOT NULL DEFAULT FALSE, -- owner manually checked
    compliance_by    TEXT,
    compliance_at    TIMESTAMPTZ,
    second_person    BOOLEAN    NOT NULL DEFAULT FALSE,
    second_person_verified BOOLEAN NOT NULL DEFAULT FALSE,
    status          TEXT        NOT NULL DEFAULT 'uploaded', -- uploaded|approved|withdrawn
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS social_variants (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    promo_video_id  UUID        NOT NULL REFERENCES promo_videos(id),
    platform        TEXT        NOT NULL,    -- instagram|tiktok|x
    file_path       TEXT        NOT NULL,
    cover_path      TEXT,
    duration_secs   FLOAT,
    resolution      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS social_posts (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_id      UUID        NOT NULL REFERENCES social_variants(id),
    job_id          UUID        REFERENCES publish_jobs(id),
    platform        TEXT        NOT NULL,
    external_id     TEXT,
    status          TEXT        NOT NULL DEFAULT 'pending', -- pending|published|removed_by_platform
    published_at    TIMESTAMPTZ,
    removed_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── account metrics (B5) ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS account_metrics (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID        NOT NULL REFERENCES platform_accounts(id),
    date            DATE        NOT NULL,
    subscribers_total   INT,
    subscribers_new     INT,
    subscribers_churned INT,
    subscribers_renewed INT,
    income_total_cents  BIGINT,
    income_subscriptions_cents BIGINT,
    income_ppv_cents    BIGINT,
    income_tips_cents   BIGINT,
    chargebacks_cents   BIGINT,
    post_views          INT,
    raw                 JSONB,
    collected_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (account_id, date)
);

CREATE TABLE IF NOT EXISTS post_metrics (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    social_post_id UUID     REFERENCES social_posts(id),
    account_id  UUID        REFERENCES platform_accounts(id),
    external_id TEXT        NOT NULL,
    date        DATE        NOT NULL,
    views       INT,
    likes       INT,
    comments    INT,
    reposts     INT,
    link_clicks INT,
    raw         JSONB,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (external_id, date)
);

-- ── inbox snapshot (B4) ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS inbox_snapshot (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID        NOT NULL REFERENCES platform_accounts(id),
    conversation_id TEXT        NOT NULL,
    client_username TEXT,
    unread_count    INT         NOT NULL DEFAULT 0,
    is_buyer        BOOLEAN     NOT NULL DEFAULT FALSE,
    waiting_since   TIMESTAMPTZ,
    last_checked    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (account_id, conversation_id)
);

-- ── period drafts (C1) ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS period_drafts (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id        UUID        NOT NULL,
    period_start    DATE        NOT NULL,
    period_end      DATE        NOT NULL,
    gross_cents     BIGINT      NOT NULL DEFAULT 0,    -- income from Fansly
    platform_fee_cents BIGINT   NOT NULL DEFAULT 0,
    chargebacks_cents  BIGINT   NOT NULL DEFAULT 0,
    base_cents      BIGINT      GENERATED ALWAYS AS
                    (gross_cents - platform_fee_cents - chargebacks_cents) STORED,
    agency_pct      NUMERIC(5,4) NOT NULL,             -- e.g. 0.2500 = 25%
    agency_cents    BIGINT      GENERATED ALWAYS AS
                    (ROUND((gross_cents - platform_fee_cents - chargebacks_cents) * agency_pct)) STORED,
    model_cents     BIGINT      GENERATED ALWAYS AS
                    ((gross_cents - platform_fee_cents - chargebacks_cents)
                     - ROUND((gross_cents - platform_fee_cents - chargebacks_cents) * agency_pct)) STORED,
    daily_sum_cents BIGINT,     -- sum of daily income rows for cross-check
    daily_discrepancy_pct NUMERIC(6,3),
    needs_review    BOOLEAN     NOT NULL DEFAULT FALSE,
    status          TEXT        NOT NULL DEFAULT 'draft', -- draft|reviewed|approved
    reviewed_by     TEXT,
    reviewed_at     TIMESTAMPTZ,
    formula_snapshot JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_period_drafts_model_period
    ON period_drafts(model_id, period_start, period_end);

-- ── wallets (C3) ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS wallets (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id        UUID        NOT NULL,
    network         TEXT        NOT NULL,   -- 'tron_trc20' | 'evm_erc20' | 'evm_bep20'
    address         TEXT        NOT NULL,
    verified        BOOLEAN     NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    added_by        TEXT        NOT NULL,   -- owner_id
    added_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deactivated_at  TIMESTAMPTZ,
    UNIQUE (model_id, address, network)
);

-- ── payout checks (C3) ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS payout_checks (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    payout_id       UUID        NOT NULL,               -- FK → payouts table (external)
    tx_hash         TEXT        NOT NULL,
    network         TEXT        NOT NULL,
    wallet_id       UUID        REFERENCES wallets(id),
    expected_cents  BIGINT      NOT NULL,
    actual_cents    BIGINT,
    confirmations   INT,
    status          TEXT        NOT NULL DEFAULT 'pending',
    -- pending|verified|needs_human|failed
    discrepancy     JSONB,      -- {'field': 'amount', 'expected': ..., 'actual': ...}
    raw_tx          JSONB,
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tx_hash, network)
);

-- ── notifications (D1) ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS notifications (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT        NOT NULL,
    user_type       TEXT        NOT NULL DEFAULT 'model', -- model|owner
    app             TEXT        NOT NULL DEFAULT 'cabinet', -- cabinet|remote
    event_type      TEXT        NOT NULL,
    category        TEXT        NOT NULL,   -- plan|money|requests|publications|accounts
    title           TEXT,
    body            TEXT        NOT NULL,
    deep_link       TEXT,
    thread_id       TEXT,
    is_urgent       BOOLEAN     NOT NULL DEFAULT FALSE,
    status          TEXT        NOT NULL DEFAULT 'pending', -- pending|sent|delivered|read
    apns_message_id TEXT,
    today_item_id   UUID,       -- linked "Сегодня" item
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at         TIMESTAMPTZ,
    delivered_at    TIMESTAMPTZ,
    read_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_notifications_user ON notifications(user_id, status);
CREATE INDEX IF NOT EXISTS ix_notifications_created ON notifications(created_at DESC);

-- ── notification settings (D2) ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS notification_settings (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT        NOT NULL,
    category        TEXT        NOT NULL,
    enabled         BOOLEAN     NOT NULL DEFAULT TRUE,
    quiet_start     TIME,       -- e.g. '23:00'
    quiet_end       TIME,       -- e.g. '08:00'
    no_text_mode    BOOLEAN     NOT NULL DEFAULT FALSE,  -- D2 "Без текста"
    badge_enabled   BOOLEAN     NOT NULL DEFAULT FALSE,  -- D2 badge off by default
    timezone        TEXT        NOT NULL DEFAULT 'UTC',
    UNIQUE (user_id, category)
);

-- ── devices / APNs tokens (D1) ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS devices (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT        NOT NULL,
    app             TEXT        NOT NULL,   -- 'cabinet' | 'remote'
    apns_token      TEXT        NOT NULL,
    environment     TEXT        NOT NULL DEFAULT 'production', -- production|sandbox
    last_active     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (apns_token, app)
);

-- ── audit log (General rule 4) ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL   PRIMARY KEY,
    actor_id    TEXT        NOT NULL,   -- user_id or 'system'
    actor_type  TEXT        NOT NULL,   -- owner|model|system
    action      TEXT        NOT NULL,
    entity_type TEXT,
    entity_id   TEXT,
    details     JSONB,
    ip_address  INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- append-only: no UPDATE/DELETE on audit_log
-- enforce via RULE in production:
-- CREATE RULE no_update_audit AS ON UPDATE TO audit_log DO INSTEAD NOTHING;
-- CREATE RULE no_delete_audit AS ON DELETE TO audit_log DO INSTEAD NOTHING;

-- ── update triggers ───────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END; $$;

DO $$ DECLARE t TEXT;
BEGIN FOR t IN VALUES ('platform_accounts'),('publish_jobs'),('period_drafts')
    LOOP EXECUTE format(
        'CREATE TRIGGER trg_updated_at BEFORE UPDATE ON %I
         FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t);
    END LOOP;
END $$;

COMMIT;
