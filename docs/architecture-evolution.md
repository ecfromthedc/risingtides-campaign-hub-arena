# Campaign Hub -- Architecture Evolution

> **Date:** 2026-02-23
> **Author:** John (Risingtides-dev) + Claude
> **Purpose:** Document what Jake built, what we changed, and why

---

## Part 1: What Jake Built

### Overview

Jake built a working campaign management dashboard as a monolithic Flask application. Server-rendered HTML with Jinja templates, inline CSS, and vanilla JavaScript for interactivity. Single Python file for all routes (~1,900 lines). Deployed on Railway with Postgres.

### Original Architecture

```
┌─────────────────────────────────────────────────────┐
│                    BROWSER                          │
│                                                     │
│  User requests page → Server returns full HTML      │
│  User clicks button → Full page reload              │
│  User submits form  → POST, redirect, reload        │
│                                                     │
└───────────────────────┬─────────────────────────────┘
                        │ HTTP (HTML + JSON)
                        ▼
┌─────────────────────────────────────────────────────┐
│              Flask App (web_dashboard.py)            │
│              ~1,900 lines, single file              │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │ HTML Routes  │  │  API Routes  │  │  Helpers  │  │
│  │ (Jinja)     │  │  (/api/*)    │  │           │  │
│  │             │  │              │  │ slugify   │  │
│  │ GET /       │  │ GET /api/    │  │ calc_budget│  │
│  │ GET /camp.. │  │   campaigns  │  │ extract_  │  │
│  │ POST /camp..│  │ GET /api/    │  │  sound_id │  │
│  │ GET /intern │  │   campaign/  │  │ load_json │  │
│  │ GET /inbox  │  │ POST /api/   │  │ save_json │  │
│  │             │  │   inbox      │  │ etc...    │  │
│  └─────────────┘  └──────────────┘  └───────────┘  │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │           Scraping Logic                     │    │
│  │  - TikTok scraping (yt-dlp)                 │    │
│  │  - Sound ID extraction (HTML parsing)        │    │
│  │  - Parallel account scraping (ThreadPool)    │    │
│  │  - Sound matching (fuzzy + exact)            │    │
│  │  - Background thread for internal scrapes    │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─────────────┐  ┌──────────────────────────┐      │
│  │  6 Jinja    │  │  Dual Storage Mode       │      │
│  │  Templates  │  │                          │      │
│  │             │  │  if DATABASE_URL:         │      │
│  │  base.html  │  │    → Postgres (SQLAlchemy)│      │
│  │  index.html │  │  else:                   │      │
│  │  campaign_  │  │    → JSON/CSV files      │      │
│  │   detail    │  │                          │      │
│  │  inbox.html │  │  Models:                 │      │
│  │  internal   │  │  - Campaign              │      │
│  │  internal_  │  │  - Creator               │      │
│  │   creator   │  │  - MatchedVideo          │      │
│  │  campaign_  │  │  - ScrapeLog             │      │
│  │   links     │  │  - InboxItem             │      │
│  └─────────────┘  │  - PaypalMemory          │      │
│                    │  - InternalCreator       │      │
│                    │  - InternalVideoCache    │      │
│                    │  - InternalScrapeResult  │      │
│                    └──────────────────────────┘      │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│              Railway Postgres                       │
│              (or local JSON/CSV files)              │
└─────────────────────────────────────────────────────┘
```

### What Worked Well

**Functional completeness.** Jake built a real, working tool that his team used daily:

- **Campaign CRUD** -- create campaigns with artist/song/sound ID/budget, edit inline, search
- **Creator management** -- add/edit/remove creators, track posts owed vs done, PayPal memory auto-fill, toggle paid status
- **TikTok scraping** -- parallel account scraping via yt-dlp, sound ID extraction from HTML, fuzzy song matching with multiple strategies (exact ID, song+artist key, core word overlap)
- **Budget tracking** -- real-time budget calculations (booked, paid, remaining, % used, CPM)
- **Slack inbox** -- API endpoint for an AI agent to POST booking recommendations, Jake approves/dismisses in the UI
- **Internal TikTok** -- monitor a roster of internal creators, background scraping with progress polling, group results by song
- **Cobrand integration** -- iframe embed of Cobrand upload page, copy-paste workflow for links
- **Dual storage** -- works with Postgres in production or flat files locally

**The scraping logic is particularly well-engineered:**
- Multiple sound ID extraction strategies (URL parsing, HTML scraping, short URL resolution)
- Fuzzy matching with core song name normalization (strips "feat.", "Promo", "Remix")
- Parallel scraping with ThreadPoolExecutor (5 workers for campaigns, 8 for internal)
- 30-day rolling video cache per internal creator
- Retry logic with fallback

### What Needed Improvement

| Issue | Impact |
|---|---|
| **Single 1,900-line file** | Hard to navigate, impossible to work on specific features without context-loading the whole thing |
| **Server-rendered HTML** | Every action = full page reload. Toggle a paid checkbox? Reload. Add a creator? Reload. |
| **No sortable tables** | Can't sort campaigns by views, budget, or CPM. Can't sort creators by rate or posts. |
| **No mobile layout** | Fixed 220px sidebar + wide tables = unusable on phones |
| **Mixed HTML + API routes** | Same endpoints serve both Jinja templates and JSON, leading to inconsistent response patterns |
| **Inline CSS in templates** | ~250 lines of CSS in base.html, no design system, no reusable components |
| **No Cobrand data integration** | Cobrand iframe for uploading links, but no live stats pulled back in |
| **No CRM connection** | Campaigns created manually, no link to Notion CRM where clients are tracked |
| **No creator database** | Creators exist per-campaign only -- no way to see a creator's full history across campaigns |

---

## Part 2: What We Built

### New Architecture

```
┌─────────────────────────────────────────────────────┐
│                    BROWSER                          │
│                                                     │
│  React SPA (Vite + TypeScript)                      │
│  Client-side routing (React Router)                 │
│  State management (React Query)                     │
│  No page reloads -- all interactions are instant    │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  Pages (7)                                   │    │
│  │                                              │    │
│  │  / ................. CampaignsList           │    │
│  │  /campaign/:slug ... CampaignDetail          │    │
│  │  /creators ......... CreatorDatabase  [NEW]  │    │
│  │  /creators/:user ... CreatorProfile   [NEW]  │    │
│  │  /internal ......... InternalTikTok          │    │
│  │  /internal/:user ... InternalCreatorDetail   │    │
│  │  /inbox ............ SlackInbox              │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  UI Layer                                    │    │
│  │                                              │    │
│  │  shadcn/ui components (table, button, card,  │    │
│  │  badge, dialog, select, input, tabs, etc.)   │    │
│  │                                              │    │
│  │  TanStack Table (sortable/filterable)        │    │
│  │  Tailwind CSS (responsive, mobile-first)     │    │
│  │  Lucide icons                                │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  Data Layer                                  │    │
│  │                                              │    │
│  │  API client (api.ts) -- 24 endpoint fns      │    │
│  │  React Query hooks (queries.ts) -- 24 hooks  │    │
│  │  TypeScript types (types.ts) -- 19 interfaces│    │
│  │  Auto-refetch, cache invalidation, polling   │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
└───────────────────────┬─────────────────────────────┘
                        │ JSON API (CORS)
                        ▼
┌─────────────────────────────────────────────────────┐
│              Flask API (Railway)                    │
│              29 endpoints, JSON only                │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  Blueprints (5 modules)                      │   │
│  │                                              │   │
│  │  campaigns.py ─── Campaign CRUD, creators,   │   │
│  │                    budget, search, links,     │   │
│  │                    scrape refresh,            │   │
│  │                    creator database [NEW]     │   │
│  │                                              │   │
│  │  internal.py ──── Internal creator mgmt,     │   │
│  │                    scrape trigger/status,     │   │
│  │                    results, creator detail    │   │
│  │                                              │   │
│  │  inbox.py ─────── Slack intake, approve,     │   │
│  │                    dismiss, campaign suggest  │   │
│  │                                              │   │
│  │  webhooks.py ──── Notion webhook [NEW],      │   │
│  │                    Notion CRM sync [NEW]      │   │
│  │                                              │   │
│  │  health.py ────── Health check               │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  Services (2 new modules)                    │   │
│  │                                              │   │
│  │  cobrand.py ──── Fetch __NEXT_DATA__ from    │   │
│  │  [NEW]           Cobrand share pages,        │   │
│  │                  extract performance stats    │   │
│  │                                              │   │
│  │  notion.py ───── Query Notion CRM for new    │   │
│  │  [NEW]           "Client" entries, map to    │   │
│  │                  campaign data structure      │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  Utils (extracted from web_dashboard.py)     │   │
│  │                                              │   │
│  │  helpers.py ──── slugify, extract_sound_id,  │   │
│  │                  TikTok URL resolution,       │   │
│  │                  sound ID from HTML, etc.     │   │
│  │                                              │   │
│  │  budget.py ───── calc_budget, calc_stats     │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  Models (extended)                           │   │
│  │                                              │   │
│  │  Original 9 models preserved                 │   │
│  │  + 17 new fields on Campaign:                │   │
│  │    Cobrand (7): share_url, upload_url,       │   │
│  │      promotion_id, last_sync, live_subs,     │   │
│  │      comments, status                        │   │
│  │    Notion (2): notion_page_id, source        │   │
│  │    CRM (8): insta_sound, campaign_stage,     │   │
│  │      round, label, project_lead, client_     │   │
│  │      email, platform_split, content_types    │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  Scraping (unchanged from Jake's build)      │   │
│  │                                              │   │
│  │  master_tracker.py -- parallel TikTok        │   │
│  │  scraping, sound matching, yt-dlp            │   │
│  │                                              │   │
│  │  get_post_links_by_song.py -- internal       │   │
│  │  creator scraping                            │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│              Railway Postgres                       │
│              9 tables + 17 new columns              │
└─────────────────────────────────────────────────────┘
```

### External System Integration (New)

```
┌──────────────┐         ┌──────────────────────┐         ┌──────────────┐
│  Notion CRM  │         │    Campaign Hub       │         │   Cobrand    │
│              │         │                       │         │              │
│  Client      │ poll/   │  Campaigns            │ scrape  │  Promotions  │
│  bookings    │ webhook │  Creators             │ parse   │  Submissions │
│  Artist info │────────▶│  Budgets              │◀────────│  Comments    │
│  Sound links │         │  Matched videos       │         │  Engagement  │
│  Labels      │         │  Payment tracking     │         │  Sound IDs   │
│              │         │                       │         │              │
└──────────────┘         └───────────┬───────────┘         └──────────────┘
                                     │
                              ┌──────┴──────┐
                              ▼             ▼
                    ┌──────────────┐  ┌──────────────┐
                    │  Slack Agent │  │   TikTok     │
                    │              │  │              │
                    │  Parses      │  │  yt-dlp      │
                    │  booking     │  │  scraping    │
                    │  channel     │  │  Sound ID    │
                    │  Stages for  │  │  extraction  │
                    │  approval    │  │              │
                    └──────────────┘  └──────────────┘
```

---

## Part 3: Before vs After Comparison

### Feature Comparison

| Feature | Jake's Build | After Migration |
|---|---|---|
| **Rendering** | Server-side (Jinja) | Client-side (React SPA) |
| **Page transitions** | Full page reload | Instant (React Router) |
| **Form submissions** | POST → redirect → reload | JSON API → update in place |
| **Table sorting** | None | All tables sortable by any column |
| **Mobile support** | None (fixed 220px sidebar) | Responsive (hamburger menu, scroll tables) |
| **Campaign CRUD** | Working | Working (same logic, better UX) |
| **Creator management** | Working | Working + cross-campaign database |
| **Creator database** | None | Full roster with aggregated stats |
| **Creator profiles** | None | Per-creator history, stats, all campaigns |
| **Budget tracking** | Working | Working (same calculations) |
| **TikTok scraping** | Working | Working (same code, untouched) |
| **Sound matching** | Working | Working (same logic, extracted to utils) |
| **Internal TikTok** | Working | Working (real-time progress, no reload) |
| **Slack inbox** | Working | Working (approve/dismiss without reload) |
| **Cobrand upload** | Iframe embed only | Iframe + live stats from tracking page |
| **Cobrand stats** | None | Live submission count, comments, engagement |
| **Notion CRM sync** | None | Webhook + polling for new Client entries |
| **Paid toggle** | Checkbox + page reload | Instant checkbox toggle |
| **Search** | Server-side filter | Client-side filter (instant) |
| **API** | Mixed HTML + JSON routes | Pure JSON API (29 endpoints) |
| **Code organization** | 1 file (1,900 lines) | 5 blueprints + 2 services + 2 utils |
| **Type safety** | None | Full TypeScript (19 interfaces) |
| **Data fetching** | Manual fetch calls | React Query (caching, auto-refetch) |

### Code Size Comparison

| Component | Jake's Build | After Migration |
|---|---|---|
| Backend routes | 1,900 lines (1 file) | ~2,300 lines (5 blueprint files) |
| Backend services | 0 | ~330 lines (cobrand.py + notion.py) |
| Backend utils | (inline in routes) | ~195 lines (helpers.py + budget.py) |
| Frontend | 0 (Jinja templates) | ~4,500 lines (React components + pages) |
| Templates/UI | ~900 lines (6 Jinja files) | Replaced by React components |
| Types | 0 | ~270 lines (TypeScript interfaces) |
| API client | 0 | ~500 lines (api.ts + queries.ts) |
| **Total new code** | | **~8,100 lines** |

### What We Preserved (Jake's Code We Didn't Touch)

- `src/scrapers/master_tracker.py` -- all scraping logic, parallel processing, sound matching
- `src/scrapers/scrape_external_accounts_cached.py` -- cached scraping
- `src/utils/get_post_links_by_song.py` -- internal creator scraping
- `campaign_manager/db.py` -- database access layer (extended, not rewritten)
- `campaign_manager/models.py` -- all 9 SQLAlchemy models (extended, not rewritten)
- All business logic in route handlers (calc_budget, sound matching, inbox suggestion, etc.)

The scraping engine and data layer were already well-built. We extracted and reorganized the route logic but preserved every line of business logic.

---

## Part 4: Deployment Architecture

### Before (Jake's Setup)

```
┌─────────────────────────────────┐
│         Railway                  │
│                                  │
│  ┌────────────────────────────┐  │
│  │  Flask + Gunicorn          │  │
│  │  Serves HTML pages         │  │
│  │  Serves JSON API           │  │
│  │  Serves static CSS/JS      │  │
│  │  Everything in one process │  │
│  └─────────────┬──────────────┘  │
│                │                 │
│  ┌─────────────▼──────────────┐  │
│  │  PostgreSQL                │  │
│  └────────────────────────────┘  │
└──────────────────────────────────┘
```

### After (Current Setup)

```
┌──────────────────┐     CORS      ┌──────────────────┐
│     Vercel       │◀─────────────▶│     Railway      │
│                  │   JSON API     │                  │
│  React SPA       │               │  Flask API       │
│  Static files    │               │  Gunicorn        │
│  CDN cached      │               │  No HTML serving │
│  Auto-deploy     │               │  Auto-deploy     │
│  from GitHub     │               │  from GitHub     │
│                  │               │                  │
│  Edge network    │               │  ┌────────────┐  │
│  (global CDN)    │               │  │ PostgreSQL │  │
│                  │               │  └────────────┘  │
└──────────────────┘               └──────────────────┘

Frontend: risingtides-campaign-hub.vercel.app
Backend:  risingtides-campaign-hub-production.up.railway.app
Repo:     github.com/Risingtides-dev/risingtides-campaign-hub
```

### Benefits of Split Architecture

| Aspect | Before | After |
|---|---|---|
| **Frontend deploys** | Requires full backend redeploy | Independent, instant on Vercel |
| **Backend deploys** | Restarts break active sessions | Frontend unaffected, just API calls |
| **CDN** | No CDN (Railway serves HTML) | Vercel edge network (global CDN) |
| **Scaling** | Scale frontend = scale backend | Scale independently |
| **Development** | Change CSS → redeploy Python | Change React → hot reload instant |
| **Cost** | Railway serves everything | Vercel free tier for static, Railway only for API |

---

## Part 5: What's Next

### Immediate (Tomorrow)

1. **Data migration** -- Import 14 active campaigns from Jake's local disk into Railway Postgres
2. **Verify end-to-end** -- Team accesses Vercel URL, sees real campaign data, performs real operations

### Short Term

3. **Notion sync test** -- Trigger CRM sync, verify campaigns flow from Notion into the Hub
4. **Cobrand linking** -- Add tracking URLs to campaigns, verify live stats display
5. **Platform-aware social links** -- Creator profiles show TikTok/IG based on booking platform
6. **Legacy cleanup** -- Remove web_dashboard.py and Jinja templates

### Medium Term

7. **Automated Notion polling** -- Background task syncs CRM every 5 minutes instead of manual trigger
8. **Enhanced creator database** -- Creator tags, ratings, performance scores for booking decisions
9. **Campaign analytics** -- CPM trends, creator performance over time, budget utilization reports
10. **Authentication** -- Basic auth or Cloudflare Access when the team grows
