# Campaign Hub

> **MIGRATION IN PROGRESS.** The codebase is transitioning from a monolithic Flask/Jinja server-rendered app to a React frontend + Flask API architecture. What you see in the code RIGHT NOW does not match the target architecture described below. The current state is a single ~1,900-line `web_dashboard.py` serving Jinja HTML templates with inline CSS. Read `docs/plans/2026-02-22-campaign-hub-refinement-design.md` after finishing this document for the full migration plan and implementation details.

## What This Is

Internal campaign management platform for Rising Tides -- a social media marketing agency running TikTok/Instagram UGC influencer campaigns for major record labels. This app is where we stage campaigns, book creators, scrape for post links, track budgets/payments, and pull live performance data from Cobrand.

## Current State (Pre-Migration)

- **Monolithic Flask app** -- all routes, helpers, and scraping logic in `campaign_manager/web_dashboard.py` (~1,900 lines)
- **Server-rendered Jinja templates** -- 6 HTML templates in `campaign_manager/templates/` with inline CSS
- **No frontend framework** -- vanilla JS for interactivity (toggle paid, approve inbox, scrape polling)
- **Deployed on Railway** -- Flask + gunicorn serving both HTML pages and JSON API endpoints
- **Railway Postgres** -- SQLAlchemy with file-based fallback for local dev
- **Working features:** Campaign CRUD, creator management, TikTok scraping via yt-dlp, sound matching, budget tracking, Slack inbox integration, internal creator monitoring, Cobrand upload iframe embed

## Target Architecture (Post-Migration)

**Frontend:** Vite + React + TypeScript + shadcn/ui + Tailwind (deployed on Vercel)
**Backend:** Flask API (Python) + SQLAlchemy + PostgreSQL (deployed on Railway)
**Integrations:** Cobrand (live post tracking), Notion CRM (campaign intake via webhook), Slack (booking intake via agent)

### Source of Truth Boundaries

| System | Owns |
|---|---|
| Notion CRM | Client relationships, campaign bookings (client paying us) |
| Campaign Hub (this app) | Creator roster, rates, posts owed, payments, budget allocation, scraping |
| Cobrand | Real-time post performance (views, engagement, submission counts) |

Financial data lives here. Performance data comes from Cobrand. Client data comes from Notion. Do not duplicate sources of truth.

## Project Structure

### Current (pre-migration)

```
risingtides-campaign-hub/
  campaign_manager/
    __init__.py
    db.py                    # Database access layer (clean, keep as-is)
    models.py                # SQLAlchemy models (clean, keep as-is)
    web_dashboard.py         # ALL routes + helpers + scraping in one file (~1,900 lines)
    templates/               # Jinja HTML templates (6 files, inline CSS)
  src/
    scrapers/
      master_tracker.py      # Parallel TikTok scraping + sound matching
      scrape_external_accounts_cached.py
    utils/
      get_post_links_by_song.py  # Internal creator scraping
  Dockerfile                 # Railway deployment config
  requirements.txt           # Python dependencies
```

### Target (post-migration)

```
risingtides-campaign-hub/
  campaign_manager/          # Flask backend (API only)
    __init__.py              # App factory
    config.py                # Environment config
    db.py                    # Database access layer (keep existing)
    models.py                # SQLAlchemy models (keep existing + new Cobrand fields)
    blueprints/              # API route modules
      campaigns.py           # /api/campaigns, /api/campaign/<slug>/*
      internal.py            # /api/internal/*
      inbox.py               # /api/inbox/*
      webhooks.py            # /api/webhooks/notion
      health.py              # /health
    services/
      cobrand.py             # Fetch + parse Cobrand share page stats
      scraping.py            # Sound ID extraction, URL resolution
      matching.py            # Sound matching logic
    utils/
      budget.py              # Budget/stats calculations
      helpers.py             # slugify, date parsing, etc.
  src/
    scrapers/                # TikTok/Instagram scraping (keep existing)
      master_tracker.py
      scrape_external_accounts_cached.py
    utils/
      get_post_links_by_song.py
  frontend/                  # React app (Vite) -- NEW
    src/
      components/            # shadcn/ui + custom components
      pages/                 # Route pages
      api/                   # API client (React Query hooks)
      lib/                   # Utilities
  docs/
    plans/                   # Design docs and implementation plans
  Dockerfile                 # Backend Docker image for Railway
```

## Data Flow

```
Notion CRM (client books)
  |  webhook
  v
Campaign Hub (blank campaign created)
  |
  +-- Slack Agent --> Inbox --> Jake approves --> Creators added
  |
  +-- Scraper finds posts using sound --> Links collected
  |
  +-- One-click: copy links + open Cobrand upload page
  |
  v  enter Cobrand tracking URL into campaign
Campaign Hub <-- Cobrand (live performance stats)
```

## Key Technical Decisions

- **Cobrand integration parses `__NEXT_DATA__` from share page HTML.** No official API -- we scrape the Next.js server-rendered JSON payload. We only consume performance fields (submissions, comments, engagement), never financial fields (budget, spend).
- **Cobrand share URLs contain auth tokens.** Store the full URL in the database but never expose the token to the frontend beyond what's needed for the iframe embed.
- **Scraping runs in background threads.** Both campaign refresh and internal scrape use ThreadPoolExecutor. Status is polled via /api endpoints. Not ideal long-term but functional. Redis + Celery is the upgrade path if needed.
- **Dual storage mode.** The db.py layer supports both Postgres (production) and file-based JSON/CSV (local dev without a database). The `USE_DB` flag controls this. Production always uses Postgres.

## Environment Variables

| Variable | Where | Purpose |
|---|---|---|
| DATABASE_URL | Railway | PostgreSQL connection string |
| SECRET_KEY | Railway | Flask session secret |
| CORS_ORIGINS | Railway | Allowed frontend origins (Vercel URL) |
| PORT | Railway | Auto-set by Railway |
| VITE_API_URL | Vercel | Backend API URL for React app |

## Development Guidelines

- Backend is pure JSON API. No HTML templates, no Jinja rendering.
- Frontend mirrors the existing UI design (colors, layout, typography from the original Jinja templates). Don't redesign -- replicate and enhance.
- All tables use TanStack Table for sorting/filtering.
- All API calls use React Query with proper loading/error states.
- No full page refreshes for user actions (optimistic updates where possible).
- Mobile layout: sidebar collapses to hamburger, tables become card layouts.

## What NOT To Do

- Don't put financial/budget data in Cobrand sync. This app tracks money.
- Don't scrape TikTok for view counts on existing posts. Cobrand handles that.
- Don't add auth yet. Internal tool, small team, no auth for Phase 1.
- Don't over-engineer the scraping infrastructure. Threads + polling works. Move to task queues only when it breaks.
