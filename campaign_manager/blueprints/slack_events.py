"""Slack Events API endpoint.

Receives event payloads from Slack's Events API and delegates to the
slack-bolt app for processing. Also handles the URL verification challenge
required during Slack app setup.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

slack_events_bp = Blueprint("slack_events", __name__, url_prefix="/api/webhooks/slack")


@slack_events_bp.post("/events")
def slack_events():
    """Handle Slack Events API requests.

    Two modes:
    1. URL verification: Slack sends a challenge during app setup,
       we echo it back to confirm the endpoint.
    2. Event delivery: Slack pushes event payloads, we delegate to slack-bolt.
    """
    body = request.get_json(silent=True) or {}

    # URL verification challenge (sent once during Slack app setup)
    if body.get("type") == "url_verification":
        return jsonify({"challenge": body.get("challenge", "")})

    # Delegate to slack-bolt handler
    from campaign_manager.services.slack_bot import get_slack_app
    slack_app = get_slack_app()

    if slack_app is None:
        return jsonify({"error": "Slack bot not initialized"}), 503

    from slack_bolt.adapter.flask import SlackRequestHandler
    handler = SlackRequestHandler(slack_app)
    return handler.handle(request)
