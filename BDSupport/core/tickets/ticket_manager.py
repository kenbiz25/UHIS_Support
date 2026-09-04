"""
core/tickets/ticket_manager.py

Creates support tickets in the main ticketing tool via main_app_client, so
agents can see and act on them. Falls back to appending a row to a local
Excel file (tickets.xlsx) via openpyxl only if that API call fails, so a
ticket is never silently lost when the two services can't reach each other.
Each Excel row: Ticket ID | Phone Number | Issue | Status | Created At
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import openpyxl
    _OPENPYXL_AVAILABLE = True
except ImportError:
    openpyxl = None  # type: ignore
    _OPENPYXL_AVAILABLE = False

_HEADERS = ["Ticket ID", "Phone Number", "Issue", "Conversation Summary", "Status", "Created At"]


def _ticket_path() -> Path:
    from config.settings import settings
    return Path(getattr(settings, "TICKET_FILE_PATH", "tickets.xlsx"))


def _init_workbook(path: Path) -> None:
    """Create the Excel file with headers if it doesn't exist."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Tickets"
    ws.append(_HEADERS)
    # Basic column widths for readability
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 60
    ws.column_dimensions["D"].width = 80
    ws.column_dimensions["E"].width = 10
    ws.column_dimensions["F"].width = 20
    wb.save(str(path))


def create_ticket(
    phone_number: str, issue: str, conversation_summary: str = "", status: str = "Open",
    name: str = "", division: str = "",
) -> Tuple[Optional[str], Optional[str]]:
    """
    Create a ticket in the main ticketing tool. Returns (ticket_id, sl_no) on
    success, (excel_ticket_id, None) if the API was unreachable and the
    Excel fallback was used instead, or (None, None) if both failed.

    Callers must check the ticket_id element, not the tuple itself — a
    2-tuple is always truthy even when both elements are None.
    """
    from core.tickets.main_app_client import create_ticket as _api_create_ticket

    ticket_id, sl_no = _api_create_ticket(phone_number, issue, conversation_summary, name=name, division=division, status=status)
    if ticket_id:
        return ticket_id, sl_no

    logger.warning("Ticketing API unavailable — falling back to Excel for %s", phone_number)
    excel_id = _create_ticket_excel(phone_number, issue, conversation_summary, status)
    return excel_id, None


def _create_ticket_excel(phone_number: str, issue: str, conversation_summary: str = "", status: str = "Open") -> Optional[str]:
    """
    Append a new ticket row to the Excel file and return the ticket ID.
    Returns None if openpyxl is not installed or write fails.
    """
    if not _OPENPYXL_AVAILABLE:
        logger.error("openpyxl is not installed — cannot create ticket. Run: pip install openpyxl")
        return None

    try:
        path = _ticket_path()
        _init_workbook(path)

        ticket_id = f"TKT-{str(uuid.uuid4())[:8].upper()}"
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        wb = openpyxl.load_workbook(str(path))
        ws = wb["Tickets"]
        ws.append([ticket_id, phone_number, issue[:500], conversation_summary[:2000], status, created_at])
        wb.save(str(path))

        logger.info("Ticket created (Excel fallback) | id=%s phone=%s", ticket_id, phone_number)
        return ticket_id

    except Exception:
        logger.exception("Failed to create Excel fallback ticket for %s", phone_number)
        return None
