"""LLM-based parsing for Slack booking messages using Claude API."""
from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional

import anthropic

log = logging.getLogger(__name__)

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


SYSTEM_PROMPT = """\
You are a booking message parser for a music marketing agency. Your job is to \
extract structured booking data from informal Slack messages.

Booking messages typically follow patterns like:
- "Book @username1 for 5 posts at $150 on [campaign name]"
- "@user1 5/$100, @user2 3/$75 - sombr campaign"
- "username - 5 posts $200 paypal: user@email.com"

Extract:
- **creators**: each creator mentioned with their username, number of posts owed, \
and total rate (dollar amount)
- **campaign_name**: the campaign or artist/song being referenced
- **notes**: anything that doesn't fit the above (special instructions, etc.)

Rules:
- Strip @ symbols from usernames
- Rates are TOTAL for all posts, not per-post
- If a PayPal email is mentioned next to a creator, include it
- If no campaign name is obvious, leave campaign_name empty
- If a message doesn't contain any booking information, return null

Respond with ONLY valid JSON (no markdown fences, no explanation). \
Return null if the message is not a booking."""

USER_TEMPLATE = """\
Parse this Slack message into a booking:

Message: {message}

Active campaigns for reference:
{campaigns}

Respond with JSON matching this schema:
{{
  "campaign_name": "string or empty",
  "creators": [
    {{
      "username": "string (no @ prefix)",
      "posts_owed": number,
      "total_rate": number,
      "paypal_email": "string or empty"
    }}
  ],
  "notes": "string or empty"
}}

Or respond with null if this is not a booking message."""


def parse_booking_message(
    raw_message: str,
    available_campaigns: List[Dict],
) -> Optional[Dict]:
    """Parse a raw Slack message into structured booking data.

    Returns a dict matching the /api/inbox POST body schema, or None if
    the message isn't a booking.
    """
    if not raw_message or not raw_message.strip():
        return None

    # Build campaign reference list for the prompt
    campaign_lines = []
    for c in available_campaigns:
        meta = c.get("meta", c)
        name = meta.get("title") or meta.get("name") or c.get("slug", "")
        artist = meta.get("artist", "")
        slug = c.get("slug", "")
        parts = [f"- {name}"]
        if artist:
            parts[0] += f" (artist: {artist})"
        if slug:
            parts[0] += f" [slug: {slug}]"
        campaign_lines.append(parts[0])

    campaigns_text = "\n".join(campaign_lines) if campaign_lines else "(none active)"

    user_msg = USER_TEMPLATE.format(
        message=raw_message,
        campaigns=campaigns_text,
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-haiku-4-20250414",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        text = response.content[0].text.strip()

        if text.lower() == "null" or not text:
            return None

        parsed = json.loads(text)
        if parsed is None:
            return None

        # Validate minimum structure
        creators = parsed.get("creators")
        if not creators or not isinstance(creators, list):
            log.warning("LLM returned no creators: %s", text)
            return None

        # Normalize creator fields
        for cr in creators:
            cr["username"] = str(cr.get("username", "")).strip().lstrip("@").lower()
            cr["posts_owed"] = int(cr.get("posts_owed", 0) or 0)
            cr["total_rate"] = float(cr.get("total_rate", 0) or 0)
            cr["paypal_email"] = str(cr.get("paypal_email", "") or "").strip()

        # Filter out creators with no username
        parsed["creators"] = [cr for cr in creators if cr["username"]]

        if not parsed["creators"]:
            return None

        return {
            "campaign_name": str(parsed.get("campaign_name", "") or ""),
            "creators": parsed["creators"],
            "notes": str(parsed.get("notes", "") or ""),
        }

    except json.JSONDecodeError as e:
        log.error("LLM returned invalid JSON: %s", e)
        return None
    except anthropic.APIError as e:
        log.error("Claude API error: %s", e)
        return None
    except Exception as e:
        log.error("Unexpected error parsing booking message: %s", e)
        return None
