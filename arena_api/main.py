"""
Arena API — minimal read-only service powering the Arena Next.js UI.

Endpoints (all JSON):
  GET /health
  GET /api/tide               -> { status, rolling_7d, total_xp, last_7_days[] }
  GET /api/fleet              -> list of squads with their operators + XP
  GET /api/operators          -> list of operators with totals
  GET /api/operator/{slug}    -> single operator detail (xp, recent posts, slingshots)
  GET /api/slingshots         -> recent slingshot edges
  GET /api/league             -> current-week standings (bronze/silver/gold/obsidian)
  GET /api/events             -> recent XP events for the live feed
"""
import os
from datetime import datetime, date, timedelta

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL or DATABASE_PUBLIC_URL must be set")

app = FastAPI(title="Arena API", version="0.1.0")

# CORS wide open for v0 (Cloudflare Access gates at the edge)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def rows(sql: str, params=None):
    with db() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params or ())
        return [dict(r) for r in cur.fetchall()]


def one(sql: str, params=None):
    r = rows(sql, params)
    return r[0] if r else None


def _ser(v):
    """Recursively coerce datetimes/dates to iso strings for JSON."""
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _ser(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_ser(x) for x in v]
    return v


@app.get("/health")
def health():
    r = one("SELECT COUNT(*)::int AS ops FROM operators")
    return {"ok": True, "operators": r["ops"] if r else 0}


@app.get("/api/tide")
def tide():
    latest = one("SELECT day, total_xp, rolling_7d, status, event_count FROM tide_log ORDER BY day DESC LIMIT 1")
    last_7 = rows("SELECT day, total_xp, status, event_count FROM tide_log ORDER BY day DESC LIMIT 14")
    fleet_totals = one(
        """
        SELECT
          COALESCE(SUM(xp),0)::int AS all_time_xp,
          COUNT(DISTINCT operator_slug)::int AS active_ops
        FROM xp_events
        """
    )
    slingshot_totals = one("SELECT COUNT(*)::int AS total FROM slingshot_edges")
    return _ser({
        "today": latest,
        "last_14_days": list(reversed(last_7)),
        "all_time_xp": fleet_totals["all_time_xp"] if fleet_totals else 0,
        "active_operators": fleet_totals["active_ops"] if fleet_totals else 0,
        "slingshot_total": slingshot_totals["total"] if slingshot_totals else 0,
    })


@app.get("/api/fleet")
def fleet():
    squads = rows("SELECT id, slug, name, motto, color FROM squads ORDER BY id")
    for s in squads:
        s["operators"] = rows(
            """
            SELECT o.slug, o.display_name, o.tagline, o.color,
                   COALESCE(SUM(e.xp),0)::int AS total_xp,
                   COUNT(e.id)::int AS event_count,
                   MAX(e.event_at) AS last_event_at
            FROM operators o
            JOIN squad_members sm ON sm.operator_id = o.id AND sm.squad_id = %s
            LEFT JOIN xp_events e ON e.operator_slug = o.slug
            GROUP BY o.slug, o.display_name, o.tagline, o.color
            ORDER BY total_xp DESC
            """,
            (s["id"],),
        )
    return _ser(squads)


@app.get("/api/operators")
def operators():
    return _ser(rows(
        """
        SELECT o.slug, o.display_name, o.tagline, o.color,
               COALESCE(SUM(e.xp),0)::int AS total_xp,
               COUNT(e.id)::int AS event_count,
               MAX(e.event_at) AS last_event_at,
               (SELECT league FROM captain_leagues cl
                WHERE cl.operator_slug = o.slug
                ORDER BY week_start DESC LIMIT 1) AS current_league,
               (SELECT rank_in_league FROM captain_leagues cl
                WHERE cl.operator_slug = o.slug
                ORDER BY week_start DESC LIMIT 1) AS current_rank
        FROM operators o
        LEFT JOIN xp_events e ON e.operator_slug = o.slug
        GROUP BY o.slug, o.display_name, o.tagline, o.color
        ORDER BY total_xp DESC
        """
    ))


@app.get("/api/operator/{slug}")
def operator_detail(slug: str):
    op = one("SELECT slug, display_name, tagline, color FROM operators WHERE slug = %s", (slug,))
    if not op:
        raise HTTPException(404, "operator not found")
    totals = one(
        """
        SELECT COALESCE(SUM(xp),0)::int AS total_xp,
               COALESCE(SUM(CASE WHEN source_kind='client'  THEN xp ELSE 0 END),0)::int AS client_xp,
               COALESCE(SUM(CASE WHEN source_kind='catalog' THEN xp ELSE 0 END),0)::int AS catalog_xp,
               COUNT(*)::int AS post_count,
               COALESCE(SUM(views),0)::int AS total_views,
               MAX(event_at) AS last_post_at
        FROM xp_events WHERE operator_slug = %s
        """,
        (slug,),
    )
    recent_posts = rows(
        """
        SELECT video_url, username, source_kind, views, xp, event_at, sound_key
        FROM xp_events
        WHERE operator_slug = %s
        ORDER BY event_at DESC NULLS LAST
        LIMIT 20
        """,
        (slug,),
    )
    slingshots_as_slinger = rows(
        """
        SELECT se.sound_key, se.first_op, se.second_at, se.bonus_xp,
               o.display_name AS first_op_name
        FROM slingshot_edges se
        LEFT JOIN operators o ON o.slug = se.first_op
        WHERE se.second_op = %s
        ORDER BY second_at DESC NULLS LAST
        LIMIT 10
        """,
        (slug,),
    )
    slingshots_as_scout = rows(
        """
        SELECT se.sound_key, se.second_op, se.first_at, se.bonus_xp,
               o.display_name AS second_op_name
        FROM slingshot_edges se
        LEFT JOIN operators o ON o.slug = se.second_op
        WHERE se.first_op = %s
        ORDER BY first_at DESC NULLS LAST
        LIMIT 10
        """,
        (slug,),
    )
    league_history = rows(
        """
        SELECT week_start, league, xp, rank_in_league
        FROM captain_leagues
        WHERE operator_slug = %s
        ORDER BY week_start DESC
        LIMIT 8
        """,
        (slug,),
    )
    return _ser({
        "operator": op,
        "totals": totals,
        "recent_posts": recent_posts,
        "slingshots_received": slingshots_as_slinger,
        "slingshots_given": slingshots_as_scout,
        "league_history": league_history,
    })


@app.get("/api/slingshots")
def slingshots():
    return _ser(rows(
        """
        SELECT se.sound_key, se.first_op, se.second_op, se.first_at, se.second_at, se.bonus_xp,
               o1.display_name AS first_name, o2.display_name AS second_name
        FROM slingshot_edges se
        LEFT JOIN operators o1 ON o1.slug = se.first_op
        LEFT JOIN operators o2 ON o2.slug = se.second_op
        ORDER BY second_at DESC NULLS LAST
        LIMIT 50
        """
    ))


@app.get("/api/league")
def league():
    latest_week = one("SELECT MAX(week_start) AS w FROM captain_leagues")
    if not latest_week or not latest_week["w"]:
        return {"week_start": None, "standings": []}
    standings = rows(
        """
        SELECT cl.operator_slug, cl.league, cl.xp, cl.rank_in_league,
               o.display_name, o.color, o.tagline
        FROM captain_leagues cl
        JOIN operators o ON o.slug = cl.operator_slug
        WHERE cl.week_start = %s
        ORDER BY cl.xp DESC
        """,
        (latest_week["w"],),
    )
    return _ser({"week_start": latest_week["w"], "standings": standings})


@app.get("/api/events")
def events():
    return _ser(rows(
        """
        SELECT e.id, e.operator_slug, o.display_name AS operator_name,
               e.video_url, e.username, e.source_kind, e.views, e.xp, e.event_at, e.sound_key
        FROM xp_events e
        LEFT JOIN operators o ON o.slug = e.operator_slug
        ORDER BY event_at DESC NULLS LAST
        LIMIT 50
        """
    ))
