-- ═══════════════════════════════════════════════════════════════
-- PRAGMAS
-- These must also be set on every connection in code (see connection.py)
-- ═══════════════════════════════════════════════════════════════
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous  = NORMAL;


-- ═══════════════════════════════════════════════════════════════
-- LEAGUES
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS leagues (
    id          INTEGER PRIMARY KEY,        -- API-Football league ID
    name        TEXT    NOT NULL,
    country     TEXT,
    logo_url    TEXT,
    season      INTEGER,
    created_at  TEXT    DEFAULT (datetime('now'))
);


-- ═══════════════════════════════════════════════════════════════
-- TEAMS
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS teams (
    id          INTEGER PRIMARY KEY,        -- API-Football team ID
    name        TEXT    NOT NULL,
    short_name  TEXT,
    logo_url    TEXT,
    venue_name  TEXT,
    country     TEXT,
    created_at  TEXT    DEFAULT (datetime('now'))
);


-- ═══════════════════════════════════════════════════════════════
-- FIXTURES
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS fixtures (
    id              INTEGER PRIMARY KEY,    -- API-Football fixture ID
    league_id       INTEGER REFERENCES leagues(id),
    home_team_id    INTEGER REFERENCES teams(id),
    away_team_id    INTEGER REFERENCES teams(id),
    kickoff_utc     TEXT    NOT NULL,       -- ISO 8601 e.g. '2025-03-20T18:00:00Z'
    status          TEXT    DEFAULT 'NS',   -- NS | LIVE | FT | PST | CANC
    home_score      INTEGER,
    away_score      INTEGER,
    round           TEXT,
    venue_name      TEXT,
    md_report_path  TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_fixtures_kickoff ON fixtures(kickoff_utc);
CREATE INDEX IF NOT EXISTS idx_fixtures_status  ON fixtures(status);
CREATE INDEX IF NOT EXISTS idx_fixtures_league  ON fixtures(league_id);


-- ═══════════════════════════════════════════════════════════════
-- PREDICTIONS (replaces flat JSON cache files)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS predictions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id        INTEGER NOT NULL REFERENCES fixtures(id) ON DELETE CASCADE,
    analysis_type     TEXT    NOT NULL DEFAULT 'enhanced',  -- 'basic' | 'enhanced'
    predicted_winner  TEXT,               -- 'home' | 'away' | 'draw'
    home_win_prob     REAL,
    draw_prob         REAL,
    away_win_prob     REAL,
    confidence        REAL,
    recommended_bet   TEXT,
    messaging_json    TEXT    NOT NULL,   -- bot payload stored as json.dumps()
    model_used        TEXT,               -- e.g. 'gpt-4'
    is_valid          INTEGER DEFAULT 1,  -- 1 = true | 0 = false
    created_at        TEXT    DEFAULT (datetime('now')),
    expires_at        TEXT,               -- NULL = never expires

    UNIQUE(fixture_id, analysis_type)
);

CREATE INDEX IF NOT EXISTS idx_predictions_fixture ON predictions(fixture_id);
CREATE INDEX IF NOT EXISTS idx_predictions_valid   ON predictions(is_valid);
CREATE INDEX IF NOT EXISTS idx_predictions_created ON predictions(created_at DESC);


-- ═══════════════════════════════════════════════════════════════
-- MATCH CONTEXT (weather, pitch, injuries, team news)
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS match_context (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id       INTEGER NOT NULL REFERENCES fixtures(id) ON DELETE CASCADE,
    weather_json     TEXT,               -- Open-Meteo payload as json.dumps()
    pitch_condition  TEXT,
    team_news_home   TEXT,
    team_news_away   TEXT,
    key_injuries     TEXT,               -- json.dumps() e.g. [{"player":"Salah","team":"home","status":"Injured"}]
    fetched_at       TEXT DEFAULT (datetime('now')),

    UNIQUE(fixture_id)
);


-- ═══════════════════════════════════════════════════════════════
-- SUBSCRIPTIONS
-- One row per successful Paystack payment.
-- payment_phone + pin = the cross-channel validation pair.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS subscriptions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Payment identity
    payment_phone     TEXT NOT NULL,         -- M-Pesa number e.g. '+254712345678'
    paystack_ref      TEXT UNIQUE,           -- Paystack transaction reference
    amount            REAL,
    currency          TEXT DEFAULT 'KES',
    plan              TEXT NOT NULL,         -- 'daily' | 'weekly' | 'monthly'

    -- Cross-channel validation pair (both required to activate)
    pin               TEXT NOT NULL UNIQUE,  -- 6-digit e.g. '847291'
    pin_generated_at  TEXT DEFAULT (datetime('now')),
    pin_used          INTEGER DEFAULT 0,     -- 0 = not yet activated | 1 = activated on at least one channel

    -- Subscription window
    status            TEXT DEFAULT 'active', -- 'active' | 'expired' | 'cancelled'
    starts_at         TEXT NOT NULL,
    expires_at        TEXT NOT NULL,

    -- Which channel triggered this payment
    initiated_from    TEXT,                  -- 'whatsapp' | 'telegram'

    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sub_phone_pin  ON subscriptions(payment_phone, pin);
CREATE INDEX IF NOT EXISTS idx_sub_phone      ON subscriptions(payment_phone);
CREATE INDEX IF NOT EXISTS idx_sub_pin        ON subscriptions(pin);
CREATE INDEX IF NOT EXISTS idx_sub_status     ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_sub_expires    ON subscriptions(expires_at);
CREATE INDEX IF NOT EXISTS idx_sub_ref        ON subscriptions(paystack_ref);


-- ═══════════════════════════════════════════════════════════════
-- PLATFORM SESSIONS
-- Created/updated when a user activates using phone + pin.
-- One row per platform per user — upserted on every activation.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS platform_sessions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id   INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,

    platform          TEXT NOT NULL,    -- 'whatsapp' | 'telegram'
    platform_user_id  TEXT NOT NULL,    -- phone number or telegram chat_id

    -- Snapshot at activation time for fast access checks
    plan              TEXT NOT NULL,
    expires_at        TEXT NOT NULL,

    activated_at      TEXT DEFAULT (datetime('now')),
    last_seen_at      TEXT DEFAULT (datetime('now')),

    UNIQUE(platform, platform_user_id)  -- one active session per user per channel
);

CREATE INDEX IF NOT EXISTS idx_session_sub      ON platform_sessions(subscription_id);
CREATE INDEX IF NOT EXISTS idx_session_platform ON platform_sessions(platform, platform_user_id);
CREATE INDEX IF NOT EXISTS idx_session_expires  ON platform_sessions(expires_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_session_sub_platform ON platform_sessions(subscription_id, platform);


-- ═══════════════════════════════════════════════════════════════
-- ACTIVATION ATTEMPTS (brute force protection)
-- Logs every phone + pin submission per platform user.
-- ═══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS activation_attempts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    platform          TEXT NOT NULL,     -- 'whatsapp' | 'telegram'
    platform_user_id  TEXT NOT NULL,     -- phone or chat_id of the person attempting
    phone_tried       TEXT NOT NULL,     -- payment_phone they submitted
    pin_tried         TEXT NOT NULL,     -- PIN they submitted
    success           INTEGER DEFAULT 0, -- 0 = failed | 1 = success
    failure_reason    TEXT,              -- lockout / invalid_credentials / etc.
    attempted_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_attempts_user ON activation_attempts(platform, platform_user_id);
CREATE INDEX IF NOT EXISTS idx_attempts_time ON activation_attempts(attempted_at);
CREATE INDEX IF NOT EXISTS idx_attempts_lockout ON activation_attempts(platform, platform_user_id, success, attempted_at);


-- ═══════════════════════════════════════════════════════════════
-- TRIGGERS
-- ═══════════════════════════════════════════════════════════════

-- Auto-update fixtures.updated_at on any row change
CREATE TRIGGER IF NOT EXISTS trg_fixtures_updated_at
AFTER UPDATE ON fixtures
BEGIN
    UPDATE fixtures
    SET updated_at = datetime('now')
    WHERE id = NEW.id;
END;

-- Auto-update subscriptions.updated_at on any row change
CREATE TRIGGER IF NOT EXISTS trg_subscriptions_updated_at
AFTER UPDATE ON subscriptions
BEGIN
    UPDATE subscriptions
    SET updated_at = datetime('now')
    WHERE id = NEW.id;
END;

-- Auto-expire subscriptions that have passed their expires_at
CREATE TRIGGER IF NOT EXISTS trg_subscriptions_auto_expire
AFTER UPDATE ON subscriptions
BEGIN
    UPDATE subscriptions
    SET status = 'expired'
    WHERE status     = 'active'
      AND expires_at < datetime('now');
END;

-- Mirror expiry to platform_sessions when subscription expires
-- Keeps access checks fast without needing a JOIN
CREATE TRIGGER IF NOT EXISTS trg_sync_session_expiry
AFTER UPDATE OF status ON subscriptions
WHEN NEW.status = 'expired'
BEGIN
    UPDATE platform_sessions
    SET expires_at = NEW.expires_at
    WHERE subscription_id = NEW.id;
END;

-- BOT USER STATES (replaces data/user_states.json and telegram memory files)
CREATE TABLE IF NOT EXISTS user_states (
    platform         TEXT NOT NULL,
    user_id          TEXT NOT NULL,
    state            TEXT NOT NULL,
    state_timestamp  TEXT NOT NULL,
    metadata_json    TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    PRIMARY KEY(platform, user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_states_updated ON user_states(updated_at);

-- PAYMENT TRANSACTIONS (replaces data/transactions.json + in-memory payment map)
CREATE TABLE IF NOT EXISTS payment_transactions (
    transaction_id   TEXT PRIMARY KEY,
    platform         TEXT,
    user_id          TEXT,
    amount           REAL,
    package          TEXT,
    status           TEXT,
    reference        TEXT,
    phone_number     TEXT,
    created_at       TEXT,
    verified_at      TEXT,
    metadata_json    TEXT,
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_payment_txn_user      ON payment_transactions(platform, user_id);
CREATE INDEX IF NOT EXISTS idx_payment_txn_status    ON payment_transactions(status);
CREATE INDEX IF NOT EXISTS idx_payment_txn_reference ON payment_transactions(reference);

CREATE TRIGGER IF NOT EXISTS trg_user_states_updated_at
AFTER UPDATE ON user_states
BEGIN
    UPDATE user_states
    SET updated_at = datetime('now')
    WHERE platform = NEW.platform
      AND user_id  = NEW.user_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_payment_transactions_updated_at
AFTER UPDATE ON payment_transactions
BEGIN
    UPDATE payment_transactions
    SET updated_at = datetime('now')
    WHERE transaction_id = NEW.transaction_id;
END;
