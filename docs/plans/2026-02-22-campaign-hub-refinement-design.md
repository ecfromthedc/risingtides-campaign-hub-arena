# Campaign Hub Refinement -- Design Document

Date: 2026-02-22
Status: Approved
Approach: Incremental Migration (API-First)

---

## Overview

Migrate the Rising Tides Campaign Hub from a Flask/Jinja server-rendered app to a React frontend + Flask API backend architecture. Add Cobrand integration for live campaign performance tracking and a Notion webhook for automated campaign creation from the CRM.

## System Architecture

### Source of Truth Map

| System | Owns | Data |
|---|---|---|
| Notion CRM | Client relationships | Client name, artist, song, campaign booking, contract terms |
| Campaign Hub | Creator operations | Creator roster, rates, posts owed, payment status, PayPal, budget allocation |
| Cobrand | Post performance | Real-time tracking of submitted links -- views, engagement, submission counts |

### Data Flow

```
Notion CRM (client books campaign)
  |
  v  webhook (new entry)
Campaign Hub (creates blank campaign shell)
  |
  +--- Slack Agent --> Inbox --> Jake approves --> Creator added to roster
  |
  +--- Scraper finds posts matching campaign sound --> Links collected
  |
  +--- One-click: copy links + open Cobrand upload
  |
  v  manually enter Cobrand tracking URL
Campaign Hub <-- Cobrand tracking link (live stats feed back in)
```

---

## Phase 1 Scope

1. React frontend (Vite + TypeScript + shadcn/ui + Tailwind) deployed on Vercel
2. Flask API refactored into blueprints, deployed on Railway with Railway Postgres
3. Cobrand integration -- pull live performance stats from tracking share URLs
4. Notion webhook endpoint -- accept new campaigns from CRM
5. Sortable/filterable tables across all views (TanStack Table)
6. Mobile-responsive layout

### Not in Scope

- Automated Cobrand campaign creation
- Automated link submission to Cobrand
- Advanced analytics dashboards
- Multi-user authentication

---

## Backend Design

### Architecture: Flask API (JSON only, no templates)

```
campaign_manager/
  __init__.py          # App factory (create_app)
  config.py            # Config from env vars (DATABASE_URL, CORS origins, etc.)
  db.py                # Database layer (keep existing, already clean)
  models.py            # SQLAlchemy models (keep existing, already clean)
  blueprints/
    campaigns.py       # /api/campaigns, /api/campaign/<slug>/*
    internal.py        # /api/internal/*
    inbox.py           # /api/inbox/*
    webhooks.py        # /api/webhooks/notion
    health.py          # /health
  services/
    cobrand.py         # Fetch + parse Cobrand share page data
    scraping.py        # Sound ID extraction, URL resolution
    matching.py        # Sound matching logic
  utils/
    budget.py          # Budget/stats calculations
    helpers.py         # slugify, date parsing, etc.
```

### Key Changes

- All routes return JSON (remove all render_template calls)
- Add Flask-CORS for cross-origin requests from Vercel frontend
- Move ~200 lines of helper functions from web_dashboard.py into services/ and utils/
- Background scrape status: in-memory store (upgrade to Redis if needed later)
- Existing /api/* endpoints stay largely the same

### New Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| /api/webhooks/notion | POST | Accept new campaign from Notion CRM webhook |
| /api/campaign/<slug>/cobrand | GET | Fetch live stats from Cobrand tracking URL |
| /api/campaign/<slug>/cobrand | PUT | Set/update Cobrand share URL and upload URL for a campaign |
| /api/campaign/<slug>/archive | POST | Archive/complete a campaign |
| /api/internal/creators | GET | List internal creators (API version) |
| /api/internal/creators | POST | Add internal creators (API version) |
| /api/internal/creators/<username> | DELETE | Remove internal creator (API version) |
| /api/internal/scrape | POST | Trigger internal scrape (API version) |
| /api/internal/scrape/status | GET | Poll scrape progress (already exists) |
| /api/internal/results | GET | Get latest internal scrape results |
| /api/internal/creator/<username> | GET | Get creator detail with cached videos |

### Cobrand Integration Service

```python
# services/cobrand.py

def fetch_cobrand_stats(share_url: str) -> dict:
    """
    Fetch the share page HTML, parse __NEXT_DATA__ JSON,
    extract and return only performance fields.
    """
    # GET the share page
    # Parse <script id="__NEXT_DATA__"> from HTML
    # Extract promotion object
    # Return filtered fields (performance only, no financial)
```

#### Fields Consumed from Cobrand

INCLUDE (performance/metadata):
- promotion.id, promotion.name, promotion.status
- promotion.live_submission_count, draft_submission_count, comment_count
- promotion.activation_count, created_at
- activations[].artist.name, artist.image_url
- activations[].segment.social_sounds[] (sound IDs, platform, title)
- activations[].name, created_at, tags
- activations[].draft_submission_due_at, final_submission_due_at

EXCLUDE (financial -- Campaign Hub is source of truth):
- promotion.budget, total_campaign_budget, spend, spend_committed
- activations[].budget, spend, spend_committed
- budget_currency fields

EXCLUDE (internal/auth):
- owner_auth0_user (auth0 IDs, email)
- organization internal IDs
- whitelabel config fields
- token (stored separately, never exposed to frontend)

### Notion CRM Integration

#### CRM Database

- Database ID: `1961465b-b829-80c9-a1b5-c4cb3284149a`
- Workspace: Rising Tides Ent
- Integration: "Rising Tides AI" bot (internal integration)

#### CRM Schema -> Campaign Hub Mapping

| Notion Field | Type | Maps To | Notes |
|---|---|---|---|
| Artist Name | title | campaign.artist | Primary identifier |
| Song Name | rich_text | campaign.song | Combined with artist for title |
| TikTok Sound Link | url | campaign.official_sound -> extract sound_id | Existing extraction logic handles URLs, short links, video URLs |
| Insta Sound Link | url | campaign.insta_sound (new) | Instagram sound URL |
| Co Brand Link | url | campaign.cobrand_share_url | Auto-link Cobrand when available |
| Desired Start Date | date | campaign.start_date | |
| Media Spend | number | campaign.budget | Can be null for early-stage leads |
| Pipeline Status | status | webhook trigger | Fire when status = "Client" |
| Campaign Stage | status | campaign.campaign_stage (new) | Lead/Signed/Onboard/Started Reachout/Posts live/Posts finished/Report/Done |
| Round | select | campaign.round (new) | Round 1-5 for multi-round campaigns |
| Label/Distro Partner | rich_text | campaign.label (new) | Warner, Atlantic, DistroKid, etc. |
| Project Lead | multi_select | campaign.project_lead (new) | EC, Seeno, Dan, Emily |
| Key Contact Email | email | campaign.client_email (new) | |
| TikTok % | multi_select | campaign.platform_split (new JSONB) | Platform allocation percentages |
| Instagram % | multi_select | campaign.platform_split (new JSONB) | |
| Types of Content Creators | multi_select | campaign.content_types (new JSONB) | POV, Trucktok, NatureTok, etc. |

Fields NOT mapped (stay in Notion only): Your Name, Your Role, Notes/Thoughts to help Emily, Song Lyrics, If Other, Text, Anything else

#### Webhook Endpoint

```
POST /api/webhooks/notion

Trigger: Pipeline Status changes to "Client" (deal closed)

Accepts (from Notion webhook or n8n/Make.com automation):
{
  "notion_page_id": "3071465b-b829-8138-9e8f-df5eb317951d",
  "artist": "Mike Posner",
  "song": "I Took A Pill in Ibiza",
  "tiktok_sound_link": "https://www.tiktok.com/music/-7607445596362885137",
  "insta_sound_link": "https://www.instagram.com/reels/audio/...",
  "cobrand_link": "",
  "start_date": "2026-02-20",
  "budget": 2500,
  "label": "Warner",
  "round": "Round 1",
  "project_lead": ["EC (Eric)"],
  "content_types": ["Everything Welcome"],
  "platform_split": {"tiktok": 100, "instagram": 0},
  "client_email": "contact@label.com"
}

Creates:
- Campaign with all metadata populated from CRM
- Sound ID auto-extracted from tiktok_sound_link
- Status: "queued" (awaiting creator bookings via Slack inbox)
- No creators yet (those flow in via Slack agent -> Inbox -> Jake approves)
- Cobrand link attached if already available
```

#### Notion Webhook Approach

Notion doesn't support native outbound webhooks. Options:
1. **n8n/Make.com automation** -- watch the Notion database for Pipeline Status = "Client", POST to Campaign Hub webhook endpoint
2. **Polling** -- Campaign Hub periodically queries Notion API for new "Client" entries (simpler, no external tool needed, slight delay)
3. **Manual trigger** -- Button in Notion or Campaign Hub to sync a specific entry

Recommendation: Start with option 2 (polling) since it requires no additional infrastructure. A background task every 5 minutes queries Notion for entries with Pipeline Status = "Client" that haven't been synced yet. Mark synced entries by storing the notion_page_id in the Campaign model.

### Database Model Changes

Add to Campaign model:
- cobrand_share_url (Text) -- the tracking/share URL with token
- cobrand_upload_url (Text) -- the upload URL for one-click workflow
- cobrand_promotion_id (String) -- Cobrand's promotion UUID
- cobrand_last_sync (DateTime) -- last time we pulled Cobrand stats
- cobrand_live_submissions (Integer) -- cached submission count
- cobrand_comments (Integer) -- cached comment count
- cobrand_status (String) -- Cobrand campaign status
- source (String, default="manual") -- how campaign was created (manual, notion, slack)
- notion_page_id (String, nullable) -- link back to Notion CRM entry
- insta_sound (Text) -- Instagram sound URL
- campaign_stage (String) -- mirrors Notion's Campaign Stage status
- round (String) -- Round 1-5
- label (String) -- Label/Distro partner name
- project_lead (JSONB) -- list of assigned leads
- client_email (String) -- key contact email
- platform_split (JSONB) -- {"tiktok": 100, "instagram": 0}
- content_types (JSONB) -- list of desired content creator types

---

## Frontend Design

### Stack

- Vite + React + TypeScript
- shadcn/ui component library
- Tailwind CSS for styling
- TanStack Table for sortable/filterable data tables
- TanStack Query (React Query) for API data fetching + caching
- React Router for navigation
- Deployed on Vercel

### Pages (mirror existing UI)

1. **Campaigns List** (`/`)
   - Sortable table: title, artist, status, budget, views, live posts, CPM
   - Search/filter bar
   - "New Campaign" form (modal or expandable)
   - Campaign status badges

2. **Campaign Detail** (`/campaign/:slug`)
   - Campaign header with edit mode (inline editing)
   - Stat cards: budget, paid, live posts, total views, CPM
   - Cobrand stats section (live submissions, comments, engagement) -- NEW
   - Creator roster table (sortable by any column)
   - Add creator form
   - Cobrand upload section (iframe + link clipboard)
   - Cobrand tracking link configuration -- NEW

3. **Internal TikTok** (`/internal`)
   - Creator list sidebar (sticky)
   - Add/remove creators
   - Scrape trigger with real-time progress (no page refresh)
   - Songs results table (sortable by views, video count)
   - Copy-links workflow

4. **Internal Creator Detail** (`/internal/:username`)
   - Per-creator video cache
   - Songs grouped and sorted

5. **Slack Inbox** (`/inbox`)
   - Pending items with editable creator fields
   - Campaign selector dropdown
   - Approve/dismiss actions (no page refresh)
   - Approved/dismissed history

### Design Principles

- Mirror existing visual design (colors, layout, typography)
- Sidebar navigation (same structure as current)
- All interactions happen without full page refreshes
- Scrape progress shown via polling + progress bar (already exists, just moves client-side)
- Mobile: sidebar collapses to hamburger menu, tables become card layouts
- Loading states and error handling on all API calls

### API Communication

- React Query for all data fetching with automatic refetching
- Optimistic updates for quick actions (toggle paid, approve inbox)
- Polling for scrape status (2-second interval during active scrapes)
- Cobrand stats fetched on-demand when viewing a campaign (cached for 5 minutes)

---

## Deployment

### Railway (Backend)

- Same Dockerfile, updated CMD (no more template serving)
- Environment vars: DATABASE_URL, CORS_ORIGINS (Vercel URL), SECRET_KEY
- Railway Postgres (already provisioned)
- Health check at /health (already exists)

### Vercel (Frontend)

- Vite build output served as static site
- Environment var: VITE_API_URL pointing to Railway backend URL
- Automatic deploys from git

### CORS Configuration

- Flask-CORS configured to allow Vercel domain
- API key header not required (no auth for now)
- Can add auth layer later without changing architecture

---

## Migration Strategy

1. Build React frontend that consumes existing /api/* endpoints
2. Refactor Flask into blueprints + add new endpoints
3. Add Cobrand integration service
4. Add Notion webhook endpoint
5. Deploy backend update to Railway
6. Deploy frontend to Vercel
7. Verify everything works end-to-end
8. Remove Jinja templates and template-serving routes from Flask
