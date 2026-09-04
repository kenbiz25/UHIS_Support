from flask import Blueprint, request, jsonify, render_template, current_app, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Ticket, WhatsAppSession, CSATRating, TicketComment, NudgeLog, Role, User
from datetime import datetime
from whatsapp_client import send as _wa_send
import logging

logger = logging.getLogger(__name__)

webhooks = Blueprint('webhooks', __name__)


def _get_wa_verify_token():
    return current_app.config.get('WHATSAPP_VERIFY_TOKEN', '')


# ---------------------------------------------------------------------------
# Verification handshake
# ---------------------------------------------------------------------------

@webhooks.route('/webhooks/whatsapp', methods=['GET'])
def whatsapp_verify():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')

    if mode == 'subscribe' and token == _get_wa_verify_token():
        return challenge, 200

    return jsonify({'error': 'Forbidden'}), 403


# ---------------------------------------------------------------------------
# Incoming message handler
# ---------------------------------------------------------------------------

@webhooks.route('/webhooks/whatsapp', methods=['POST'])
def whatsapp_incoming():
    try:
        data = request.get_json(force=True, silent=True) or {}
        entries = data.get('entry', [])
        if not entries:
            return jsonify({'status': 'ok'}), 200

        changes = entries[0].get('changes', [])
        if not changes:
            return jsonify({'status': 'ok'}), 200

        value = changes[0].get('value', {})
        messages = value.get('messages', [])
        if not messages:
            return jsonify({'status': 'ok'}), 200

        msg = messages[0]
        phone = msg.get('from', '')
        body = (msg.get('text') or {}).get('body', '').strip()

        contacts = value.get('contacts', [])
        name = contacts[0].get('profile', {}).get('name', phone) if contacts else phone

        if phone and body:
            _handle_wa_message(phone, body, name)

    except Exception as exc:
        logger.exception('whatsapp_incoming unhandled error: %s', exc)

    return jsonify({'status': 'ok'}), 200


@webhooks.route('/webhooks/whatsapp/twilio', methods=['POST'])
def whatsapp_twilio_incoming():
    """Twilio WhatsApp inbound webhook - same state machine as the Meta handler."""
    try:
        phone = request.form.get('From', '').replace('whatsapp:', '').strip()
        body = request.form.get('Body', '').strip()
        name = request.form.get('ProfileName', '').strip() or phone

        if phone and body:
            _handle_wa_message(phone, body, name)
    except Exception as exc:
        logger.exception('whatsapp_twilio_incoming unhandled error: %s', exc)

    return '', 204


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

_GREETING_KEYWORDS = {'hi', 'hello', 'help', 'start'}

_APP_MAP = {
    '1': 'SPICE',
    '2': 'Tiberbu',
    '3': 'Afyangu',
    '4': 'Other',
}

_GREETING_MESSAGE = (
    "Hello {name}! Welcome to Medtronic LABS Support \U0001f3e5\n"
    "Which application do you need help with?\n"
    "1️⃣ SPICE\n"
    "2️⃣ Tiberbu\n"
    "3️⃣ Afyangu\n"
    "4️⃣ Other\n"
    "Reply with the number (1–4)"
)


def _get_or_create_session(phone):
    session = WhatsAppSession.query.get(phone)
    if session is None:
        session = WhatsAppSession(phone=phone, state='INIT', data={})
        db.session.add(session)
        db.session.flush()
    return session


def _handle_wa_message(phone, body, name):
    session = _get_or_create_session(phone)
    body_lower = body.lower().strip()

    # Any greeting keyword resets to INIT flow regardless of current state
    if body_lower in _GREETING_KEYWORDS:
        session.state = 'INIT'

    state = session.state

    if state == 'INIT':
        session.state = 'CHOOSE_APP'
        session.data = {'name': name}
        session.updated_at = datetime.utcnow()
        db.session.commit()
        _wa_send(phone, _GREETING_MESSAGE.format(name=name))
        return

    if state == 'CHOOSE_APP':
        chosen = _APP_MAP.get(body.strip())
        if not chosen:
            _wa_send(phone, 'Please reply with a number between 1 and 4.')
            return
        data = dict(session.data or {})
        data['app'] = chosen
        session.data = data
        session.state = 'DESCRIBE'
        session.updated_at = datetime.utcnow()
        db.session.commit()
        _wa_send(
            phone,
            f'Got it — {chosen}. Please describe your issue in as much detail as possible.'
        )
        return

    if state == 'DESCRIBE':
        data = dict(session.data or {})
        data['description'] = body
        session.data = data
        session.state = 'CONFIRM'
        session.updated_at = datetime.utcnow()
        db.session.commit()
        preview = body[:100]
        summary = (
            f'Here is your ticket summary:\n'
            f'App: {data.get("app", "")}\n'
            f'Issue: {preview}{"..." if len(body) > 100 else ""}\n\n'
            f'Submit this ticket? Reply YES to confirm or NO to cancel.'
        )
        _wa_send(phone, summary)
        return

    if state == 'CONFIRM':
        answer = body.strip().upper()
        if answer == 'YES':
            ticket = _create_wa_ticket(session)
            session.state = 'OPEN'
            data = dict(session.data or {})
            data['ticket_id'] = ticket.id
            data['sl_no'] = ticket.sl_no
            session.data = data
            session.updated_at = datetime.utcnow()
            db.session.commit()
            _wa_send(
                phone,
                f'Your ticket has been created! ✅\n'
                f'Ticket ID: {ticket.sl_no}\n'
                f'We will get back to you shortly. Reply STATUS at any time to check your ticket status.'
            )
        elif answer == 'NO':
            session.state = 'INIT'
            session.data = {}
            session.updated_at = datetime.utcnow()
            db.session.commit()
            _wa_send(
                phone,
                'Your ticket has been cancelled. Reply Hi to start again.'
            )
        else:
            _wa_send(phone, 'Please reply YES to submit your ticket or NO to cancel.')
        return

    if state == 'OPEN':
        data = dict(session.data or {})
        ticket_id = data.get('ticket_id')

        if body.strip().upper() == 'STATUS':
            if ticket_id:
                ticket = Ticket.query.get(ticket_id)
                if ticket:
                    solved_info = ''
                    if ticket.current_status and ticket.current_status.lower() in ('resolved', 'closed'):
                        solved_info = f'\nResolved/Closed.'
                    _wa_send(
                        phone,
                        f'Ticket: {ticket.sl_no}\n'
                        f'Status: {ticket.current_status}\n'
                        f'Priority: {ticket.priority}'
                        f'{solved_info}'
                    )
                else:
                    _wa_send(phone, 'Could not find your ticket. Please contact support.')
            else:
                _wa_send(phone, 'No open ticket found for your account.')
        else:
            if ticket_id:
                comment_body = f'[WhatsApp] {name}: {body}'
                system_user = User.query.filter_by(username='whatsapp-bot').first()
                sys_id = system_user.id if system_user else 1
                comment = TicketComment(
                    ticket_id=ticket_id,
                    author_id=sys_id,
                    body=comment_body,
                )
                db.session.add(comment)
                db.session.commit()
                _wa_send(
                    phone,
                    'Your message has been added to your ticket. Our support team will respond shortly.'
                )
            else:
                _wa_send(
                    phone,
                    'No open ticket found. Reply Hi to create a new ticket.'
                )
        return

    if state == 'CSAT_PENDING':
        rating_str = body.strip()
        if rating_str in ('1', '2', '3', '4', '5'):
            rating_val = int(rating_str)
            data = dict(session.data or {})
            ticket_id = data.get('ticket_id')
            nudge_id = data.get('nudge_id')

            if ticket_id:
                existing = CSATRating.query.filter_by(ticket_id=ticket_id).first()
                if not existing:
                    csat = CSATRating(
                        ticket_id=ticket_id,
                        rating=rating_val,
                        submitted_at=datetime.utcnow(),
                    )
                    db.session.add(csat)

            if nudge_id:
                nudge = NudgeLog.query.get(nudge_id)
                if nudge:
                    nudge.status = 'responded'
                    nudge.response = rating_str
                    nudge.responded_at = datetime.utcnow()

            session.state = 'INIT'
            session.data = {}
            session.updated_at = datetime.utcnow()
            db.session.commit()
            _wa_send(
                phone,
                f'Thank you for your feedback! You rated us {rating_val}/5. \U0001f64f'
            )
        else:
            _wa_send(phone, 'Please reply with a number between 1 and 5 to rate your experience.')
        return

    # Fallback — unknown state, reset
    session.state = 'INIT'
    session.data = {}
    session.updated_at = datetime.utcnow()
    db.session.commit()
    _wa_send(phone, 'Reply Hi to start a new support session.')


# ---------------------------------------------------------------------------
# Ticket creation helper
# ---------------------------------------------------------------------------

def _create_wa_ticket(session):
    data = session.data or {}
    phone = session.phone
    name = data.get('name', phone)
    description = data.get('description', '')
    app = data.get('app', '')

    ticket = Ticket(
        channel='whatsapp',
        sl_no=Ticket.generate_sl_no(),
        issue_reporter_name=name,
        issue_reporter_contact=phone,
        problem_details=description,
        spice_platform=app,
        whatsapp_phone=phone,
        current_status='Open',
        priority='Medium',
        reporting_date=datetime.utcnow(),
        issue_start_date=datetime.utcnow(),
    )
    db.session.add(ticket)
    db.session.flush()
    return ticket


# ---------------------------------------------------------------------------
# Agent reply endpoint
# ---------------------------------------------------------------------------

@webhooks.route('/webhooks/whatsapp/reply/<int:ticket_id>', methods=['POST'])
@login_required
def whatsapp_agent_reply(ticket_id):
    if current_user.role not in (Role.SUPER_ADMIN, Role.ADMIN, Role.AGENT):
        return jsonify({'ok': False, 'error': 'Forbidden'}), 403

    payload = request.get_json(force=True, silent=True) or {}
    message = (payload.get('message') or '').strip()
    phone = (payload.get('phone') or '').strip()

    if not message or not phone:
        return jsonify({'ok': False, 'error': 'message and phone are required'}), 400

    ticket = Ticket.query.get_or_404(ticket_id)

    from whatsapp_client import send_to_ticket
    sent = send_to_ticket(ticket, message)

    comment = TicketComment(
        ticket_id=ticket.id,
        author_id=current_user.id,
        body=f'[Agent WhatsApp reply to {phone}]: {message}',
    )
    db.session.add(comment)
    db.session.commit()

    # sent=False means the comment was saved but delivery failed - callers
    # must not treat this response as a plain success (see whatsapp_inbox.html
    # / ticket_detail.html's WhatsApp reply panel, which surfaces this).
    return jsonify({'ok': True, 'sent': sent})


# ---------------------------------------------------------------------------
# WhatsApp inbox view
# ---------------------------------------------------------------------------

@webhooks.route('/admin/whatsapp')
@login_required
def whatsapp_inbox():
    if current_user.role not in (Role.SUPER_ADMIN, Role.ADMIN, Role.AGENT):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.index'))

    sessions = (
        WhatsAppSession.query
        .order_by(WhatsAppSession.updated_at.desc())
        .all()
    )

    session_data = []
    for sess in sessions:
        data = sess.data or {}
        ticket_id = data.get('ticket_id')
        ticket = Ticket.query.get(ticket_id) if ticket_id else None
        session_data.append({'session': sess, 'ticket': ticket})

    return render_template('admin/whatsapp_inbox.html', session_data=session_data)
