-- ============================================================
-- Arena Shadow Build — Migration 002: Backfill XP + slingshots
-- ============================================================
-- Turns 14,529 historical videos into live XP events.
-- Derives slingshot edges, weekly leagues, daily tide snapshot.

BEGIN;

-- ---- XP events from internal_video_cache -----------------------
-- Each video by an operator-owned username gets one XP event.
-- base_xp = floor(ln(views+1) * 10), min 1
-- multiplier = 1.5 for catalog sounds, 1.0 for client sounds
INSERT INTO xp_events (operator_slug, video_id, video_url, username, source_kind, sound_key, views, base_xp, multiplier, xp, event_at)
SELECT
    g.slug  AS operator_slug,
    v.id    AS video_id,
    v.url   AS video_url,
    v.username,
    CASE WHEN st.kind = 'client'
           OR EXISTS (SELECT 1 FROM matched_videos mv WHERE mv.url = v.url)
         THEN 'client'
         ELSE 'catalog' END AS source_kind,
    LOWER(TRIM(COALESCE(v.song,'') || '|' || COALESCE(v.artist,''))) AS sound_key,
    COALESCE(v.views,0) AS views,
    GREATEST(1, FLOOR(LN(GREATEST(COALESCE(v.views,0),1) + 1) * 10)::INT) AS base_xp,
    CASE WHEN st.kind = 'client'
           OR EXISTS (SELECT 1 FROM matched_videos mv WHERE mv.url = v.url)
         THEN 1.0
         ELSE 1.5 END AS multiplier,
    CAST(
        GREATEST(1, FLOOR(LN(GREATEST(COALESCE(v.views,0),1) + 1) * 10)::INT) *
        (CASE WHEN st.kind = 'client'
                OR EXISTS (SELECT 1 FROM matched_videos mv WHERE mv.url = v.url)
              THEN 1.0
              ELSE 1.5 END)
    AS INT) AS xp,
    COALESCE(
        CASE WHEN v.timestamp   ~ '^\d{4}-\d{2}-\d{2}' THEN v.timestamp::timestamp   END,
        CASE WHEN v.upload_date ~ '^\d{4}-\d{2}-\d{2}$' THEN v.upload_date::date::timestamp END,
        v.cached_at,
        NOW()
    ) AS event_at
FROM internal_video_cache v
JOIN internal_creator_group_members m ON m.username = v.username
JOIN internal_creator_groups g        ON g.id = m.group_id AND g.kind = 'booked_by'
LEFT JOIN sound_tags st               ON st.sound_key = LOWER(TRIM(COALESCE(v.song,'') || '|' || COALESCE(v.artist,'')))
ON CONFLICT (video_id, operator_slug) DO NOTHING;

-- ---- Slingshot edges (second op within 72h of first) -----------
INSERT INTO slingshot_edges (sound_key, first_op, second_op, first_at, second_at, bonus_xp)
SELECT DISTINCT ON (e1.sound_key, e1.operator_slug, e2.operator_slug)
    e1.sound_key,
    e1.operator_slug AS first_op,
    e2.operator_slug AS second_op,
    e1.event_at      AS first_at,
    e2.event_at      AS second_at,
    GREATEST(25, CAST(e2.base_xp * 0.5 AS INT)) AS bonus_xp
FROM xp_events e1
JOIN xp_events e2
  ON e2.sound_key      = e1.sound_key
 AND e2.operator_slug <> e1.operator_slug
 AND e2.event_at       > e1.event_at
 AND e2.event_at       < e1.event_at + INTERVAL '72 hours'
WHERE e1.sound_key IS NOT NULL AND e1.sound_key <> '|'
ORDER BY e1.sound_key, e1.operator_slug, e2.operator_slug, e1.event_at, e2.event_at
ON CONFLICT (sound_key, first_op, second_op) DO NOTHING;

-- ---- Captain leagues (weekly) ----------------------------------
INSERT INTO captain_leagues (operator_slug, week_start, league, xp, rank_in_league)
SELECT
    operator_slug,
    week_start,
    CASE WHEN xp >= 1500 THEN 'obsidian'
         WHEN xp >=  500 THEN 'gold'
         WHEN xp >=  150 THEN 'silver'
         ELSE                 'bronze' END AS league,
    xp,
    ROW_NUMBER() OVER (PARTITION BY week_start ORDER BY xp DESC) AS rank_in_league
FROM (
    SELECT
        operator_slug,
        DATE_TRUNC('week', event_at)::date AS week_start,
        SUM(xp) AS xp
    FROM xp_events
    GROUP BY operator_slug, DATE_TRUNC('week', event_at)
) w
ON CONFLICT (operator_slug, week_start) DO UPDATE
   SET league=EXCLUDED.league, xp=EXCLUDED.xp, rank_in_league=EXCLUDED.rank_in_league;

-- ---- Tide log (daily fleet-wide pulse) -------------------------
INSERT INTO tide_log (day, total_xp, rolling_7d, status, event_count)
SELECT
    day,
    total_xp,
    SUM(total_xp) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)::INT AS rolling_7d,
    CASE WHEN total_xp > 500 THEN 'green'
         WHEN total_xp > 100 THEN 'yellow'
         ELSE                      'red' END AS status,
    event_count
FROM (
    SELECT DATE(event_at) AS day, SUM(xp)::INT AS total_xp, COUNT(*)::INT AS event_count
    FROM xp_events
    GROUP BY DATE(event_at)
) d
ON CONFLICT (day) DO UPDATE
   SET total_xp    = EXCLUDED.total_xp,
       rolling_7d  = EXCLUDED.rolling_7d,
       status      = EXCLUDED.status,
       event_count = EXCLUDED.event_count;

COMMIT;
