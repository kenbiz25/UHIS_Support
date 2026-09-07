"""core/tickets/csat_sweep.py

Sends the "how did we do?" WhatsApp survey for BDSupport-created tickets
once the main app shows them resolved for at least CSAT_DELAY_MINUTES,
mirroring the native bot's own CSAT dispatch (app.py's _dispatch_wa_csat)
which explicitly excludes BDSupport tickets on the assumption BDSupport
handles this itself - this module is what makes that assumption true.

Actively polls the main app (core/tickets/main_app_client.get_ticket_status)
rather than waiting on BDSupport's own passively-cached ticket state, since
a resolution made in the ticketing UI never reaches this bot on its own -
the only way to notice it without the user having to message again is to
ask.

Called opportunistically from rag/flow.py on inbound traffic (throttled -
see _should_run below), and also runnable directly as a scheduled job via
scripts/sweep_csat.py for a timelier, more reliable cadence than
"whenever someone happens to message the bot" alone can guarantee.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from config.settings import settings
from core.contacts import state as contact_state
from core.i18n import t as _t
from core.tickets import csat_state
from core.tickets.main_app_client import get_ticket_status

logger = logging.getLogger(__name__)


def _last_sweep_path() -> Path:
    d = Path(__file__).resolve().parent / "csat_state"
    d.mkdir(parents=True, exist_ok=True)
    return d / "_last_sweep.txt"


def _should_run(min_interval_seconds: int = 300) -> bool:
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


_wa_service = None


def _whatsapp_service():
    """Lazily build a WhatsAppService using the same env vars app.py wires
    the bot's own instance from - the sweep isn't handed a BotFlow, so it
    can't reuse that instance directly."""
    global _wa_service
    if _wa_service is None:
        from core.whatsapp.whatsapp_service import WhatsAppService
        _wa_service = WhatsAppService(
            phone_id=os.getenv("WHATSAPP_PHONE_ID", ""),
            token=os.getenv("META_WHATSAPP_TOKEN", ""),
        )
    return _wa_service


def sweep_csat(max_age_minutes: float = None, force: bool = False) -> int:
    """Best-effort, throttled on the opportunistic path (see rag/flow.py);
    run scripts/sweep_csat.py on a real schedule (force=True) for a timely,
    reliable cadence independent of inbound bot traffic.

    Returns the number of CSAT prompts sent.
    """
    if not force and not _should_run():
        return 0

    max_age = max_age_minutes if max_age_minutes is not None else getattr(settings, "CSAT_DELAY_MINUTES", 60)
    sent = 0
    try:
        for phone, state in csat_state.iter_all():
            if state.get("prompted_at"):
                continue
            ticket_id = state.get("ticket_id")
            if not ticket_id:
                csat_state.clear(phone)
                continue

            info = get_ticket_status(ticket_id, phone)
            if not info:
                continue
            if info.get("csat_submitted"):
                csat_state.clear(phone)
                continue
            if info.get("status") not in ("Resolved", "Closed"):
                continue

            solved_date = info.get("solved_date")
            if not solved_date or _age_minutes(solved_date) < max_age:
                continue

            language = contact_state.get_language(phone) or "en"
            prompt = _t("csat_prompt", language).format(ref=state.get("sl_no") or ticket_id)
            try:
                _whatsapp_service().send_message(phone, message=prompt)
                csat_state.mark_prompted(phone)
                sent += 1
            except Exception:
                logger.exception("Failed to send CSAT prompt to %s", phone)
    except Exception:
        logger.exception("sweep_csat failed")
    return sent
