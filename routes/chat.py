"""
Live chat routes:
  - GET  /chat/widget          Public widget page (embeddable or linked)
  - POST /chat/start           Visitor starts a session
  - GET  /chat/<token>         Visitor chat view (polling)
  - POST /chat/<token>/message Visitor sends message
  - GET  /chat/<token>/poll    JSON poll for new messages (visitor)
  - GET  /admin/chat           Agent inbox
  - GET  /admin/chat/<id>      Agent chat session view
  - POST /admin/chat/<id>/reply Agent replies
  - POST /admin/chat/<id>/assign Assign session to agent
  - POST /admin/chat/<id>/close Close + optionally create ticket
  - GET  /admin/chat/poll      JSON poll for new unread sessions
"""
from datetime import datetime

from flask import (
    Blueprint, render_template, redirect, url_for,
    request, jsonify, flash, current_app,
)
from flask_login import login_required, current_user

from models import db, ChatSession, ChatMessage, Ticket, User, Role, SLAPolicy, CSATRating
from utils import notify_staff, create_notification, log_history

chat = Blueprint("chat", __name__)


# ── Public widget ──────────────────────────────────────────────────────────────

@chat.route("/chat/widget")
def widget():
    return render_template("chat/widget.html")


@chat.route("/chat/start", methods=["POST"])
def start_session():
    name = request.form.get("name", "").strip() or "Visitor"
    email = request.form.get("email", "").strip()
    session = ChatSession(visitor_name=name, visitor_email=email or None)
    db.session.add(session)
    db.session.flush()
    db.session.add(ChatMessage(
        session_id=session.id,
        sender_type="agent",
        sender_name="Support Bot",
        body="👋 Hi! Thanks for reaching out. An agent will be with you shortly.",
    ))
    notify_staff(
        f"New live chat from {name} ({email or 'no email'})",
        notif_type="info",
    )
    db.session.commit()
    return redirect(url_for("chat.visitor_chat", token=session.token))


@chat.route("/chat/<token>")
def visitor_chat(token):
    session = ChatSession.query.filter_by(token=token).first_or_404()
    return render_template("chat/visitor.html", session=session)


@chat.route("/chat/<token>/message", methods=["POST"])
def visitor_message(token):
    session = ChatSession.query.filter_by(token=token).first_or_404()
    if session.status == "closed":
        return jsonify({"error": "Session closed"}), 400
    body = request.form.get("body", "").strip()
    if not body:
        return jsonify({"error": "Empty message"}), 400
    msg = ChatMessage(
        session_id=session.id,
        sender_type="visitor",
        sender_name=session.visitor_name,
        body=body,
    )
    db.session.add(msg)
    session.updated_at = datetime.utcnow()
    db.session.commit()
    if session.assigned_to_id:
        create_notification(
            session.assigned_to_id,
            f"New chat message from {session.visitor_name}",
            notif_type="info",
        )
        db.session.commit()
    return jsonify({"status": "ok", "id": msg.id})


@chat.route("/chat/<token>/poll")
def visitor_poll(token):
    session = ChatSession.query.filter_by(token=token).first_or_404()
    since_id = request.args.get("since", 0, type=int)
    msgs = ChatMessage.query.filter(
        ChatMessage.session_id == session.id,
        ChatMessage.id > since_id,
    ).order_by(ChatMessage.created_at).all()
    return jsonify({
        "status": session.status,
        "messages": [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "sender_name": m.sender_name,
                "body": m.body,
                "time": m.created_at.strftime("%H:%M"),
            }
            for m in msgs
        ],
    })


# ── Agent inbox ────────────────────────────────────────────────────────────────

@chat.route("/admin/chat")
@login_required
def agent_inbox():
    if not current_user.can_update_tickets():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    open_sessions = (
        ChatSession.query.filter(ChatSession.status != "closed")
        .order_by(ChatSession.updated_at.desc()).all()
    )
    unread_counts = {}
    for s in open_sessions:
        unread_counts[s.id] = ChatMessage.query.filter_by(
            session_id=s.id, sender_type="visitor", is_read=False
        ).count()
    return render_template(
        "chat/agent_inbox.html",
        sessions=open_sessions,
        unread_counts=unread_counts,
    )


@chat.route("/admin/chat/<int:session_id>")
@login_required
def agent_session(session_id):
    if not current_user.can_update_tickets():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    session = ChatSession.query.get_or_404(session_id)
    # Mark visitor messages as read
    ChatMessage.query.filter_by(
        session_id=session_id, sender_type="visitor", is_read=False
    ).update({"is_read": True})
    db.session.commit()
    agents = User.query.filter(
        User.role.in_([Role.AGENT, Role.ADMIN, Role.SUPER_ADMIN]), User.is_active == True
    ).all()
    return render_template("chat/agent_session.html", session=session, agents=agents)


@chat.route("/admin/chat/<int:session_id>/reply", methods=["POST"])
@login_required
def agent_reply(session_id):
    if not current_user.can_update_tickets():
        return jsonify({"error": "Forbidden"}), 403
    session = ChatSession.query.get_or_404(session_id)
    body = request.form.get("body", "").strip()
    if not body:
        flash("Reply cannot be empty.", "warning")
        return redirect(url_for("chat.agent_session", session_id=session_id))
    db.session.add(ChatMessage(
        session_id=session.id,
        sender_type="agent",
        sender_name=current_user.full_name,
        body=body,
        is_read=True,
    ))
    session.updated_at = datetime.utcnow()
    if session.status == "open":
        session.status = "assigned"
        session.assigned_to_id = current_user.id
    db.session.commit()
    flash("Reply sent.", "success")
    return redirect(url_for("chat.agent_session", session_id=session_id))


@chat.route("/admin/chat/<int:session_id>/assign", methods=["POST"])
@login_required
def assign_session(session_id):
    if not current_user.can_update_tickets():
        flash("Access denied.", "danger")
        return redirect(url_for("chat.agent_inbox"))
    session = ChatSession.query.get_or_404(session_id)
    agent_id = request.form.get("agent_id", type=int)
    if agent_id:
        session.assigned_to_id = agent_id
        session.status = "assigned"
        db.session.commit()
        flash("Session assigned.", "success")
    return redirect(url_for("chat.agent_session", session_id=session_id))


@chat.route("/admin/chat/<int:session_id>/close", methods=["POST"])
@login_required
def close_session(session_id):
    if not current_user.can_update_tickets():
        flash("Access denied.", "danger")
        return redirect(url_for("chat.agent_inbox"))
    session = ChatSession.query.get_or_404(session_id)
    session.status = "closed"
    session.updated_at = datetime.utcnow()

    if request.form.get("create_ticket") == "yes":
        transcript = "\n".join(
            f"[{m.sender_type.upper()}] {m.sender_name}: {m.body}"
            for m in session.messages
        )
        from datetime import timedelta
        ticket = Ticket(
            sl_no=Ticket.generate_sl_no(),
            channel="chat",
            issue_reporter_name=session.visitor_name,
            form_submit_email=session.visitor_email,
            issue_type="Live Chat",
            problem_details=transcript,
            priority="Medium",
        )
        db.session.add(ticket)
        db.session.flush()
        sla = SLAPolicy.query.filter_by(priority="Medium", is_active=True).first()
        if sla:
            ticket.due_date = datetime.utcnow() + timedelta(hours=sla.resolution_hours)
        db.session.add(CSATRating(ticket_id=ticket.id))
        session.ticket_id = ticket.id
        log_history(ticket.id, current_user.id, "Ticket created from live chat session")
        db.session.commit()
        flash(f"Session closed. Ticket {ticket.sl_no} created.", "success")
        return redirect(url_for("tickets.detail", ticket_id=ticket.id))

    db.session.commit()
    flash("Chat session closed.", "success")
    return redirect(url_for("chat.agent_inbox"))


@chat.route("/admin/chat/poll")
@login_required
def agent_poll():
    """Return unread session count for notification badge."""
    if not current_user.can_update_tickets():
        return jsonify({"unread": 0})
    unread = ChatSession.query.filter(
        ChatSession.status != "closed",
    ).join(ChatMessage, ChatMessage.session_id == ChatSession.id).filter(
        ChatMessage.sender_type == "visitor",
        ChatMessage.is_read == False,
    ).distinct().count()
    return jsonify({"unread": unread})
