"""Notion CRM sync -- poll for new 'Client' entries and create campaigns.

The Notion CRM database (Rising Tides Ent workspace) tracks client relationships
and campaign bookings. When a deal's Pipeline Status changes to "Client", we sync
that entry to Campaign Hub as a new campaign.

CRM Database ID: 1961465b-b829-80c9-a1b5-c4cb3284149a
Integration: "Rising Tides AI" bot (internal integration)
"""
import os
from typing import Dict, List, Optional, Set

import requests

from campaign_manager.utils.helpers import slugify, extract_sound_id


NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _get_api_key() -> str:
    """Get the Notion API key from environment."""
    return os.environ.get("NOTION_API_KEY", "")


def _get_database_id() -> str:
    """Get the CRM database ID from environment."""
    return os.environ.get(
        "NOTION_CRM_DATABASE_ID", "1961465b-b829-80c9-a1b5-c4cb3284149a"
    )


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


# -- Notion property extractors --

def _get_title(prop: Dict) -> str:
    """Extract plain text from a Notion title property."""
    parts = prop.get("title", [])
    return "".join(t.get("plain_text", "") for t in parts)


def _get_rich_text(prop: Dict) -> str:
    """Extract plain text from a Notion rich_text property."""
    parts = prop.get("rich_text", [])
    return "".join(t.get("plain_text", "") for t in parts)


def _get_select(prop: Dict) -> str:
    """Extract value from a Notion select property."""
    s = prop.get("select")
    return s.get("name", "") if s else ""


def _get_multi_select(prop: Dict) -> List[str]:
    """Extract values from a Notion multi_select property."""
    return [o.get("name", "") for o in prop.get("multi_select", [])]


def _get_status(prop: Dict) -> str:
    """Extract value from a Notion status property."""
    s = prop.get("status")
    return s.get("name", "") if s else ""


def _get_url(prop: Dict) -> str:
    """Extract value from a Notion url property."""
    return prop.get("url", "") or ""


def _get_date(prop: Dict) -> str:
    """Extract start date from a Notion date property."""
    d = prop.get("date")
    return d.get("start", "") if d else ""


def _get_number(prop: Dict) -> Optional[float]:
    """Extract value from a Notion number property."""
    return prop.get("number")


def _get_email(prop: Dict) -> str:
    """Extract value from a Notion email property."""
    return prop.get("email", "") or ""


def _parse_platform_split(tiktok_pct: List[str], insta_pct: List[str]) -> Dict:
    """Parse TikTok/Instagram percentage multi-selects into a platform split dict.

    Notion stores these as multi_select with values like "70%", "100%".
    We take the first value from each.
    """
    split = {}
    if tiktok_pct:
        try:
            split["tiktok"] = int(tiktok_pct[0].replace("%", ""))
        except (ValueError, IndexError):
            pass
    if insta_pct:
        try:
            split["instagram"] = int(insta_pct[0].replace("%", ""))
        except (ValueError, IndexError):
            pass
    return split


def query_new_clients(synced_page_ids: Set[str]) -> List[Dict]:
    """Query Notion CRM for entries with Pipeline Status = 'Client' not yet synced.

    Args:
        synced_page_ids: Set of Notion page IDs already imported to Campaign Hub.

    Returns:
        List of campaign dicts ready to be saved via db.save_campaign().
    """
    api_key = _get_api_key()
    if not api_key:
        return []

    database_id = _get_database_id()
    url = f"{NOTION_API_BASE}/databases/{database_id}/query"

    payload = {
        "filter": {
            "property": "Pipeline Status",
            "status": {"equals": "Client"},
        },
        "page_size": 50,
    }

    try:
        resp = requests.post(url, headers=_headers(), json=payload, timeout=15)
        if resp.status_code != 200:
            return []
    except Exception:
        return []

    results = []
    for page in resp.json().get("results", []):
        page_id = page["id"]
        if page_id in synced_page_ids:
            continue

        props = page.get("properties", {})

        # Extract all mapped fields from the CRM schema
        artist = _get_title(props.get("Artist Name", {}))
        song = _get_rich_text(props.get("Song Name", {}))
        tiktok_sound = _get_url(props.get("TikTok Sound Link", {})).strip()
        insta_sound = _get_url(props.get("Insta Sound Link", {})).strip()
        cobrand = _get_url(props.get("Co Brand Link", {})).strip()
        start_date = _get_date(props.get("Desired Start Date", {}))
        budget = _get_number(props.get("Media Spend", {}))
        campaign_stage = _get_status(props.get("Campaign Stage", {}))
        round_val = _get_select(props.get("Round", {}))
        label = _get_rich_text(props.get("Label/Distro Partner", {}))
        lead = _get_multi_select(props.get("Project Lead", {}))
        email = _get_email(props.get("Key Contact Email", {}))
        content_types = _get_multi_select(props.get("Types of Content Creators", {}))
        tiktok_pct = _get_multi_select(props.get("TikTok", {}))
        insta_pct = _get_multi_select(props.get("Instagram", {}))

        platform_split = _parse_platform_split(tiktok_pct, insta_pct)

        # Extract sound ID from TikTok sound link if available
        sound_id = ""
        if tiktok_sound:
            sound_id = extract_sound_id(tiktok_sound)

        # Build campaign title
        if artist and song:
            title = f"{artist} - {song}"
        elif artist:
            title = artist
        elif song:
            title = song
        else:
            title = f"Untitled ({page_id[:8]})"

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
            "campaign_stage": campaign_stage,
            "round": round_val,
            "label": label,
            "project_lead": lead,
            "client_email": email,
            "content_types": content_types,
            "platform_split": platform_split,
            "source": "notion",
        })

    return results
