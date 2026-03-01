-- ============================================================
-- Fortnite Tracker — PostgreSQL Schema (Supabase)
-- Migration 001: Tables + Row Level Security
-- ============================================================

-- ┌──────────────────────────────────────────────────────────┐
-- │  1. PLAYERS — Jogadores monitorados                      │
-- └──────────────────────────────────────────────────────────┘
CREATE TABLE IF NOT EXISTS players (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE,
    platforms   TEXT[] DEFAULT '{}',
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- ┌──────────────────────────────────────────────────────────┐
-- │  2. SNAPSHOTS — Uma execução do scraper para um jogador  │
-- └──────────────────────────────────────────────────────────┘
CREATE TABLE IF NOT EXISTS snapshots (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    player_id   UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    status      TEXT NOT NULL DEFAULT 'sucesso',  -- sucesso, erro, privado, captcha
    scraped_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_player ON snapshots(player_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_scraped_at ON snapshots(scraped_at DESC);

-- ┌──────────────────────────────────────────────────────────┐
-- │  3. OVERVIEW_STATS — Lifetime Overview (tempo, BP)       │
-- └──────────────────────────────────────────────────────────┘
CREATE TABLE IF NOT EXISTS overview_stats (
    id                      UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    snapshot_id             UUID NOT NULL UNIQUE REFERENCES snapshots(id) ON DELETE CASCADE,
    play_time               TEXT DEFAULT 'N/A',
    battle_pass_level       TEXT DEFAULT 'N/A',
    wins                    INTEGER DEFAULT 0,
    kd_ratio                NUMERIC(6,2) DEFAULT 0.0,
    win_percentage          TEXT DEFAULT '0%',
    total_kills             INTEGER DEFAULT 0,
    total_matches           INTEGER DEFAULT 0,
    top_3_5_10              INTEGER DEFAULT 0,
    top_6_12_25             INTEGER DEFAULT 0
);

-- ┌──────────────────────────────────────────────────────────┐
-- │  4. PERIOD_STATS — Last 7 Days / Last 30 Days            │
-- └──────────────────────────────────────────────────────────┘
CREATE TABLE IF NOT EXISTS period_stats (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    snapshot_id         UUID NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    period_name         TEXT NOT NULL,  -- 'Last 7 Days' ou 'Last 30 Days'
    matches             INTEGER DEFAULT 0,
    win_percentage      TEXT DEFAULT '0%',
    wins                INTEGER DEFAULT 0,
    kd_ratio            NUMERIC(6,2) DEFAULT 0.0,
    kills               INTEGER DEFAULT 0,
    top_3_5_10          INTEGER DEFAULT 0,
    top_6_12_25         INTEGER DEFAULT 0,

    UNIQUE (snapshot_id, period_name)
);

-- ┌──────────────────────────────────────────────────────────┐
-- │  5. MODE_STATS — Stats por modo (Solo, Duos, etc.)       │
-- └──────────────────────────────────────────────────────────┘
CREATE TABLE IF NOT EXISTS mode_stats (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    snapshot_id         UUID NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    mode_name           TEXT NOT NULL,
    matches             INTEGER DEFAULT 0,
    tracker_rating      TEXT DEFAULT 'N/A',
    wins                INTEGER DEFAULT 0,
    win_percentage      TEXT DEFAULT '0%',
    kills               INTEGER DEFAULT 0,
    kd_ratio            NUMERIC(6,2) DEFAULT 0.0,
    top_position_1_name TEXT DEFAULT 'N/A',
    top_position_1      TEXT DEFAULT 'N/A',
    top_position_2_name TEXT DEFAULT 'N/A',
    top_position_2      TEXT DEFAULT 'N/A',

    UNIQUE (snapshot_id, mode_name)
);

-- ┌──────────────────────────────────────────────────────────┐
-- │  6. RANK_INFO — Ranks competitivos                       │
-- └──────────────────────────────────────────────────────────┘
CREATE TABLE IF NOT EXISTS rank_info (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    snapshot_id     UUID NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    mode_name       TEXT NOT NULL,
    current_rank    TEXT DEFAULT 'Unrated',
    best_rank       TEXT DEFAULT 'N/A',

    UNIQUE (snapshot_id, mode_name)
);

-- ┌──────────────────────────────────────────────────────────┐
-- │  7. RECENT_MATCHES — Sessões de partidas recentes        │
-- └──────────────────────────────────────────────────────────┘
CREATE TABLE IF NOT EXISTS recent_matches (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    snapshot_id     UUID NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    session_header  TEXT DEFAULT '',
    match_details   JSONB DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_recent_matches_snapshot ON recent_matches(snapshot_id);

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================
-- Princípio: leitura apenas para usuários autenticados,
--            escrita apenas para service_role (scraper CI).

ALTER TABLE players        ENABLE ROW LEVEL SECURITY;
ALTER TABLE snapshots       ENABLE ROW LEVEL SECURITY;
ALTER TABLE overview_stats  ENABLE ROW LEVEL SECURITY;
ALTER TABLE period_stats    ENABLE ROW LEVEL SECURITY;
ALTER TABLE mode_stats      ENABLE ROW LEVEL SECURITY;
ALTER TABLE rank_info       ENABLE ROW LEVEL SECURITY;
ALTER TABLE recent_matches  ENABLE ROW LEVEL SECURITY;

-- ── SELECT — somente autenticados podem ler ──────────────────
CREATE POLICY "Authenticated read players"
    ON players FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Authenticated read snapshots"
    ON snapshots FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Authenticated read overview_stats"
    ON overview_stats FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Authenticated read period_stats"
    ON period_stats FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Authenticated read mode_stats"
    ON mode_stats FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Authenticated read rank_info"
    ON rank_info FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Authenticated read recent_matches"
    ON recent_matches FOR SELECT
    TO authenticated
    USING (true);

-- ── INSERT/UPDATE/DELETE bloqueado pela API pública ──────────
-- O scraper usa service_role key que BYPASSA o RLS,
-- então NÃO precisamos de policies de escrita.
-- Qualquer tentativa via anon/authenticated será negada.
