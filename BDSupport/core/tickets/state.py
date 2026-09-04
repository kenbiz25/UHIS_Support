"""core/tickets/state.py

Tracks "does this WhatsApp phone currently have an open ticket, and which
one" as one small JSON file per phone - mirrors the one-file-per-key pattern
already used by core/memory/memory_service.py, but deliberately NOT stored
inside the conversation transcript. Scanning memory for a marker (e.g. a
"ticket_created" system message) degrades as the conversation grows, since
get_recent(limit=N) only returns the tail N lines - a long-running chat could
scroll the marker out of view and make the bot "forget" a ticket is open.
This file is the single source of truth instead, independent of memory.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


class TicketState(TypedDict):
    ticket_id: int
    sl_no: str
    status: str


def _state_dir() -> Path:
    d = Path(__file__).resolve().parent / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_path(phone: str) -> Path:
    safe = phone.replace("/", "_")
    return _state_dir() / f"{safe}.json"


def get_state(phone: str) -> Optional[TicketState]:
    path = _state_path(phone)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read ticket state for %s", phone)
        return None


def set_state(phone: str, ticket_id: int, sl_no: str, status: str) -> None:
    path = _state_path(phone)
    try:
        path.write_text(
            json.dumps({"ticket_id": ticket_id, "sl_no": sl_no, "status": status}),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("Failed to write ticket state for %s", phone)


def clear_state(phone: str) -> None:
    path = _state_path(phone)
    try:
        if path.exists():
            path.unlink()
    except Exception:
        logger.exception("Failed to clear ticket state for %s", phone)
