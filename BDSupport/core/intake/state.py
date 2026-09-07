"""core/intake/state.py

Tracks an in-progress structured-intake Q&A (see core/intake/categories.py
and core/intake/engine.py), one small JSON file per phone - same
one-file-per-key pattern as core/tickets/state.py and
core/contacts/state.py, and for the same reason: this needs to survive and
stay reachable independent of how far the conversation transcript has
scrolled.

Storing `updated_at` here (rather than only in the memory transcript) is
also what lets core/intake/sweep.py find and finalize an intake a user
started and then went silent on, without having to scan every session's
conversation memory.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TypedDict

logger = logging.getLogger(__name__)


class IntakeState(TypedDict, total=False):
    category_id: str
    issue_type: str
    answers: Dict[str, str]
    current_index: int
    started_at: str
    updated_at: str


def _state_dir() -> Path:
    d = Path(__file__).resolve().parent / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_path(phone: str) -> Path:
    safe = phone.replace("/", "_")
    return _state_dir() / f"{safe}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start(phone: str, category_id: str, issue_type: str) -> IntakeState:
    state: IntakeState = {
        "category_id": category_id,
        "issue_type": issue_type,
        "answers": {},
        "current_index": 0,
        "started_at": _now(),
        "updated_at": _now(),
    }
    _write(phone, state)
    return state


def get(phone: str) -> Optional[IntakeState]:
    path = _state_path(phone)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read intake state for %s", phone)
        return None


def is_active(phone: str) -> bool:
    return get(phone) is not None


def record_answer(phone: str, key: str, value: str) -> Optional[IntakeState]:
    state = get(phone)
    if not state:
        return None
    state.setdefault("answers", {})[key] = value
    state["current_index"] = int(state.get("current_index", 0)) + 1
    state["updated_at"] = _now()
    _write(phone, state)
    return state


def clear(phone: str) -> None:
    path = _state_path(phone)
    try:
        if path.exists():
            path.unlink()
    except Exception:
        logger.exception("Failed to clear intake state for %s", phone)


def _write(phone: str, state: IntakeState) -> None:
    path = _state_path(phone)
    try:
        path.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        logger.exception("Failed to write intake state for %s", phone)


def iter_all() -> List[Tuple[str, IntakeState]]:
    """List every in-progress intake as (phone, state) - used by the stale
    sweep. Best-effort: unreadable files are skipped rather than raising."""
    out: List[Tuple[str, IntakeState]] = []
    try:
        for path in _state_dir().glob("*.json"):
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            out.append((path.stem, state))
    except Exception:
        logger.exception("Failed to list intake states")
    return out
