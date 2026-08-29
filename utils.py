import smtplib
import json
import urllib.request
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]
    )


# Magic bytes for common dangerous file types (zip/jar/exe/elf/pdf with macros warning)
_DANGEROUS_SIGNATURES = [
    b"MZ",           # Windows PE (exe, dll)
    b"\x7fELF",      # Linux ELF binary
    b"\xca\xfe\xba\xbe",  # Java class / Mach-O fat binary
    b"PK\x03\x04",   # ZIP-based (could be jar, apk — we block unless allowed ext)
]
_ZIP_EXTENSIONS = {"zip", "jar", "apk", "war"}


def scan_file_magic(file_storage):
    """Return (safe: bool, reason: str). Checks magic bytes of uploaded file."""
    header = file_storage.read(8)
    file_storage.seek(0)

    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""

    for sig in _DANGEROUS_SIGNATURES:
        if header.startswith(sig):
            if sig == b"PK\x03\x04" and ext in _ZIP_EXTENSIONS:
                continue  # allow zip if extension is explicitly zip
            return False, f"Rejected: file matches dangerous signature ({sig[:4]!r})"

    return True, "ok"


def send_notification(to_email, subject, body, html_body=None):
    """Send an email notification. Returns True on success, False on failure."""
    if not current_app.config.get("MAIL_USERNAME") or not current_app.config.get("MAIL_PASSWORD"):
        current_app.logger.warning("Email not configured — skipping notification.")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = current_app.config["MAIL_USERNAME"]
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(
            current_app.config["MAIL_SERVER"], current_app.config["MAIL_PORT"]
        ) as server:
            server.ehlo()
            if current_app.config["MAIL_USE_TLS"]:
                server.starttls()
            server.login(
                current_app.config["MAIL_USERNAME"],
                current_app.config["MAIL_PASSWORD"],
            )
            server.sendmail(
                current_app.config["MAIL_USERNAME"], to_email, msg.as_string()
            )
        return True
    except Exception as exc:
        current_app.logger.error(f"Email send failed to {to_email}: {exc}")
        return False


# ── Password reset tokens ──────────────────────────────────────────────────────

def generate_reset_token(email):
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return s.dumps(email, salt="password-reset-salt")


def verify_reset_token(token, max_age=3600):
    """Verify a password-reset token. Returns the email address or None."""
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        email = s.loads(token, salt="password-reset-salt", max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None
    return email


def send_reset_email(to_email, reset_url, full_name):
    subject = "Password Reset Request - Bangladesh UHIS"

    plain = f"""Hello {full_name},

You requested a password reset for your Bangladesh UHIS account.

Reset link (expires in 1 hour):
{reset_url}

If you did not request this, you can safely ignore this email.
Your password will not change until you click the link above and set a new one.

Bangladesh UHIS
"""

    html = f"""
<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">
  <div style="text-align:center;margin-bottom:24px;">
    <h2 style="color:#2514BE;margin:0;">Bangladesh UHIS</h2>
    <p style="color:#6c757d;font-size:14px;margin:4px 0 0;">Password Reset Request</p>
  </div>
  <div style="background:#f8f9fa;border-radius:8px;padding:24px;margin-bottom:24px;">
    <p style="margin-top:0;">Hello <strong>{full_name}</strong>,</p>
    <p>You requested a password reset for your account. Click the button below to set a new password.</p>
    <p style="text-align:center;margin:28px 0;">
      <a href="{reset_url}"
         style="background:#2514BE;color:#fff;padding:12px 28px;border-radius:6px;
                text-decoration:none;font-weight:600;display:inline-block;">
        Reset Password
      </a>
    </p>
    <p style="font-size:13px;color:#6c757d;margin-bottom:0;">
      This link expires in <strong>1 hour</strong>. If you did not request a reset,
      you can safely ignore this email.
    </p>
  </div>
  <p style="font-size:12px;color:#adb5bd;text-align:center;margin:0;">
    If the button doesn't work, copy and paste this URL:<br>
    <a href="{reset_url}" style="color:#2514BE;">{reset_url}</a>
  </p>
</div>
"""
    return send_notification(to_email, subject, plain, html_body=html)


def send_ticket_notification(to_email, full_name, sl_no, old_status, new_status, remarks):
    subject = f"Ticket {sl_no} - Status Update"

    plain = f"""Hello {full_name},

Your ticket {sl_no} has been updated.

Status: {old_status} -> {new_status}
Remarks: {remarks or 'No remarks added.'}

Log in to view the full ticket details.
"""

    html = f"""
<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">
  <div style="text-align:center;margin-bottom:24px;">
    <h2 style="color:#2514BE;margin:0;">Bangladesh UHIS</h2>
    <p style="color:#6c757d;font-size:14px;margin:4px 0 0;">Ticket Status Update</p>
  </div>
  <div style="background:#f8f9fa;border-radius:8px;padding:24px;">
    <p style="margin-top:0;">Hello <strong>{full_name}</strong>,</p>
    <p>Your ticket <strong>{sl_no}</strong> has been updated.</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;">
      <tr>
        <td style="padding:8px 12px;background:#e9ecef;border-radius:4px 0 0 4px;
                   font-weight:600;width:40%;">Previous Status</td>
        <td style="padding:8px 12px;background:#fff;border:1px solid #dee2e6;">{old_status}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;background:#e9ecef;font-weight:600;">New Status</td>
        <td style="padding:8px 12px;background:#fff;border:1px solid #dee2e6;color:#00A372;
                   font-weight:600;">{new_status}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;background:#e9ecef;border-radius:0 0 0 4px;font-weight:600;">Remarks</td>
        <td style="padding:8px 12px;background:#fff;border:1px solid #dee2e6;">
          {remarks or 'No remarks added.'}</td>
      </tr>
    </table>
  </div>
</div>
"""
    return send_notification(to_email, subject, plain, html_body=html)


# ── In-app notification helpers ────────────────────────────────────────────────

def create_notification(user_id, message, ticket_id=None, notif_type="info"):
    from models import db, Notification
    db.session.add(Notification(
        user_id=user_id, ticket_id=ticket_id, message=message, notif_type=notif_type,
    ))


def notify_staff(message, ticket_id=None, notif_type="info",
                 exclude_user_id=None, roles=None):
    from models import User, Role
    if roles is None:
        roles = [Role.SUPER_ADMIN, Role.ADMIN, Role.AGENT]
    for u in User.query.filter(User.role.in_(roles), User.is_active == True).all():
        if u.id != exclude_user_id:
            create_notification(u.id, message, ticket_id, notif_type)


def auto_route_ticket(ticket, level):
    """Assign `ticket` to the least-loaded active agent at `level` (1-4).

    Falls back to Admins if no agent at that tier is active. Returns the
    assigned User, or None if nobody was available.
    """
    from models import db, User, Role, Ticket

    candidates = User.query.filter(
        User.role == Role.AGENT, User.agent_level == level, User.is_active == True
    ).all()
    if not candidates:
        candidates = User.query.filter(User.role == Role.AGENT, User.is_active == True).all()
    if not candidates:
        candidates = User.query.filter(User.role == Role.ADMIN, User.is_active == True).all()
    if not candidates:
        return None

    best = min(
        candidates,
        key=lambda u: Ticket.query.filter(
            Ticket.assigned_to_id == u.id,
            Ticket.current_status.notin_(["Resolved", "Closed"]),
        ).count(),
    )
    ticket.assigned_to_id = best.id
    return best


def log_history(ticket_id, changed_by_id, action, old_value=None, new_value=None):
    from models import db, TicketHistory
    db.session.add(TicketHistory(
        ticket_id=ticket_id,
        changed_by_id=changed_by_id,
        action=action,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
    ))


# ── Slack notification ─────────────────────────────────────────────────────────

def notify_slack(message: str, ticket=None, level: str = "info") -> bool:
    """Post a message to the configured Slack incoming webhook."""
    url = current_app.config.get("SLACK_WEBHOOK_URL")
    if not url:
        return False
    color = {"danger": "#751A1A", "warning": "#C35721", "success": "#00A372"}.get(level, "#2514BE")
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": message}}]
    if ticket:
        blocks.append({"type": "context", "elements": [
            {"type": "mrkdwn", "text": f"*Ticket:* {ticket.sl_no} | *Priority:* {ticket.priority} | *Status:* {ticket.current_status}"}
        ]})
    payload = json.dumps({"attachments": [{"color": color, "blocks": blocks}]}).encode()
    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception as e:
        current_app.logger.warning(f"Slack notify failed: {e}")
        return False


# ── Microsoft Teams notification ───────────────────────────────────────────────

def notify_teams(message: str, ticket=None, level: str = "info") -> bool:
    """Post an Adaptive Card message to the configured Teams incoming webhook."""
    url = current_app.config.get("TEAMS_WEBHOOK_URL")
    if not url:
        return False
    theme_color = {"danger": "751A1A", "warning": "C35721", "success": "00A372"}.get(level, "2514BE")
    body = [{"type": "TextBlock", "text": message, "wrap": True}]
    if ticket:
        body.append({"type": "TextBlock", "wrap": True, "isSubtle": True,
                     "text": f"Ticket: {ticket.sl_no} | Priority: {ticket.priority} | Status: {ticket.current_status}"})
    payload = json.dumps({
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "msteams": {"width": "Full"},
                "body": body,
            }
        }]
    }).encode()
    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception as e:
        current_app.logger.warning(f"Teams notify failed: {e}")
        return False


# ── Real-time translation ──────────────────────────────────────────────────────

def translate_text(text: str, target_lang: str, source_lang: str = "auto") -> str:
    """Translate text using the configured provider. Returns translated string or original on failure."""
    provider = current_app.config.get("TRANSLATE_PROVIDER", "google")
    if provider == "google":
        api_key = current_app.config.get("TRANSLATE_API_KEY")
        if not api_key:
            return text
        try:
            params = urllib.parse.urlencode({
                "q": text, "target": target_lang,
                "source": "" if source_lang == "auto" else source_lang,
                "key": api_key, "format": "text",
            }).encode()
            req = urllib.request.Request(
                "https://translation.googleapis.com/language/translate/v2",
                data=params, method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                result = json.loads(resp.read())
            return result["data"]["translations"][0]["translatedText"]
        except Exception as e:
            current_app.logger.warning(f"Google Translate failed: {e}")
            return text

    elif provider == "libretranslate":
        base = current_app.config.get("LIBRETRANSLATE_URL", "http://localhost:5000")
        try:
            payload = json.dumps({
                "q": text, "source": source_lang if source_lang != "auto" else "auto",
                "target": target_lang, "format": "text",
            }).encode()
            req = urllib.request.Request(
                f"{base}/translate", data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                result = json.loads(resp.read())
            return result.get("translatedText", text)
        except Exception as e:
            current_app.logger.warning(f"LibreTranslate failed: {e}")
            return text

    return text


# ── Automation Rules Engine ────────────────────────────────────────────────────

def run_automation_rules(ticket, event: str, current_user_id=None):
    """Execute all active automation rules that match the given trigger event and ticket state."""
    from models import AutomationRule, Tag, User, TicketComment, Notification
    rules = (
        AutomationRule.query
        .filter_by(is_active=True, trigger_event=event)
        .order_by(AutomationRule.run_order)
        .all()
    )
    for rule in rules:
        if not _eval_conditions(ticket, rule.conditions_json or []):
            continue
        _apply_actions(ticket, rule.actions_json or [], current_user_id)
        if not rule.continue_on_match:
            break
    try:
        from models import db
        db.session.flush()
    except Exception:
        pass


def _eval_conditions(ticket, conditions):
    if not conditions:
        return True
    for cond in conditions:
        field = cond.get("field", "")
        op = cond.get("operator", "eq")
        value = cond.get("value", "")
        actual = _get_ticket_field(ticket, field)
        if not _compare(actual, op, value):
            return False
    return True


def _get_ticket_field(ticket, field):
    mapping = {
        "priority": ticket.priority,
        "current_status": ticket.current_status,
        "channel": ticket.channel,
        "category_id": str(ticket.category_id or ""),
        "issue_type": ticket.issue_type or "",
        "problem_details": ticket.problem_details or "",
        "escalation_level": str(ticket.escalation_level),
        "assigned_to_id": str(ticket.assigned_to_id or ""),
    }
    return mapping.get(field, "")


def _compare(actual, operator, value):
    actual_l = str(actual).lower()
    value_l = str(value).lower()
    if operator == "eq":
        return actual_l == value_l
    if operator == "neq":
        return actual_l != value_l
    if operator == "contains":
        return value_l in actual_l
    if operator == "not_contains":
        return value_l not in actual_l
    if operator == "gt":
        try:
            return float(actual) > float(value)
        except (ValueError, TypeError):
            return False
    if operator == "lt":
        try:
            return float(actual) < float(value)
        except (ValueError, TypeError):
            return False
    return False


def _apply_actions(ticket, actions, actor_id=None):
    from models import db, Tag, User, TicketComment, Role
    from datetime import datetime
    for action in actions:
        atype = action.get("type", "")
        params = action.get("params", {})
        try:
            if atype == "set_priority":
                ticket.priority = params.get("priority", ticket.priority)
            elif atype == "set_status":
                ticket.current_status = params.get("status", ticket.current_status)
            elif atype == "assign_to":
                uid = params.get("user_id")
                if uid:
                    ticket.assigned_to_id = int(uid)
            elif atype == "escalate":
                level = int(params.get("level", 1))
                if level > ticket.escalation_level:
                    ticket.escalation_level = level
            elif atype == "add_tag":
                tag_id = params.get("tag_id")
                if tag_id:
                    tag = Tag.query.get(int(tag_id))
                    if tag and tag not in ticket.tags.all():
                        ticket.tags.append(tag)
            elif atype == "add_internal_note":
                body = params.get("body", "").strip()
                if body and actor_id:
                    note = TicketComment(
                        ticket_id=ticket.id,
                        author_id=actor_id,
                        body=f"[Automation] {body}",
                        is_internal=True,
                    )
                    db.session.add(note)
            elif atype == "notify_staff":
                msg = params.get("message", "").strip()
                if msg:
                    notify_staff(
                        f"[Automation] {msg} — Ticket {ticket.sl_no}",
                        ticket_id=ticket.id,
                        notif_type="info",
                    )
            elif atype == "send_email_reporter":
                subject = params.get("subject", "Update on your support ticket")
                body = params.get("body", "Your ticket has been updated.")
                if ticket.form_submit_email:
                    send_notification(
                        ticket.form_submit_email,
                        subject.replace("{sl_no}", ticket.sl_no or ""),
                        body.replace("{sl_no}", ticket.sl_no or ""),
                    )
        except Exception:
            pass
