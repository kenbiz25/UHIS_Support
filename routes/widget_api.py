import json
from flask import Blueprint, request, jsonify, current_app, make_response
from models import (
    db, Ticket, KBArticle, KBCategory, CSATRating,
    BrandingSettings, IssueCategory, Country, TicketComment,
)
from datetime import datetime

widget_api = Blueprint("widget_api", __name__, url_prefix="/widget")

MAX_HISTORY_TURNS = 12
FALLBACK_ESCALATE_TURNS = 2  # user turns before we ask for contact info when no AI key is set


# ── CORS ────────────────────────────────────────────────────────────────────────

def _cors_origin():
    """Return the Access-Control-Allow-Origin value for the current request.

    When WIDGET_ALLOWED_ORIGINS is '*' (default) every origin is allowed.
    Otherwise only origins in the comma-separated allowlist are reflected;
    unrecognised origins get no CORS header and the browser will block them.
    """
    allowed = current_app.config.get("WIDGET_ALLOWED_ORIGINS", "*").strip()
    if allowed == "*":
        return "*"
    origin = request.headers.get("Origin", "")
    allowed_set = {o.strip() for o in allowed.split(",") if o.strip()}
    return origin if origin in allowed_set else None


@widget_api.after_request
def add_cors_headers(response):
    origin = _cors_origin()
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        if origin != "*":
            response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Widget-Token"
    return response


@widget_api.route("/<path:subpath>", methods=["OPTIONS"])
@widget_api.route("/", methods=["OPTIONS"])
def handle_options(subpath=None):
    return jsonify({}), 200


# ── GET /widget/config ──────────────────────────────────────────────────────────

@widget_api.route("/config", methods=["GET"])
def widget_config():
    branding = BrandingSettings.get()
    categories = KBCategory.query.filter_by(is_active=True).order_by(KBCategory.display_order).all()
    countries = Country.query.filter_by(is_active=True).order_by(Country.name).all()

    return jsonify({
        "app_name": branding.app_name,
        "primary_color": branding.primary_color,
        "categories": [
            {"id": c.id, "name": c.name, "icon": c.icon}
            for c in categories
        ],
        "countries": [
            {"id": co.id, "name": co.name, "code": co.code}
            for co in countries
        ],
    })


# ── GET /widget/search ──────────────────────────────────────────────────────────

@widget_api.route("/search", methods=["GET"])
def widget_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})

    pattern = f"%{q}%"
    articles = (
        KBArticle.query
        .filter(
            KBArticle.is_published == True,
            db.or_(
                KBArticle.title.ilike(pattern),
                KBArticle.body_html.ilike(pattern),
            ),
        )
        .limit(5)
        .all()
    )

    results = []
    for a in articles:
        results.append({
            "id": a.id,
            "title": a.title,
            "slug": a.slug,
            "meta_description": a.meta_description,
            "category_name": a.category.name if a.category else None,
        })

    return jsonify({"results": results})


# ── POST /widget/ai-chat ────────────────────────────────────────────────────────

def _kb_context():
    """Compact reference list of published KB articles, used to ground AI replies."""
    articles = KBArticle.query.filter_by(is_published=True).limit(40).all()
    lines = []
    for a in articles:
        desc = (a.meta_description or "").strip()
        lines.append(f"- {a.title}: {desc}" if desc else f"- {a.title}")
    return "\n".join(lines)


def _fallback_ai_reply(message, history, branding):
    """No OPENAI_API_KEY configured (or the AI call failed): a simple guided
    intake that still always reaches a ticket - describe the issue for a
    couple of turns, then ask for contact info."""
    user_turns = [h for h in history if h.get("role") == "user"] + [{"content": message}]
    if len(user_turns) < FALLBACK_ESCALATE_TURNS:
        return {
            "reply": "Thanks for reaching out. Could you share a few more details about the issue so I can log it accurately for our team?",
            "escalate": False,
        }
    summary = " ".join((t.get("content") or "").strip() for t in user_turns).strip()
    return {
        "reply": "Got it - I've put together a summary of your issue. Please share your name and phone number or email so our support team can follow up.",
        "escalate": True,
        "summary": summary[:2000],
    }


@widget_api.route("/ai-chat", methods=["POST"])
def ai_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []
    if not isinstance(history, list):
        history = []
    history = history[-MAX_HISTORY_TURNS:]

    if not message:
        return jsonify({"error": "message is required"}), 422

    branding = BrandingSettings.get()
    api_key = current_app.config.get("OPENAI_API_KEY")

    if not api_key:
        return jsonify(_fallback_ai_reply(message, history, branding))

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        system_prompt = (
            f"You are a support assistant for {branding.app_name}. "
            "Answer using the knowledge base reference below when it's relevant. "
            "Ask at most one or two clarifying questions. If you cannot resolve the "
            "issue, or the user asks for a human/agent/ticket, stop asking questions "
            "and escalate: set escalate to true and write a concise summary of the "
            "issue for a support agent to read. "
            "Reply with ONLY a JSON object of the form "
            '{"reply": "your message to the user", "escalate": true or false, '
            '"summary": "concise issue summary, only when escalate is true"}.\n\n'
            f"Knowledge base:\n{_kb_context()}"
        )
        messages = [{"role": "system", "content": system_prompt}]
        for turn in history:
            role = turn.get("role")
            content = (turn.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content[:2000]})
        messages.append({"role": "user", "content": message[:2000]})

        resp = client.chat.completions.create(
            model=current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            response_format={"type": "json_object"},
            timeout=20,
        )
        parsed = json.loads(resp.choices[0].message.content)
        escalate = bool(parsed.get("escalate"))
        return jsonify({
            "reply": (parsed.get("reply") or "").strip() or "Could you tell me a bit more about the issue?",
            "escalate": escalate,
            "summary": (parsed.get("summary") or "").strip()[:2000] if escalate else None,
        })
    except Exception as e:
        current_app.logger.warning(f"AI chat failed, falling back to guided intake: {e}")
        return jsonify({
            "reply": "I'm having trouble reaching our AI assistant right now. Could you share your name and phone number or email so our team can follow up directly?",
            "escalate": True,
            "summary": message[:2000],
        })


# ── POST /widget/ticket ─────────────────────────────────────────────────────────

@widget_api.route("/ticket", methods=["POST"])
def create_ticket():
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    description = (data.get("issue") or data.get("description") or "").strip()

    if not name:
        return jsonify({"ok": False, "error": "name is required"}), 422
    if not description:
        return jsonify({"ok": False, "error": "issue description is required"}), 422

    contact = (data.get("contact") or "").strip()
    email = (data.get("email") or "").strip() or None
    app_name = (data.get("app") or "").strip() or None
    page = (data.get("page") or "").strip() or None
    priority = (data.get("priority") or "Medium").strip()
    category_id = data.get("category_id") or None
    country_id = data.get("country_id") or None

    now = datetime.utcnow()
    sl_no = Ticket.generate_sl_no()

    ticket = Ticket(
        sl_no=sl_no,
        channel="widget",
        widget_app=app_name,
        widget_page=page,
        issue_reporter_name=name,
        issue_reporter_contact=contact,
        form_submit_email=email,
        problem_details=description,
        priority=priority,
        category_id=category_id,
        country_id=country_id,
        current_status="Open",
        reporting_date=now,
        issue_start_date=now,
        created_at=now,
        updated_at=now,
    )

    db.session.add(ticket)
    db.session.flush()

    csat = CSATRating(ticket_id=ticket.id)
    db.session.add(csat)
    db.session.commit()

    return jsonify({
        "ok": True,
        "ticket_id": ticket.id,
        "sl_no": ticket.sl_no,
        "status": ticket.current_status,
        "csat_token": csat.token,
    }), 201


# ── GET /widget/ticket/<sl_no> ──────────────────────────────────────────────────

@widget_api.route("/ticket/<sl_no>", methods=["GET"])
def get_ticket(sl_no):
    ticket = Ticket.query.filter_by(sl_no=sl_no).first()
    if not ticket:
        return jsonify({"ok": False, "error": "Ticket not found"}), 404

    # Determine last update: latest public comment or ticket updated_at
    last_comment = (
        TicketComment.query
        .filter_by(ticket_id=ticket.id, is_internal=False)
        .order_by(TicketComment.created_at.desc())
        .first()
    )
    if last_comment:
        last_update = last_comment.created_at.isoformat()
    else:
        last_update = ticket.updated_at.isoformat() if ticket.updated_at else None

    return jsonify({
        "sl_no": ticket.sl_no,
        "status": ticket.current_status,
        "priority": ticket.priority,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "solved_date": ticket.solved_date.isoformat() if ticket.solved_date else None,
        "sla_status": ticket.sla_status(),
        "last_update": last_update,
    })


# ── POST /widget/csat/<token> ───────────────────────────────────────────────────

@widget_api.route("/csat/<token>", methods=["POST"])
def submit_csat(token):
    csat = CSATRating.query.filter_by(token=token).first()
    if not csat:
        return jsonify({"ok": False, "error": "Invalid token"}), 404

    if csat.submitted_at is not None:
        return jsonify({"ok": False, "error": "Already rated"}), 409

    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    feedback = data.get("feedback") or None

    if not isinstance(rating, int) or not (1 <= rating <= 5):
        return jsonify({"ok": False, "error": "rating must be an integer between 1 and 5"}), 422

    csat.rating = rating
    csat.feedback = feedback
    csat.submitted_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"ok": True})
