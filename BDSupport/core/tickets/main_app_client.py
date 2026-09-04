"""core/tickets/main_app_client.py

HTTP client for the main Flask ticketing tool's internal BD-support API
(routes/bd_support_api.py in the sibling project). Called from rag/flow.py
whenever a conversation is handed off to a human, and on every subsequent
message while a ticket stays open, so the ticket in the tool reflects the
live WhatsApp conversation.

Both functions are best-effort: they never raise, they return a falsy/None
result on any failure so callers (flow.py) can fall back gracefully instead
of breaking the bot's reply path. Timeouts are kept short because
post_message() now sits in the hot path of every forwarded user message, not
just ticket creation.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 5.0


def _headers() -> dict:
    return {"X-API-Key": settings.BD_SUPPORT_API_KEY}


def _configured() -> bool:
    return bool(settings.MAIN_APP_BASE_URL and settings.BD_SUPPORT_API_KEY)


def create_ticket(
    phone: str, issue: str, conversation_summary: str,
    name: str = "", division: str = "",
) -> Tuple[Optional[int], Optional[str]]:
    """Create (or fetch the existing open) ticket for this phone.

    name/division come from the pre-answer contact intake (core/contacts/state.py)
    when the user provided them - blank if skipped, in which case the main app
    falls back to using the phone number as the reporter name.

    Returns (ticket_id, sl_no) on success, (None, None) if the ticketing
    tool couldn't be reached or is not configured.
    """
    if not _configured():
        logger.warning("main_app_client.create_ticket: MAIN_APP_BASE_URL/BD_SUPPORT_API_KEY not set")
        return None, None

    try:
        resp = httpx.post(
            f"{settings.MAIN_APP_BASE_URL.rstrip('/')}/api/bd-support/tickets",
            json={
                "phone": phone, "issue": issue, "conversation_summary": conversation_summary,
                "name": name or None, "division": division or None,
            },
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("ticket_id"), body.get("sl_no")
    except Exception:
        logger.exception("main_app_client.create_ticket failed for phone=%s", phone)
        return None, None


def post_message(ticket_id: int, phone: str, body: str, sender: str = "user") -> Optional[str]:
    """Forward a chat message onto an already-open ticket as a comment.

    Returns the ticket's current_status on success, None on any failure -
    callers should treat None as "unknown, keep polling next message" rather
    than "ticket closed."
    """
    if not _configured():
        return None

    try:
        resp = httpx.post(
            f"{settings.MAIN_APP_BASE_URL.rstrip('/')}/api/bd-support/tickets/{ticket_id}/messages",
            json={"phone": phone, "body": body, "sender": sender},
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("current_status")
    except Exception:
        logger.exception("main_app_client.post_message failed for ticket_id=%s phone=%s", ticket_id, phone)
        return None
