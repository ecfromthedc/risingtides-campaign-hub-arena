"""TidesTracker API client.

Talks to the TidesTracker service via its `/api/campaigns` endpoint.
TidesTracker is the source of truth for tracker data; Campaign Hub only
maintains a local "folder" overlay (groups + assignments).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import requests as _requests
from flask import current_app


class TidesTrackerError(Exception):
    """Raised when the TidesTracker API call fails or is unconfigured."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


# Pinned to the canonical TidesTracker domain so the integration can't
# silently break when a Vercel subdomain alias drifts to an old build.
# Env var overrides only for dev/staging.
TIDESTRACKER_PUBLIC_URL = "https://risingtides-tracker.com/"
TIDESTRACKER_DEFAULT_API = "https://risingtides-tracker.com/api"


def _config() -> Tuple[str, str, str]:
    api = current_app.config.get("TIDESTRACKER_API_URL", "") or TIDESTRACKER_DEFAULT_API
    key = current_app.config.get("TIDESTRACKER_SERVICE_KEY", "")
    base = current_app.config.get("TIDESTRACKER_BASE_URL", "") or TIDESTRACKER_PUBLIC_URL
    if not key:
        raise TidesTrackerError(
            "TidesTracker not configured. Set TIDESTRACKER_SERVICE_KEY.",
            status_code=500,
        )
    # Force the canonical domain even if a stale env var still points at the
    # raw Vercel subdomain — that subdomain has historically pinned to old
    # deployments and missed feature deploys.
    if "frontend-tidestracker.vercel.app" in api:
        api = TIDESTRACKER_DEFAULT_API
    return api, key, base


def tracker_url_for(tracker_id: str) -> str:
    """Public deep link to a specific tracker.

    TidesTracker exposes auth-free public dashboards at /<uuid>
    (see api/public/[campaignId].ts on the TidesTracker side), so the
    UUID itself is the access token.
    """
    if not tracker_id:
        return ""
    return f"{TIDESTRACKER_PUBLIC_URL.rstrip('/')}/{tracker_id}"


def create_tracker_campaign(
    name: str,
    slug: str,
    cobrand_share_url: str,
    client_id: Optional[str] = None,
) -> Tuple[str, str]:
    """Call the TidesTracker API to create a campaign.

    Returns (tracker_campaign_id, tracker_url).
    Raises TidesTrackerError on configuration issues or HTTP failure.
    """
    api, key, base = _config()

    if not cobrand_share_url:
        raise TidesTrackerError("cobrand_share_url is required", status_code=400)

    try:
        resp = _requests.post(
            f"{api}/campaigns",
            json={
                "name": name,
                "slug": slug,
                "cobrand_share_link": cobrand_share_url,
                "client_id": client_id,
            },
            headers={
                "Content-Type": "application/json",
                "x-service-key": key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()
    except _requests.RequestException as e:
        raise TidesTrackerError(f"Failed to create tracker: {e}", status_code=502)

    tracker_campaign_id = (result.get("campaign") or {}).get("id", "") or ""
    tracker_url = f"{base}/{tracker_campaign_id}" if base and tracker_campaign_id else ""
    return tracker_campaign_id, tracker_url


def list_tracker_campaigns(client_id: Optional[str] = None) -> List[Dict]:
    """Fetch all active campaigns from TidesTracker via the service-key API.

    Returns the raw list of campaign dicts as returned by the API:
        [{ id, client_id, name, slug, cobrand_share_link, is_active,
           created_at, client: { id, name, slug } | None }, ...]
    """
    api, key, _base = _config()

    params = {}
    if client_id:
        params["client_id"] = client_id

    try:
        resp = _requests.get(
            f"{api}/campaigns",
            headers={"x-service-key": key},
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()
    except _requests.RequestException as e:
        raise TidesTrackerError(f"Failed to list trackers: {e}", status_code=502)

    return result.get("campaigns") or []
