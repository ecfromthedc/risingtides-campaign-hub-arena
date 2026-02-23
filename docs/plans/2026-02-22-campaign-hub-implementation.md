# Campaign Hub Migration -- Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate Campaign Hub from Flask/Jinja monolith to React + Flask API architecture with Cobrand and Notion integrations.

**Architecture:** Flask backend refactored into JSON-only API with blueprints, served on Railway. React frontend (Vite + TS + shadcn/ui) on Vercel. Cobrand stats pulled via HTML scraping. Notion CRM synced via polling.

**Tech Stack:** Python/Flask/SQLAlchemy (backend), React/TypeScript/Vite/shadcn-ui/TanStack Table/TanStack Query (frontend), PostgreSQL (Railway), Vercel (frontend hosting)

**Design Doc:** `docs/plans/2026-02-22-campaign-hub-refinement-design.md`

---

## Phase 1: Backend Refactor (API-Only Flask)

Goal: Transform the monolithic web_dashboard.py into a clean Flask API with blueprints. All existing functionality preserved, just reorganized and returning JSON instead of HTML.

---

### Task 1: Project Setup and Dependencies

**Files:**
- Modify: `requirements.txt`
- Create: `campaign_manager/config.py`
- Modify: `campaign_manager/__init__.py`

**Step 1: Add new dependencies to requirements.txt**

Add these lines to `requirements.txt`:

```
# CORS support
flask-cors>=4.0.0
```

**Step 2: Create config.py**

Create `campaign_manager/config.py`:

```python
"""Application configuration from environment variables."""
import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "campaign-dashboard-local")
    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
    NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
    NOTION_CRM_DATABASE_ID = os.environ.get(
        "NOTION_CRM_DATABASE_ID", "1961465b-b829-80c9-a1b5-c4cb3284149a"
    )
    IS_RAILWAY = os.environ.get("RAILWAY_ENVIRONMENT") is not None
```

**Step 3: Create app factory in __init__.py**

Replace `campaign_manager/__init__.py` contents:

```python
"""Campaign Manager Flask application factory."""
from flask import Flask
from flask_cors import CORS

from campaign_manager.config import Config
from campaign_manager import db


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    # Initialize CORS
    CORS(app, origins=app.config["CORS_ORIGINS"])

    # Initialize database
    db.init(app.config.get("DATABASE_URL"))

    # Register blueprints
    from campaign_manager.blueprints.health import health_bp
    from campaign_manager.blueprints.campaigns import campaigns_bp
    from campaign_manager.blueprints.internal import internal_bp
    from campaign_manager.blueprints.inbox import inbox_bp
    from campaign_manager.blueprints.webhooks import webhooks_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(internal_bp)
    app.register_blueprint(inbox_bp)
    app.register_blueprint(webhooks_bp)

    return app
```

**Step 4: Install new dependency**

Run: `pip install flask-cors>=4.0.0`

**Step 5: Commit**

```bash
git add requirements.txt campaign_manager/config.py campaign_manager/__init__.py
git commit -m "feat: add app factory, config module, CORS support"
```

---

### Task 2: Extract Utility Functions

**Files:**
- Create: `campaign_manager/utils/__init__.py`
- Create: `campaign_manager/utils/helpers.py`
- Create: `campaign_manager/utils/budget.py`

**Step 1: Create utils package**

Create empty `campaign_manager/utils/__init__.py`.

**Step 2: Create helpers.py**

Extract from `web_dashboard.py` lines ~102-293 into `campaign_manager/utils/helpers.py`:

```python
"""Shared helper functions extracted from web_dashboard."""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict

import requests


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    return text


def load_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return {}


def save_json(path: Path, data: Dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def campaign_title(meta: Dict) -> str:
    return meta.get("title") or meta.get("name") or "Untitled Campaign"


def parse_sort_datetime(meta: Dict) -> datetime:
    created_at = str(meta.get("created_at") or "").strip()
    if created_at:
        try:
            return datetime.fromisoformat(created_at)
        except Exception:
            pass
    start_date = str(meta.get("start_date") or "").strip()
    if start_date:
        for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(start_date, fmt)
            except Exception:
                continue
    return datetime.min


def resolve_tiktok_short_url(short_url: str) -> str:
    try:
        resp = requests.head(short_url, allow_redirects=True, timeout=10,
                             headers={"User-Agent": "Mozilla/5.0"})
        return resp.url
    except Exception:
        try:
            resp = requests.get(short_url, allow_redirects=True, timeout=10,
                                headers={"User-Agent": "Mozilla/5.0"}, stream=True)
            return resp.url
        except Exception:
            return short_url


def extract_sound_id_from_html(video_url: str):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(video_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None, None
        pattern = r'<script[^>]*id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>'
        matches = re.findall(pattern, resp.text, re.DOTALL)
        if not matches:
            return None, None
        data = json.loads(matches[0])
        music = data["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"]["itemStruct"]["music"]
        sound_id = music.get("id")
        song_title = music.get("title", "")
        if sound_id and str(sound_id).isdigit():
            return str(sound_id), song_title
        return None, song_title
    except Exception:
        return None, None


def extract_sound_id(input_str: str) -> str:
    input_str = input_str.strip()
    if re.match(r"^\d{10,}$", input_str):
        return input_str
    if "tiktok.com/music/" in input_str:
        match = re.search(r"-(\d{10,})(?:\?|$)", input_str)
        if match:
            return match.group(1)
        match = re.search(r"(\d{10,})", input_str)
        if match:
            return match.group(1)
    if "tiktok.com/t/" in input_str:
        resolved = resolve_tiktok_short_url(input_str)
        if resolved != input_str:
            return extract_sound_id(resolved)
    if "tiktok.com/" in input_str and ("/video/" in input_str or "/photo/" in input_str):
        sound_id, _ = extract_sound_id_from_html(input_str)
        if sound_id:
            return sound_id
    match = re.search(r"(\d{10,})", input_str)
    if match:
        return match.group(1)
    return input_str


def is_original_sound(song: str, artist: str) -> bool:
    s = (song or "").strip().lower()
    if s.startswith("original sound"):
        return True
    if s == "unknown" or s == "":
        return True
    if s.startswith("son original") or s.startswith("suara asli"):
        return True
    return False
```

**Step 3: Create budget.py**

Extract budget/stats calculations into `campaign_manager/utils/budget.py`:

```python
"""Budget and stats calculation helpers."""
from typing import Dict, List


def calc_budget(meta: Dict, creators: List[Dict]) -> Dict:
    total = float(meta.get("budget", 0) or 0)
    active = [c for c in creators if c.get("status", "active") != "removed"]
    booked = sum(float(c.get("total_rate", 0) or 0) for c in active)
    paid = sum(float(c.get("total_rate", 0) or 0) for c in active if str(c.get("paid", "")).lower() == "yes")
    left = total - booked
    pct = round(booked / total * 100) if total > 0 else 0
    return {"total": total, "booked": booked, "paid": paid, "left": left, "pct": pct}


def calc_stats(meta: Dict, creators: List[Dict]) -> Dict:
    active = [c for c in creators if c.get("status", "active") != "removed"]
    live_posts = sum(int(c.get("posts_done", 0) or 0) for c in active)
    stored = meta.get("stats", {})
    total_views = int(stored.get("total_views", 0))
    budget_info = calc_budget(meta, creators)
    cpm = None
    if total_views > 0 and budget_info["booked"] > 0:
        cpm = (budget_info["booked"] / total_views) * 1_000_000
    return {
        "live_posts": live_posts,
        "total_views": total_views,
        "cpm": cpm,
    }
```

**Step 4: Commit**

```bash
git add campaign_manager/utils/
git commit -m "refactor: extract helpers and budget utils from web_dashboard"
```

---

### Task 3: Create Blueprint Stubs

**Files:**
- Create: `campaign_manager/blueprints/__init__.py`
- Create: `campaign_manager/blueprints/health.py`
- Create: `campaign_manager/blueprints/campaigns.py`
- Create: `campaign_manager/blueprints/internal.py`
- Create: `campaign_manager/blueprints/inbox.py`
- Create: `campaign_manager/blueprints/webhooks.py`

**Step 1: Create blueprints package**

Create empty `campaign_manager/blueprints/__init__.py`.

**Step 2: Create health.py**

```python
"""Health check endpoint."""
from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    return jsonify({"ok": True})
```

**Step 3: Create campaigns.py**

Move all campaign-related routes from `web_dashboard.py` into `campaign_manager/blueprints/campaigns.py`. This includes:

- `GET /api/campaigns` (existing)
- `GET /api/campaign/<slug>` (existing)
- `GET /api/campaign/<slug>/budget` (existing)
- `GET /api/search` (existing)
- `POST /api/campaign/create` (convert from form POST to JSON POST)
- `POST /api/campaign/<slug>/edit` (convert to JSON)
- `POST /api/campaign/<slug>/refresh` (keep as-is, returns JSON)
- `GET /api/campaign/<slug>/links` (convert to JSON)
- `POST /api/campaign/<slug>/creator/add` (convert to JSON)
- `POST /api/campaign/<slug>/creator/<username>/edit` (convert to JSON)
- `POST /api/campaign/<slug>/creator/<username>/toggle-paid` (already JSON)
- `POST /api/campaign/<slug>/creator/<username>/remove` (convert to JSON)
- `GET /api/paypal/<username>` (existing)
- `GET /api/campaign/<slug>/cobrand` (new)
- `PUT /api/campaign/<slug>/cobrand` (new)

All routes that previously used `render_template` should return `jsonify` responses instead. All routes that previously read `request.form` should read `request.get_json()` instead.

The blueprint prefix is `/api` for all API routes.

**Step 4: Create internal.py**

Move all internal creator routes:

- `GET /api/internal/creators`
- `POST /api/internal/creators`
- `DELETE /api/internal/creators/<username>`
- `POST /api/internal/scrape`
- `GET /api/internal/scrape/status`
- `GET /api/internal/results`
- `GET /api/internal/creator/<username>`

**Step 5: Create inbox.py**

Move all inbox routes:

- `GET /api/inbox`
- `POST /api/inbox`
- `POST /api/inbox/<item_id>/approve`
- `POST /api/inbox/<item_id>/dismiss`

**Step 6: Create webhooks.py**

Stub for now (implemented in Phase 3):

```python
"""Webhook endpoints for external integrations."""
from flask import Blueprint, jsonify

webhooks_bp = Blueprint("webhooks", __name__, url_prefix="/api/webhooks")


@webhooks_bp.post("/notion")
def notion_webhook():
    # Implemented in Phase 3
    return jsonify({"error": "Not implemented"}), 501
```

**Step 7: Commit**

```bash
git add campaign_manager/blueprints/
git commit -m "refactor: create blueprint stubs for all route modules"
```

---

### Task 4: Migrate Campaign Routes to Blueprint

**Files:**
- Modify: `campaign_manager/blueprints/campaigns.py`

This is the largest task. Move every campaign-related route from `web_dashboard.py` into the campaigns blueprint. Convert all `render_template` calls to `jsonify` returns. Convert all `request.form` reads to `request.get_json()`.

Key conversion pattern for each route:

```python
# BEFORE (web_dashboard.py):
@app.post("/campaign/create")
def create_campaign():
    title = (request.form.get("title") or "").strip()
    # ... logic ...
    flash(f"Created campaign: {title}", "ok")
    return redirect(url_for("campaign_detail", slug=slug))

# AFTER (blueprints/campaigns.py):
@campaigns_bp.post("/campaign/create")
def create_campaign():
    data = request.get_json()
    title = (data.get("title") or "").strip()
    # ... same logic ...
    return jsonify({"ok": True, "slug": slug, "message": f"Created campaign: {title}"})
```

The `get_campaigns()` helper function should also be moved into this blueprint (or into a shared service) since it orchestrates loading campaign data from DB or files.

**Step 1: Implement the full campaigns blueprint with all routes converted**

**Step 2: Verify the existing /api/* routes still return the same JSON shape**

**Step 3: Commit**

```bash
git add campaign_manager/blueprints/campaigns.py
git commit -m "refactor: migrate all campaign routes to blueprint (JSON-only)"
```

---

### Task 5: Migrate Internal and Inbox Routes

**Files:**
- Modify: `campaign_manager/blueprints/internal.py`
- Modify: `campaign_manager/blueprints/inbox.py`

**Step 1: Implement internal.py with all routes from the Internal TikTok section of web_dashboard.py**

Convert `internal_page`, `internal_add_creator`, `internal_remove_creator`, `internal_scrape`, `internal_scrape_status`, `internal_creator_detail` to JSON-returning API endpoints.

The background scrape thread logic (`_run_internal_scrape`, `_internal_scrape_status` global dict) moves here.

**Step 2: Implement inbox.py**

These are already JSON endpoints in `web_dashboard.py` -- mostly a cut-and-paste into the blueprint with the import paths updated.

**Step 3: Commit**

```bash
git add campaign_manager/blueprints/internal.py campaign_manager/blueprints/inbox.py
git commit -m "refactor: migrate internal and inbox routes to blueprints"
```

---

### Task 6: Update Model with New Fields

**Files:**
- Modify: `campaign_manager/models.py`
- Modify: `campaign_manager/db.py`

**Step 1: Add new columns to Campaign model in models.py**

```python
# Add these columns to the Campaign class:
cobrand_share_url = Column(Text, default="")
cobrand_upload_url = Column(Text, default="")
cobrand_promotion_id = Column(String(100), default="")
cobrand_last_sync = Column(DateTime, nullable=True)
cobrand_live_submissions = Column(Integer, default=0)
cobrand_comments = Column(Integer, default=0)
cobrand_status = Column(String(50), default="")
source = Column(String(20), default="manual")
notion_page_id = Column(String(100), nullable=True, unique=True)
insta_sound = Column(Text, default="")
campaign_stage = Column(String(50), default="")
round = Column(String(20), default="")
label = Column(String(255), default="")
project_lead = Column(JSONB, default=list)
client_email = Column(String(255), default="")
platform_split = Column(JSONB, default=dict)
content_types = Column(JSONB, default=list)
```

**Step 2: Update `to_meta_dict()` to include new fields**

**Step 3: Update `save_campaign()` in db.py to handle new fields**

**Step 4: Commit**

```bash
git add campaign_manager/models.py campaign_manager/db.py
git commit -m "feat: add Cobrand, Notion, and CRM fields to Campaign model"
```

---

### Task 7: Update Dockerfile and Entry Point

**Files:**
- Modify: `Dockerfile`

**Step 1: Update the CMD to use the app factory**

Change the gunicorn CMD in Dockerfile:

```dockerfile
CMD gunicorn --workers 4 --timeout 120 --bind 0.0.0.0:${PORT:-8080} "campaign_manager:create_app()"
```

**Step 2: Commit**

```bash
git add Dockerfile
git commit -m "refactor: update Dockerfile CMD for app factory pattern"
```

---

### Task 8: Verify Backend Works Locally

**Step 1: Run the app locally**

```bash
cd risingtides-campaign-hub
FLASK_APP=campaign_manager python -m flask run --port 5055
```

**Step 2: Test key endpoints**

```bash
curl http://localhost:5055/health
curl http://localhost:5055/api/campaigns
```

Expected: JSON responses, no errors.

**Step 3: If everything works, commit any fixes and tag the backend as done**

```bash
git add -A
git commit -m "refactor: backend migration to blueprints complete"
```

---

## Phase 2: Cobrand Integration Service

Goal: Add the service that fetches live campaign stats from Cobrand share pages.

---

### Task 9: Create Cobrand Service

**Files:**
- Create: `campaign_manager/services/__init__.py`
- Create: `campaign_manager/services/cobrand.py`

**Step 1: Create services package**

Create empty `campaign_manager/services/__init__.py`.

**Step 2: Implement cobrand.py**

```python
"""Cobrand integration -- fetch live campaign stats from share pages."""
import json
import re
from typing import Dict, Optional

import requests


def fetch_cobrand_stats(share_url: str) -> Optional[Dict]:
    """Fetch the Cobrand share page and extract performance data from __NEXT_DATA__."""
    if not share_url:
        return None

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(share_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None

        # Parse __NEXT_DATA__ script tag
        pattern = r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>'
        matches = re.findall(pattern, resp.text, re.DOTALL)
        if not matches:
            return None

        data = json.loads(matches[0])
        promotion = data.get("props", {}).get("pageProps", {}).get("promotion")
        if not promotion:
            return None

        # Extract performance fields only (no financial data)
        activations = []
        for act in promotion.get("activations", []):
            sounds = []
            segment = act.get("segment", {})
            for sound in segment.get("social_sounds", []):
                sounds.append({
                    "id_platform": sound.get("id_platform", ""),
                    "platform": sound.get("platform", ""),
                    "title": sound.get("title", ""),
                })

            artist = act.get("artist", {})
            activations.append({
                "id": act.get("id", ""),
                "name": act.get("name", ""),
                "artist_name": artist.get("name", ""),
                "artist_image_url": artist.get("image_url", ""),
                "social_sounds": sounds,
                "created_at": act.get("created_at", ""),
                "draft_submission_due_at": act.get("draft_submission_due_at"),
                "final_submission_due_at": act.get("final_submission_due_at"),
                "tags": act.get("tags", []),
            })

        return {
            "promotion_id": promotion.get("id", ""),
            "name": promotion.get("name", ""),
            "status": promotion.get("status", ""),
            "live_submission_count": promotion.get("live_submission_count", 0),
            "draft_submission_count": promotion.get("draft_submission_count", 0),
            "comment_count": promotion.get("comment_count", 0),
            "activation_count": promotion.get("activation_count", 0),
            "created_at": promotion.get("created_at", ""),
            "activations": activations,
        }

    except Exception:
        return None
```

**Step 3: Commit**

```bash
git add campaign_manager/services/
git commit -m "feat: add Cobrand integration service for live stats"
```

---

### Task 10: Add Cobrand API Endpoints

**Files:**
- Modify: `campaign_manager/blueprints/campaigns.py`

**Step 1: Add GET /api/campaign/<slug>/cobrand endpoint**

```python
@campaigns_bp.get("/campaign/<slug>/cobrand")
def get_cobrand_stats(slug: str):
    """Fetch live stats from Cobrand for this campaign."""
    from campaign_manager.services.cobrand import fetch_cobrand_stats

    meta = _db.get_campaign(slug)
    if not meta:
        return jsonify({"error": "Campaign not found"}), 404

    share_url = meta.get("cobrand_share_url", "")
    if not share_url:
        return jsonify({"error": "No Cobrand tracking link configured"}), 404

    stats = fetch_cobrand_stats(share_url)
    if stats is None:
        return jsonify({"error": "Failed to fetch Cobrand stats"}), 502

    # Cache the stats in the database
    _db.update_cobrand_cache(slug, stats)

    return jsonify(stats)
```

**Step 2: Add PUT /api/campaign/<slug>/cobrand endpoint**

```python
@campaigns_bp.put("/campaign/<slug>/cobrand")
def set_cobrand_links(slug: str):
    """Set or update Cobrand share and upload URLs for a campaign."""
    data = request.get_json()
    share_url = (data.get("share_url") or "").strip()
    upload_url = (data.get("upload_url") or "").strip()

    if not _db.campaign_exists(slug):
        return jsonify({"error": "Campaign not found"}), 404

    updates = {}
    if share_url:
        updates["cobrand_share_url"] = share_url
    if upload_url:
        updates["cobrand_upload_url"] = upload_url

    # TODO: add update_campaign_fields to db.py
    return jsonify({"ok": True, "message": "Cobrand links updated"})
```

**Step 3: Add `update_cobrand_cache` to db.py**

**Step 4: Commit**

```bash
git add campaign_manager/blueprints/campaigns.py campaign_manager/db.py
git commit -m "feat: add Cobrand API endpoints for stats and link configuration"
```

---

## Phase 3: Notion CRM Integration

Goal: Implement polling-based sync from Notion CRM to auto-create campaigns.

---

### Task 11: Create Notion Sync Service

**Files:**
- Create: `campaign_manager/services/notion.py`

**Step 1: Implement notion.py**

```python
"""Notion CRM sync -- poll for new 'Client' entries and create campaigns."""
import requests
from typing import Dict, List, Optional

from campaign_manager.config import Config
from campaign_manager.utils.helpers import slugify, extract_sound_id


NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {Config.NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def _get_text(prop: Dict) -> str:
    """Extract plain text from a Notion rich_text or title property."""
    key = "rich_text" if "rich_text" in prop else "title"
    parts = prop.get(key, [])
    return "".join(t.get("plain_text", "") for t in parts)


def _get_select(prop: Dict) -> str:
    s = prop.get("select")
    return s.get("name", "") if s else ""


def _get_multi(prop: Dict) -> List[str]:
    return [o.get("name", "") for o in prop.get("multi_select", [])]


def _get_status(prop: Dict) -> str:
    s = prop.get("status")
    return s.get("name", "") if s else ""


def _get_url(prop: Dict) -> str:
    return prop.get("url", "") or ""


def _get_date(prop: Dict) -> str:
    d = prop.get("date")
    return d.get("start", "") if d else ""


def _get_number(prop: Dict) -> Optional[float]:
    return prop.get("number")


def _get_email(prop: Dict) -> str:
    return prop.get("email", "") or ""


def query_new_clients(synced_page_ids: set) -> List[Dict]:
    """Query Notion CRM for entries with Pipeline Status = 'Client' not yet synced."""
    url = f"{NOTION_API_BASE}/databases/{Config.NOTION_CRM_DATABASE_ID}/query"

    payload = {
        "filter": {
            "property": "Pipeline Status",
            "status": {"equals": "Client"},
        },
        "page_size": 50,
    }

    resp = requests.post(url, headers=_headers(), json=payload, timeout=15)
    if resp.status_code != 200:
        return []

    results = []
    for page in resp.json().get("results", []):
        page_id = page["id"]
        if page_id in synced_page_ids:
            continue

        props = page.get("properties", {})

        artist = _get_text(props.get("Artist Name", {}))
        song = _get_text(props.get("Song Name", {}))
        tiktok_sound = _get_url(props.get("TikTok Sound Link", {}))
        insta_sound = _get_url(props.get("Insta Sound Link", {}))
        cobrand = _get_url(props.get("Co Brand Link", {}))
        start_date = _get_date(props.get("Desired Start Date", {}))
        budget = _get_number(props.get("Media Spend", {}))
        stage = _get_status(props.get("Campaign Stage", {}))
        round_val = _get_select(props.get("Round", {}))
        label = _get_text(props.get("Label/Distro Partner", {}))
        lead = _get_multi(props.get("Project Lead", {}))
        email = _get_email(props.get("Key Contact Email", {}))
        content_types = _get_multi(props.get("Types of Content Creators", {}))

        tiktok_pct = _get_multi(props.get("TikTok", {}))
        insta_pct = _get_multi(props.get("Instagram", {}))
        platform_split = {}
        if tiktok_pct:
            platform_split["tiktok"] = int(tiktok_pct[0].replace("%", "") or 0)
        if insta_pct:
            platform_split["instagram"] = int(insta_pct[0].replace("%", "") or 0)

        sound_id = ""
        if tiktok_sound:
            sound_id = extract_sound_id(tiktok_sound)

        title = f"{artist} - {song}".strip(" -") if artist and song else artist or song
        slug = slugify(title)

        results.append({
            "notion_page_id": page_id,
            "title": title,
            "slug": slug,
            "artist": artist,
            "song": song,
            "official_sound": tiktok_sound,
            "sound_id": sound_id,
            "insta_sound": insta_sound,
            "cobrand_share_url": cobrand,
            "start_date": start_date,
            "budget": float(budget) if budget else 0.0,
            "campaign_stage": stage,
            "round": round_val,
            "label": label,
            "project_lead": lead,
            "client_email": email,
            "content_types": content_types,
            "platform_split": platform_split,
            "source": "notion",
        })

    return results
```

**Step 2: Commit**

```bash
git add campaign_manager/services/notion.py
git commit -m "feat: add Notion CRM sync service"
```

---

### Task 12: Add Notion Webhook and Sync Endpoints

**Files:**
- Modify: `campaign_manager/blueprints/webhooks.py`

**Step 1: Implement the webhook endpoint and manual sync trigger**

```python
"""Webhook endpoints for external integrations."""
from flask import Blueprint, jsonify, request

from campaign_manager import db as _db
from campaign_manager.services.notion import query_new_clients

webhooks_bp = Blueprint("webhooks", __name__, url_prefix="/api/webhooks")


@webhooks_bp.post("/notion")
def notion_webhook():
    """Accept a campaign payload from Notion (via n8n/Make/manual trigger)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    slug = data.get("slug", "")
    if not slug:
        from campaign_manager.utils.helpers import slugify
        title = data.get("title", "")
        if not title:
            artist = data.get("artist", "")
            song = data.get("song", "")
            title = f"{artist} - {song}".strip(" -")
        slug = slugify(title)

    if _db.campaign_exists(slug):
        return jsonify({"error": f"Campaign '{slug}' already exists", "slug": slug}), 409

    from datetime import datetime
    meta = {
        "title": data.get("title", slug),
        "name": data.get("title", slug),
        "slug": slug,
        "artist": data.get("artist", ""),
        "song": data.get("song", ""),
        "official_sound": data.get("tiktok_sound_link", ""),
        "sound_id": data.get("sound_id", ""),
        "start_date": data.get("start_date", ""),
        "budget": float(data.get("budget", 0) or 0),
        "status": "queued",
        "platform": "tiktok",
        "created_at": datetime.now().isoformat(),
        "stats": {"total_views": 0, "total_likes": 0},
    }

    _db.save_campaign(slug, meta)
    # TODO: save additional fields (notion_page_id, label, etc.) via extended save

    return jsonify({"ok": True, "slug": slug, "message": f"Campaign created from Notion"})


@webhooks_bp.post("/notion/sync")
def notion_sync():
    """Manual trigger: poll Notion CRM for new Client entries and create campaigns."""
    synced_ids = _db.get_synced_notion_ids()
    new_entries = query_new_clients(synced_ids)

    created = []
    skipped = []

    for entry in new_entries:
        slug = entry["slug"]
        if _db.campaign_exists(slug):
            skipped.append(slug)
            continue

        from datetime import datetime
        meta = {
            "title": entry["title"],
            "name": entry["title"],
            "slug": slug,
            "artist": entry["artist"],
            "song": entry["song"],
            "official_sound": entry["official_sound"],
            "sound_id": entry["sound_id"],
            "start_date": entry["start_date"],
            "budget": entry["budget"],
            "status": "queued",
            "platform": "tiktok",
            "created_at": datetime.now().isoformat(),
            "stats": {"total_views": 0, "total_likes": 0},
        }
        _db.save_campaign(slug, meta)
        # TODO: save extended fields
        created.append(slug)

    return jsonify({
        "ok": True,
        "created": created,
        "skipped": skipped,
        "message": f"Synced {len(created)} new campaigns from Notion",
    })
```

**Step 2: Add `get_synced_notion_ids()` to db.py**

**Step 3: Commit**

```bash
git add campaign_manager/blueprints/webhooks.py campaign_manager/db.py
git commit -m "feat: add Notion webhook and sync endpoints"
```

---

## Phase 4: React Frontend

Goal: Build the React frontend that replaces the Jinja templates.

---

### Task 13: Scaffold React App

**Step 1: Create Vite + React + TypeScript project**

```bash
cd risingtides-campaign-hub
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

**Step 2: Install dependencies**

```bash
npm install @tanstack/react-table @tanstack/react-query react-router-dom
npm install -D tailwindcss @tailwindcss/vite
```

**Step 3: Initialize Tailwind**

Add Tailwind to `frontend/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
})
```

Add to `frontend/src/index.css`:

```css
@import "tailwindcss";
```

**Step 4: Initialize shadcn/ui**

```bash
cd frontend
npx shadcn@latest init
```

Select: New York style, Slate base color, CSS variables.

**Step 5: Add shadcn components we need**

```bash
npx shadcn@latest add table button input badge card select dialog tabs separator dropdown-menu
```

**Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold React frontend with Vite, Tailwind, shadcn/ui"
```

---

### Task 14: API Client and React Query Setup

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/queries.ts`

**Step 1: Create API client**

```typescript
// frontend/src/lib/api.ts
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:5055";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(error.error || res.statusText);
  }
  return res.json();
}

export const api = {
  // Campaigns
  getCampaigns: () => request<any[]>("/api/campaigns"),
  getCampaign: (slug: string) => request<any>(`/api/campaign/${slug}`),
  getCampaignBudget: (slug: string) => request<any>(`/api/campaign/${slug}/budget`),
  createCampaign: (data: any) => request<any>("/api/campaign/create", { method: "POST", body: JSON.stringify(data) }),
  editCampaign: (slug: string, data: any) => request<any>(`/api/campaign/${slug}/edit`, { method: "POST", body: JSON.stringify(data) }),
  refreshStats: (slug: string) => request<any>(`/api/campaign/${slug}/refresh`, { method: "POST" }),
  getCampaignLinks: (slug: string) => request<any>(`/api/campaign/${slug}/links`),
  searchCampaigns: (q: string) => request<any>(`/api/search?q=${encodeURIComponent(q)}`),

  // Creators
  addCreator: (slug: string, data: any) => request<any>(`/api/campaign/${slug}/creator/add`, { method: "POST", body: JSON.stringify(data) }),
  editCreator: (slug: string, username: string, data: any) => request<any>(`/api/campaign/${slug}/creator/${username}/edit`, { method: "POST", body: JSON.stringify(data) }),
  togglePaid: (slug: string, username: string) => request<any>(`/api/campaign/${slug}/creator/${username}/toggle-paid`, { method: "POST" }),
  removeCreator: (slug: string, username: string) => request<any>(`/api/campaign/${slug}/creator/${username}/remove`, { method: "POST" }),
  getPaypal: (username: string) => request<any>(`/api/paypal/${username}`),

  // Cobrand
  getCobrandStats: (slug: string) => request<any>(`/api/campaign/${slug}/cobrand`),
  setCobrandLinks: (slug: string, data: any) => request<any>(`/api/campaign/${slug}/cobrand`, { method: "PUT", body: JSON.stringify(data) }),

  // Internal
  getInternalCreators: () => request<any>("/api/internal/creators"),
  addInternalCreators: (data: any) => request<any>("/api/internal/creators", { method: "POST", body: JSON.stringify(data) }),
  removeInternalCreator: (username: string) => request<any>(`/api/internal/creators/${username}`, { method: "DELETE" }),
  triggerInternalScrape: (hours: number) => request<any>("/api/internal/scrape", { method: "POST", body: JSON.stringify({ hours }) }),
  getInternalScrapeStatus: () => request<any>("/api/internal/scrape/status"),
  getInternalResults: () => request<any>("/api/internal/results"),
  getInternalCreator: (username: string) => request<any>(`/api/internal/creator/${username}`),

  // Inbox
  getInbox: (status?: string) => request<any[]>(`/api/inbox${status ? `?status=${status}` : ""}`),
  approveInbox: (id: string, data: any) => request<any>(`/api/inbox/${id}/approve`, { method: "POST", body: JSON.stringify(data) }),
  dismissInbox: (id: string) => request<any>(`/api/inbox/${id}/dismiss`, { method: "POST" }),

  // Notion sync
  syncNotion: () => request<any>("/api/webhooks/notion/sync", { method: "POST" }),
};
```

**Step 2: Create React Query hooks in queries.ts**

Set up `useQuery` and `useMutation` wrappers for each API call.

**Step 3: Set up QueryClientProvider in main.tsx**

**Step 4: Commit**

```bash
git add frontend/src/lib/
git commit -m "feat: add API client and React Query setup"
```

---

### Task 15: Layout and Navigation

**Files:**
- Create: `frontend/src/components/layout/Sidebar.tsx`
- Create: `frontend/src/components/layout/Layout.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Build sidebar matching the existing design**

Same navigation structure: Promotions, Internal TikTok, Slack Inbox. Same colors (#1a1a2e, #0b62d6, #f7f7f9). Mobile: hamburger menu that slides in.

**Step 2: Set up React Router with routes**

```typescript
// Routes:
// /              -> CampaignsList
// /campaign/:slug -> CampaignDetail
// /internal      -> InternalTikTok
// /internal/:username -> InternalCreatorDetail
// /inbox         -> SlackInbox
```

**Step 3: Commit**

```bash
git add frontend/src/
git commit -m "feat: add layout, sidebar, and routing"
```

---

### Task 16: Campaigns List Page

**Files:**
- Create: `frontend/src/pages/CampaignsList.tsx`
- Create: `frontend/src/components/campaigns/CampaignsTable.tsx`
- Create: `frontend/src/components/campaigns/CreateCampaignForm.tsx`

**Step 1: Build CampaignsTable with TanStack Table**

Sortable columns: Title, Artist, Status, Budget, Total Views, Live Posts, CPM. Click row to navigate to detail page.

**Step 2: Build CreateCampaignForm (expandable, mirrors existing form)**

**Step 3: Add search bar**

**Step 4: Commit**

```bash
git add frontend/src/pages/ frontend/src/components/campaigns/
git commit -m "feat: add campaigns list page with sortable table"
```

---

### Task 17: Campaign Detail Page

**Files:**
- Create: `frontend/src/pages/CampaignDetail.tsx`
- Create: `frontend/src/components/campaigns/CampaignHeader.tsx`
- Create: `frontend/src/components/campaigns/StatCards.tsx`
- Create: `frontend/src/components/campaigns/CreatorsTable.tsx`
- Create: `frontend/src/components/campaigns/AddCreatorForm.tsx`
- Create: `frontend/src/components/campaigns/CobrandSection.tsx`

**Step 1: Campaign header with inline edit mode (display/edit toggle)**

**Step 2: Stat cards (budget, paid, live posts, views, CPM)**

**Step 3: Cobrand stats section (fetches from /api/campaign/<slug>/cobrand)**

**Step 4: Creators table with TanStack Table (sortable, inline edit, toggle paid)**

**Step 5: Add creator form**

**Step 6: Cobrand upload section (iframe embed + link clipboard)**

**Step 7: Commit**

```bash
git add frontend/src/pages/CampaignDetail.tsx frontend/src/components/campaigns/
git commit -m "feat: add campaign detail page with Cobrand stats and creator management"
```

---

### Task 18: Internal TikTok Pages

**Files:**
- Create: `frontend/src/pages/InternalTikTok.tsx`
- Create: `frontend/src/pages/InternalCreatorDetail.tsx`
- Create: `frontend/src/components/internal/CreatorSidebar.tsx`
- Create: `frontend/src/components/internal/ScrapeProgress.tsx`
- Create: `frontend/src/components/internal/SongsResults.tsx`

**Step 1: Two-panel layout (creator sidebar + results)**

**Step 2: Scrape trigger with real-time polling progress bar**

**Step 3: Songs results with sortable table and copy-links**

**Step 4: Creator detail page with cached videos**

**Step 5: Commit**

```bash
git add frontend/src/pages/ frontend/src/components/internal/
git commit -m "feat: add internal TikTok pages with scrape progress"
```

---

### Task 19: Slack Inbox Page

**Files:**
- Create: `frontend/src/pages/SlackInbox.tsx`
- Create: `frontend/src/components/inbox/InboxCard.tsx`

**Step 1: Pending items with editable fields**

**Step 2: Campaign selector dropdown**

**Step 3: Approve/dismiss with optimistic updates (no page refresh)**

**Step 4: Approved/dismissed history sections**

**Step 5: Commit**

```bash
git add frontend/src/pages/SlackInbox.tsx frontend/src/components/inbox/
git commit -m "feat: add Slack inbox page with approve/dismiss workflow"
```

---

### Task 20: Mobile Responsive Layout

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx`
- Modify: `frontend/src/components/layout/Layout.tsx`
- Modify: various page components

**Step 1: Sidebar collapses to hamburger menu on mobile (< 768px)**

**Step 2: Tables switch to card layouts on mobile**

**Step 3: Stat grids stack vertically**

**Step 4: Test at 375px, 768px, 1024px, 1440px widths**

**Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat: add mobile responsive layout"
```

---

## Phase 5: Deployment

Goal: Deploy both services and verify end-to-end.

---

### Task 21: Deploy Backend to Railway

**Step 1: Set environment variables on Railway**

```
DATABASE_URL      = (already set)
SECRET_KEY        = (generate a random string)
CORS_ORIGINS      = https://your-app.vercel.app
NOTION_API_KEY    = ntn_Z547538333765ndn3tLFdv5XFNDKPGXcXouqcN8C9hDedm
NOTION_CRM_DATABASE_ID = 1961465b-b829-80c9-a1b5-c4cb3284149a
```

**Step 2: Push to Railway and verify deployment**

```bash
curl https://your-railway-url.up.railway.app/health
```

Expected: `{"ok": true}`

**Step 3: Verify API endpoints work**

```bash
curl https://your-railway-url.up.railway.app/api/campaigns
```

---

### Task 22: Deploy Frontend to Vercel

**Step 1: Create Vercel project from the frontend/ directory**

**Step 2: Set environment variable**

```
VITE_API_URL = https://your-railway-url.up.railway.app
```

**Step 3: Deploy and verify**

Navigate to the Vercel URL. Campaigns list should load with data from Railway.

**Step 4: Update CORS_ORIGINS on Railway with the actual Vercel URL**

---

### Task 23: End-to-End Verification

**Step 1: Create a test campaign from the React frontend**

**Step 2: Add a creator, toggle paid status**

**Step 3: Add a Cobrand tracking link, verify live stats load**

**Step 4: Trigger a Notion sync, verify new campaigns appear**

**Step 5: Run an internal scrape, verify progress polling works**

**Step 6: Test inbox approve/dismiss flow**

**Step 7: Test on mobile**

---

### Task 24: Clean Up Legacy Code

**Files:**
- Delete: `campaign_manager/templates/` (all 6 files)
- Delete: `campaign_manager/web_dashboard.py`

**Step 1: Remove Jinja templates directory**

**Step 2: Remove web_dashboard.py (all routes now in blueprints)**

**Step 3: Remove Jinja2 from requirements.txt if it was explicitly listed (Flask includes it but it's no longer used)**

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: remove legacy Jinja templates and monolithic web_dashboard"
```

---

## Summary

| Phase | Tasks | What Ships |
|---|---|---|
| Phase 1 | Tasks 1-8 | Flask API with blueprints, all existing functionality as JSON endpoints |
| Phase 2 | Tasks 9-10 | Cobrand live stats integration |
| Phase 3 | Tasks 11-12 | Notion CRM sync |
| Phase 4 | Tasks 13-20 | Full React frontend with sortable tables and mobile layout |
| Phase 5 | Tasks 21-24 | Deployed to Railway + Vercel, legacy code removed |

Each phase is independently deployable. Phase 1 can ship while the old Jinja frontend still works (both the old HTML routes and new API routes coexist until Phase 5 removes the templates).
