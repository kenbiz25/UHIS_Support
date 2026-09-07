"""core/intake/sweep.py

Safety net for the "user reports a problem, then goes silent" gap: a
structured intake left mid-way, or a handoff/RAG conversation that never
got an explicit close/resolution/decline, auto-becomes an Open ticket once
it's been quiet for STALE_TICKET_MINUTES - so it isn't silently lost.

Called opportunistically from rag/flow.py on inbound traffic (throttled -
see _should_run below), and also runnable directly as a scheduled job via
scripts/sweep_stale_conversations.py for a more reliable, timely sweep than
"whenever anyone else happens to message the bot" alone can guarantee.
"""
from __future__ import annotations

import glob
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from config.settings import settings
from core.intake import state as intake_state
from core.intake.engine import compile_partial

logger = logging.getLogger(__name__)


def _last_sweep_path() -> Path:
    d = Path(__file__).resolve().parent / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d / "_last_sweep.txt"


def _should_run(min_interval_seconds: int = 300) -> bool:
    """Throttle: a full directory scan on every single inbound message is
    unnecessary for a timeout measured in minutes - once every few minutes
    is plenty."""
    path = _last_sweep_path()
    now = datetime.now(timezone.utc).timestamp()
    try:
        if path.exists():
            last = float(path.read_text(encoding="utf-8").strip() or "0")
            if (now - last) < min_interval_seconds:
                return False
        path.write_text(str(now), encoding="utf-8")
        return True
    except Exception:
        return True


def _age_minutes(iso_ts: str) -> float:
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds() / 60.0
    except Exception:
        return 0.0


def _finalize_stale_intakes(max_age_minutes: float) -> int:
    """A structured intake (core/intake/state.py) the user never finished
    answering - create a ticket from whatever was captured so far."""
    from core.tickets import state as ticket_state
    from core.tickets.ticket_manager import create_ticket

    finalized = 0
    for phone, state in intake_state.iter_all():
        updated_at = state.get("updated_at") or state.get("started_at")
        if not updated_at or _age_minutes(updated_at) < max_age_minutes:
            continue

        issue_type = state.get("issue_type", "General/Other")
        issue_text = (
            compile_partial(state)
            + "\n\n(Auto-created: user did not finish answering before going silent.)"
        )
        try:
            ticket_id, sl_no = create_ticket(
                phone, issue_text, issue_text, status="Open", issue_type=issue_type,
            )
            if ticket_id:
                if sl_no:
                    ticket_state.set_state(phone, ticket_id, sl_no, "Open")
                finalized += 1
        except Exception:
            logger.exception("Failed to auto-finalize stale intake for %s", phone)
        intake_state.clear(phone)
    return finalized


def _sessions_dir() -> str:
    return os.path.join(os.getcwd(), "core", "memory", "sessions")


def _read_session_lines(path: str) -> List[dict]:
    out: List[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return out


def _finalize_stale_conversations(max_age_minutes: float) -> int:
    """Any conversation that reached the menu/RAG/handoff stage but never
    got an explicit close, resolution, decline, or ticket - and has gone
    quiet past the timeout - becomes an Open ticket. Structured-intake
    categories (1-4, 7) create their ticket immediately on completion and
    never reach this path unless abandoned mid-way (handled above); this
    covers category 5/6 (Get Help / Training) chats and any RAG handoff
    that was offered but never confirmed.
    """
    from core.tickets import state as ticket_state
    from core.tickets.ticket_manager import create_ticket
    from core.memory.memory_service import ConversationMemory

    finalized = 0
    sessions_dir = _sessions_dir()
    if not os.path.isdir(sessions_dir):
        return 0

    terminal_markers = {"ticket_created", "conversation_closed", "ticket_declined"}

    for path in glob.glob(os.path.join(sessions_dir, "*.jsonl")):
        session_id = os.path.splitext(os.path.basename(path))[0]
        lines = _read_session_lines(path)
        if not lines:
            continue

        last_ts = lines[-1].get("ts")
        if not last_ts or _age_minutes(last_ts) < max_age_minutes:
            continue

        markers = {m.get("text") for m in lines if m.get("role") == "system"}
        if markers & terminal_markers:
            continue
        if "menu_shown" not in markers:
            # Never even reached the menu - nothing reported yet to log.
            continue

        open_state = ticket_state.get_state(session_id)
        if open_state and open_state.get("status") not in ("Resolved", "Closed"):
            # Already has an open ticket - messages were already forwarded
            # onto it as they came in; nothing new to create.
            continue

        transcript = "\n".join(
            f"{m.get('role')}: {m.get('text', '')}" for m in lines if m.get("role") in ("user", "assistant")
        )
        if not transcript:
            continue

        note = (
            "(Auto-created: a support ticket was offered but never confirmed, "
            "and the conversation went quiet.)"
            if "ticket_pending" in markers else
            "(Auto-created: this conversation went quiet without an explicit "
            "resolution or close message.)"
        )
        issue_text = f"{transcript}\n\n{note}"

        try:
            ticket_id, sl_no = create_ticket(
                session_id, issue_text, issue_text, status="Open",
                issue_type="General/Chat (auto-closed)",
            )
            if ticket_id:
                if sl_no:
                    ticket_state.set_state(session_id, ticket_id, sl_no, "Open")
                ConversationMemory().save_message(session_id, "system", "ticket_created")
                finalized += 1
        except Exception:
            logger.exception("Failed to auto-finalize stale conversation for %s", session_id)

    return finalized


def sweep_stale(max_age_minutes: float = None, force: bool = False) -> int:
    """Best-effort safety net, called opportunistically on inbound traffic
    (see rag/flow.py) and throttled via _should_run since it's not
    time-critical on that path. For a timely, reliable sweep independent of
    whether anyone else happens to message the bot, run
    scripts/sweep_stale_conversations.py on a real schedule (cron / Task
    Scheduler) with force=True.

    Returns the number of tickets auto-created.
    """
    if not force and not _should_run():
        return 0
    max_age = max_age_minutes if max_age_minutes is not None else getattr(settings, "STALE_TICKET_MINUTES", 20)
    try:
        total = _finalize_stale_intakes(max_age)
        total += _finalize_stale_conversations(max_age)
        return total
    except Exception:
        logger.exception("sweep_stale failed")
        return 0
