"""core/tickets/csat_state.py

Tracks "does this phone have a ticket awaiting a CSAT rating, and have we
already asked" - one small JSON file per phone, same pattern as
core/tickets/state.py, but deliberately a SEPARATE file/lifecycle from it.

core/tickets/state.py ("is there an open ticket to forward messages onto")
gets cleared the moment BDSupport learns a ticket resolved, which normally
only happens when the user sends another message - exactly the case where
a proactive CSAT survey is needed most (the user went quiet after being
helped). Tying CSAT tracking to that same file would mean losing the
ticket_id right when core/tickets/csat_sweep.py needs it, so this tracks
every BDSupport-created ticket from the moment of creation, independent of
whatever core/tickets/state.py is doing with it, until a rating is in hand
(or too much time has passed to bother).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TypedDict

logger = logging.getLogger(__name__)


class CsatState(TypedDict, total=False):
    ticket_id: int
    sl_no: str
    created_at: str
    prompted_at: str  # absent until the "please rate" message has been sent


def _state_dir() -> Path:
    d = Path(__file__).resolve().parent / "csat_state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_path(phone: str) -> Path:
    safe = phone.replace("/", "_")
    return _state_dir() / f"{safe}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start(phone: str, ticket_id: int, sl_no: str) -> None:
    """Begin CSAT tracking for a just-created ticket. Safe to call for every
    ticket BDSupport creates - the sweep only acts once the main app reports
    the ticket as resolved."""
    _write(phone, {"ticket_id": ticket_id, "sl_no": sl_no, "created_at": _now()})


def get(phone: str) -> Optional[CsatState]:
    path = _state_path(phone)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read CSAT state for %s", phone)
        return None


def mark_prompted(phone: str) -> None:
    state = get(phone)
    if not state:
        return
    state["prompted_at"] = _now()
    _write(phone, state)


def clear(phone: str) -> None:
    path = _state_path(phone)
    try:
        if path.exists():
            path.unlink()
    except Exception:
        logger.exception("Failed to clear CSAT state for %s", phone)


def _write(phone: str, state: Dict) -> None:
    path = _state_path(phone)
    try:
        path.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        logger.exception("Failed to write CSAT state for %s", phone)


def iter_all() -> List[Tuple[str, CsatState]]:
    """List every phone with CSAT tracking in progress, as (phone, state) -
    used by core/tickets/csat_sweep.py. Best-effort: unreadable files are
    skipped rather than raising."""
    out: List[Tuple[str, CsatState]] = []
    try:
        for path in _state_dir().glob("*.json"):
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            out.append((path.stem, state))
    except Exception:
        logger.exception("Failed to list CSAT states")
    return out
