"""Slack bot integration using slack-bolt.

Listens for booking messages in the configured channel, parses them with
Claude, and feeds structured data into the Campaign Hub inbox pipeline.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from slack_bolt import App

from campaign_manager.services.llm import parse_booking_message

log = logging.getLogger(__name__)

_slack_app: Optional[App] = None


def init_slack_app() -> Optional[App]:
    """Initialize the Slack bolt app. Returns None if credentials aren't set."""
    global _slack_app

    token = os.environ.get("SLACK_BOT_TOKEN", "")
    secret = os.environ.get("SLACK_SIGNING_SECRET", "")

    if not token or not secret:
        log.info("Slack credentials not set, skipping Slack bot initialization")
        return None

    _slack_app = App(
        token=token,
        signing_secret=secret,
        # Process events only, don't start a socket listener
        process_before_response=True,
    )

    booking_channel = os.environ.get("SLACK_BOOKING_CHANNEL", "")

    @_slack_app.event("message")
    def handle_message(event, say):
        """Handle incoming channel messages."""
        # Ignore bot messages and message edits/deletes
        if event.get("bot_id") or event.get("subtype"):
            return

        # Only process messages in the configured booking channel
        if booking_channel and event.get("channel") != booking_channel:
            return

        text = event.get("text", "")
        if not text.strip():
            return

        log.info("Processing message: %.100s...", text)

        # Get available campaigns for context
        from campaign_manager.blueprints.campaigns import get_campaigns
        campaigns = get_campaigns()

        # Parse with LLM
        result = parse_booking_message(text, campaigns)
        if result is None:
            log.info("Message not recognized as a booking, skipping")
            return

        # Feed into inbox pipeline
        from campaign_manager.blueprints.inbox import create_inbox_item
        item = create_inbox_item(
            source="slack",
            raw_message=text,
            campaign_name=result.get("campaign_name", ""),
            creators=result.get("creators", []),
            notes=result.get("notes", ""),
        )

        log.info(
            "Created inbox item %s with %d creator(s) from Slack message",
            item["id"],
            len(result.get("creators", [])),
        )

    log.info("Slack bot initialized, listening on channel %s", booking_channel or "(all)")
    return _slack_app


def get_slack_app() -> Optional[App]:
    """Get the initialized Slack app, or None if not initialized."""
    return _slack_app
