"""core/contacts/state.py

Tracks the name/email/division/language a WhatsApp user has given us (or
declined to give), one small JSON file per phone - same one-file-per-key
pattern as core/tickets/state.py, and for the same reason: this needs to
survive and stay reachable independent of how far the conversation
transcript has scrolled, and independent of any single ticket's lifecycle
(a contact should still be known on a second ticket from the same phone,
long after the first one closed).

Language and contact info are two separate first-touch steps (language is
asked first, then contact details), so each has its own "have we asked yet"
flag in the same file rather than sharing one.
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
    contact_done: bool
    language: str


def _state_dir() -> Path:
    d = Path(__file__).resolve().parent / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_path(phone: str) -> Path:
    safe = phone.replace("/", "_")
    return _state_dir() / f"{safe}.json"


def _read(phone: str) -> dict:
    path = _state_path(phone)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read contact info for %s", phone)
        return {}


def _write(phone: str, data: dict) -> None:
    path = _state_path(phone)
    try:
        path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        logger.exception("Failed to write contact info for %s", phone)


def get_contact(phone: str) -> Optional[ContactInfo]:
    data = _read(phone)
    return data or None


def set_contact(phone: str, *, name: str = "", email: str = "", division: str = "", skipped: bool = False) -> None:
    """Records the resolved contact-intake step (given info or skipped).
    Merges into (rather than overwrites) any language preference already
    stored for this phone."""
    data = _read(phone)
    data.update({"name": name, "email": email, "division": division, "skipped": skipped, "contact_done": True})
    _write(phone, data)


def has_been_asked(phone: str) -> bool:
    """True once the contact-intake step has been resolved (given or skipped)."""
    return bool(_read(phone).get("contact_done"))


def get_language(phone: str) -> Optional[str]:
    """Returns the stored language preference ('en'/'bn'), or None if never set."""
    return _read(phone).get("language") or None


def set_language(phone: str, language: str) -> None:
    """Records the chosen language. Merges into (rather than overwrites) any
    contact info already stored for this phone."""
    data = _read(phone)
    data["language"] = language
    _write(phone, data)


def has_language_been_asked(phone: str) -> bool:
    """True once a language preference is stored for this phone."""
    return get_language(phone) is not None
