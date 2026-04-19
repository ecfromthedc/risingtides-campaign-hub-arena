-- ============================================================
-- Arena Shadow Build — Migration 001: Arena tables (additive)
-- ============================================================
-- All new tables FK into existing prod tables. Zero destructive ops.

BEGIN;

-- ---- operators -------------------------------------------------
CREATE TABLE IF NOT EXISTS operators (
    id           SERIAL PRIMARY KEY,
    slug         VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    tagline      VARCHAR(255) DEFAULT '',
    color        VARCHAR(20)  DEFAULT '#D4A843',
    created_at   TIMESTAMP DEFAULT NOW()
);

-- ---- squads ----------------------------------------------------
CREATE TABLE IF NOT EXISTS squads (
    id         SERIAL PRIMARY KEY,
    slug       VARCHAR(100) NOT NULL UNIQUE,
    name       VARCHAR(255) NOT NULL,
    motto      VARCHAR(500) DEFAULT '',
    color      VARCHAR(20)  DEFAULT '#D4A843',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS squad_members (
    squad_id    INT REFERENCES squads(id)    ON DELETE CASCADE,
    operator_id INT REFERENCES operators(id) ON DELETE CASCADE,
    role        VARCHAR(50) DEFAULT 'captain',
    joined_at   TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (squad_id, operator_id)
);

-- ---- sound_tags ------------------------------------------------
CREATE TABLE IF NOT EXISTS sound_tags (
    id                  SERIAL PRIMARY KEY,
    sound_key           VARCHAR(500) NOT NULL UNIQUE,   -- "song|artist" (lowercased)
    kind                VARCHAR(20)  NOT NULL,          -- 'catalog' | 'client' | 'organic'
    multiplier          NUMERIC(4,2) DEFAULT 1.0,
    source_campaign_id  INT REFERENCES campaigns(id) ON DELETE SET NULL,
    added_at            TIMESTAMP DEFAULT NOW()
);

-- ---- xp_events -------------------------------------------------
CREATE TABLE IF NOT EXISTS xp_events (
    id             SERIAL PRIMARY KEY,
    operator_slug  VARCHAR(100) NOT NULL,
    video_id       INT REFERENCES internal_video_cache(id) ON DELETE CASCADE,
    video_url      TEXT NOT NULL,
    username       VARCHAR(255) NOT NULL,
    source_kind    VARCHAR(20)  NOT NULL,               -- 'client' | 'catalog'
    sound_key      VARCHAR(500),
    views          INT  DEFAULT 0,
    base_xp        INT  DEFAULT 0,
    multiplier     NUMERIC(4,2) DEFAULT 1.0,
    xp             INT  NOT NULL,
    event_at       TIMESTAMP DEFAULT NOW(),
    UNIQUE (video_id, operator_slug)
);
CREATE INDEX IF NOT EXISTS ix_xp_events_operator ON xp_events(operator_slug);
CREATE INDEX IF NOT EXISTS ix_xp_events_event_at ON xp_events(event_at DESC);
CREATE INDEX IF NOT EXISTS ix_xp_events_sound    ON xp_events(sound_key);

-- ---- slingshot_edges -------------------------------------------
CREATE TABLE IF NOT EXISTS slingshot_edges (
    id           SERIAL PRIMARY KEY,
    sound_key    VARCHAR(500) NOT NULL,
    first_op     VARCHAR(100) NOT NULL,
    second_op    VARCHAR(100) NOT NULL,
    first_at     TIMESTAMP,
    second_at    TIMESTAMP,
    window_hours INT DEFAULT 72,
    bonus_xp     INT NOT NULL,
    created_at   TIMESTAMP DEFAULT NOW(),
    UNIQUE (sound_key, first_op, second_op)
);
CREATE INDEX IF NOT EXISTS ix_slingshot_first  ON slingshot_edges(first_op);
CREATE INDEX IF NOT EXISTS ix_slingshot_second ON slingshot_edges(second_op);

-- ---- captain_leagues -------------------------------------------
CREATE TABLE IF NOT EXISTS captain_leagues (
    id             SERIAL PRIMARY KEY,
    operator_slug  VARCHAR(100) NOT NULL,
    week_start     DATE NOT NULL,
    league         VARCHAR(20) NOT NULL,   -- bronze | silver | gold | obsidian
    xp             INT NOT NULL,
    rank_in_league INT,
    UNIQUE (operator_slug, week_start)
);

-- ---- tide_log --------------------------------------------------
CREATE TABLE IF NOT EXISTS tide_log (
    day         DATE PRIMARY KEY,
    total_xp    INT NOT NULL,
    rolling_7d  INT NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'green',
    event_count INT DEFAULT 0
);

-- ============================================================
-- Seed: operators from internal_creator_groups(kind='booked_by')
-- ============================================================
INSERT INTO operators (slug, display_name, tagline)
SELECT slug, title, 'Captain of ' || title
FROM internal_creator_groups
WHERE kind = 'booked_by'
ON CONFLICT (slug) DO NOTHING;

-- Seed single fleet squad for v0
INSERT INTO squads (slug, name, motto, color)
VALUES ('flagship', 'The Flagship', 'First in the water, last to leave.', '#D4A843')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO squad_members (squad_id, operator_id)
SELECT s.id, o.id
FROM squads s CROSS JOIN operators o
WHERE s.slug = 'flagship'
ON CONFLICT DO NOTHING;

-- Seed sound tags: every campaign song = client sound
INSERT INTO sound_tags (sound_key, kind, multiplier, source_campaign_id)
SELECT DISTINCT
    LOWER(TRIM(COALESCE(c.song,'') || '|' || COALESCE(c.artist,''))) AS sound_key,
    'client', 1.0, MIN(c.id)
FROM campaigns c
WHERE c.song IS NOT NULL AND c.song <> ''
GROUP BY LOWER(TRIM(COALESCE(c.song,'') || '|' || COALESCE(c.artist,'')))
ON CONFLICT (sound_key) DO NOTHING;

COMMIT;
