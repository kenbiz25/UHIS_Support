"""core/contacts/state.py

Tracks the name/email/region a WhatsApp user has given us (or declined to
give), one small JSON file per phone - same one-file-per-key pattern as
core/tickets/state.py, and for the same reason: this needs to survive and
stay reachable independent of how far the conversation transcript has
scrolled, and independent of any single ticket's lifecycle (a contact should
still be known on a second ticket from the same phone, long after the first
one closed).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


class ContactInfo(TypedDict, total=False):
    name: str
    email: str
    division: str
    skipped: bool


def _state_dir() -> Path:
    d = Path(__file__).resolve().parent / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_path(phone: str) -> Path:
    safe = phone.replace("/", "_")
    return _state_dir() / f"{safe}.json"


def get_contact(phone: str) -> Optional[ContactInfo]:
    path = _state_path(phone)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read contact info for %s", phone)
        return None


def set_contact(phone: str, *, name: str = "", email: str = "", division: str = "", skipped: bool = False) -> None:
    path = _state_path(phone)
    try:
        path.write_text(
            json.dumps({"name": name, "email": email, "division": division, "skipped": skipped}),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("Failed to write contact info for %s", phone)


def has_been_asked(phone: str) -> bool:
    """True once we've either collected or been declined contact info."""
    return get_contact(phone) is not None
