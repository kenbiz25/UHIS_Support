"""Internal API for the standalone BDSupport WhatsApp bot (FastAPI service,
lives in the sibling BDSupport/ project) to create/update tickets in this
app's database and forward chat messages as comments, so its conversations
show up here for agents to act on. See models.is_bd_support_ticket and
whatsapp_client.send_to_ticket for the corresponding outbound-reply side.

Auth: shared secret in the X-API-Key header, same value configured on the
BDSupport side as BD_SUPPORT_API_KEY. Not the generic API_KEY used by
/tickets/api/create - kept separate so it can be rotated independently.
"""
import hmac
import logging

from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.exc import IntegrityError

from extensions import limiter
from models import db, Ticket, TicketComment, User, AdminLevel1
from datetime import datetime

logger = logging.getLogger(__name__)

bd_support_api = Blueprint('bd_support_api', __name__, url_prefix='/api/bd-support')


def _check_api_key():
    api_key = request.headers.get('X-API-Key', '')
    expected = current_app.config.get('BD_SUPPORT_API_KEY', '')
    return bool(expected) and hmac.compare_digest(api_key, expected)


def _bot_user_id():
    bot = User.query.filter_by(username='bd-support-bot').first()
    return bot.id if bot else 1


def _external_id(phone):
    return f"bdsupport:{phone}"


def _resolve_division(division_name):
    """Best-effort match of a free-text division name (from the WhatsApp
    contact intake) to a seeded AdminLevel1 row. Returns None if blank or
    unmatched rather than erroring - division is optional, never blocks
    ticket creation."""
    if not division_name:
        return None
    return (
        AdminLevel1.query
        .filter(AdminLevel1.name.ilike(division_name.strip()))
        .first()
    )


def _find_open_ticket(phone):
    return (
        Ticket.query
        .filter_by(external_id=_external_id(phone))
        .filter(Ticket.current_status.notin_(["Resolved", "Closed"]))
        .order_by(Ticket.id.desc())
        .first()
    )


@bd_support_api.route('/tickets', methods=['POST'])
@limiter.limit('30 per minute')
def upsert_ticket():
    if not _check_api_key():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(force=True, silent=True) or {}
    phone = (data.get('phone') or '').strip()
    issue = (data.get('issue') or '').strip()
    if not phone or not issue:
        return jsonify({'error': 'phone and issue are required'}), 400

    name = (data.get('name') or phone).strip()
    division = (data.get('division') or '').strip()
    conversation_summary = (data.get('conversation_summary') or '').strip()

    existing = _find_open_ticket(phone)
    if existing:
        return jsonify({
            'ticket_id': existing.id,
            'sl_no': existing.sl_no,
            'status': 'existing',
        }), 200

    admin1 = _resolve_division(division)

    ticket = Ticket(
        channel='whatsapp',
        external_id=_external_id(phone),
        whatsapp_phone=phone,
        issue_reporter_name=name,
        issue_reporter_contact=phone,
        admin1_id=admin1.id if admin1 else None,
        country_id=admin1.country_id if admin1 else None,
        problem_details=issue,
        spice_platform='BD Support Bot',
        priority='Medium',
        current_status='Open',
        reporting_date=datetime.utcnow(),
        issue_start_date=datetime.utcnow(),
    )

    # generate_sl_no() is a non-atomic COUNT(*)-based counter - fine for the
    # human-paced native bot, but this endpoint is a bursty automated caller,
    # so retry on a unique-constraint collision instead of 500ing.
    for attempt in range(3):
        ticket.sl_no = Ticket.generate_sl_no()
        db.session.add(ticket)
        try:
            db.session.commit()
            break
        except IntegrityError:
            db.session.rollback()
            if attempt == 2:
                logger.error('upsert_ticket: sl_no collision persisted after 3 attempts for phone=%s', phone)
                return jsonify({'error': 'Could not allocate a ticket number, try again'}), 500

    if conversation_summary:
        db.session.add(TicketComment(
            ticket_id=ticket.id,
            author_id=_bot_user_id(),
            body=f"[WhatsApp] Conversation summary:\n{conversation_summary}",
        ))
        db.session.commit()

    logger.info('BDSupport ticket created | id=%s sl_no=%s phone=%s', ticket.id, ticket.sl_no, phone)
    return jsonify({'ticket_id': ticket.id, 'sl_no': ticket.sl_no, 'status': 'created'}), 201


@bd_support_api.route('/tickets/<int:ticket_id>/messages', methods=['POST'])
@limiter.limit('60 per minute')
def post_message(ticket_id):
    if not _check_api_key():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(force=True, silent=True) or {}
    phone = (data.get('phone') or '').strip()
    body = (data.get('body') or '').strip()
    sender = (data.get('sender') or 'user').strip()
    if not phone or not body:
        return jsonify({'error': 'phone and body are required'}), 400

    ticket = Ticket.query.get(ticket_id)
    # The shared API key alone doesn't prove which conversation a message
    # belongs to - require the phone to match the ticket it claims to be for,
    # so a bug or leaked key can't post onto an unrelated ticket.
    if not ticket or ticket.external_id != _external_id(phone):
        return jsonify({'error': 'Not found'}), 404

    db.session.add(TicketComment(
        ticket_id=ticket.id,
        author_id=_bot_user_id(),
        body=f"[WhatsApp] {sender}: {body}",
    ))
    db.session.commit()

    return jsonify({'ok': True, 'current_status': ticket.current_status}), 200
