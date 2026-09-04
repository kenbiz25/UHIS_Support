"""Shared WhatsApp send helpers - Meta Cloud API + Twilio, provider-aware.

Single source of truth for outbound WhatsApp messages, used by
routes/webhooks.py (bot conversation + agent replies) and routes/nudges.py
(proactive aging/broadcast/CSAT nudges) so both respect WA_PROVIDER instead
of each hardcoding Meta only.
"""
import logging
import requests
from flask import current_app

logger = logging.getLogger(__name__)


def send_meta(phone, message):
    """Send a WhatsApp message via the Meta Cloud API."""
    token = current_app.config.get('WHATSAPP_TOKEN')
    phone_id = current_app.config.get('WHATSAPP_PHONE_ID')

    if not token or not phone_id:
        logger.warning(
            'send_meta: WHATSAPP_TOKEN or WHATSAPP_PHONE_ID not configured - message not sent.'
        )
        return False

    api_version = current_app.config.get('WHATSAPP_API_VERSION', 'v18.0')
    url = f'https://graph.facebook.com/{api_version}/{phone_id}/messages'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    payload = {
        'messaging_product': 'whatsapp',
        'to': phone,
        'type': 'text',
        'text': {'body': message},
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.warning('send_meta failed for %s: %s', phone, exc)
        return False


def send_twilio(phone, message):
    """Send a WhatsApp message via Twilio."""
    sid = current_app.config.get('TWILIO_ACCOUNT_SID')
    token = current_app.config.get('TWILIO_AUTH_TOKEN')
    from_number = current_app.config.get('TWILIO_WA_FROM')

    if not sid or not token:
        logger.warning(
            'send_twilio: TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not configured - message not sent.'
        )
        return False

    to_number = phone if phone.startswith('whatsapp:') else f'whatsapp:{phone}'

    try:
        resp = requests.post(
            f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',
            auth=(sid, token),
            data={'From': from_number, 'To': to_number, 'Body': message},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.warning('send_twilio failed for %s: %s', phone, exc)
        return False


def send(phone, message):
    """Send via whichever provider is configured (WA_PROVIDER=meta|twilio)."""
    provider = current_app.config.get('WA_PROVIDER', 'meta')
    if provider == 'twilio':
        return send_twilio(phone, message)
    return send_meta(phone, message)


def _relay_via_bd_support(phone, message):
    """Send a WhatsApp message through the standalone BDSupport bot service
    (its own Meta credentials/number, not this app's), for tickets raised via
    that bot. See models.is_bd_support_ticket / routes/bd_support_api.py.
    """
    base_url = current_app.config.get('BD_SUPPORT_BASE_URL')
    api_key = current_app.config.get('BD_SUPPORT_API_KEY')
    if not base_url or not api_key:
        logger.warning(
            '_relay_via_bd_support: BD_SUPPORT_BASE_URL or BD_SUPPORT_API_KEY not configured - message not sent.'
        )
        return False

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/internal/whatsapp/send",
            json={'phone': phone, 'message': message},
            headers={'X-API-Key': api_key},
            timeout=10,
        )
        resp.raise_for_status()
        return bool((resp.json() or {}).get('ok', True))
    except requests.RequestException as exc:
        logger.warning('_relay_via_bd_support failed for %s: %s', phone, exc)
        return False


def send_to_ticket(ticket, message):
    """Send an outbound WhatsApp update for a ticket, routed to whichever bot
    actually owns that phone conversation. channel=='whatsapp' alone doesn't
    tell you which bot/credentials to use - always send ticket replies
    through this instead of calling send()/_wa_send() directly with
    ticket.whatsapp_phone.
    """
    from models import is_bd_support_ticket

    if is_bd_support_ticket(ticket):
        return _relay_via_bd_support(ticket.whatsapp_phone, message)
    return send(ticket.whatsapp_phone, message)
