import json
from datetime import datetime

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, jsonify,
)
from flask_login import login_required, current_user

from models import db, AutomationRule, Tag, User, Role, Ticket

automation = Blueprint("automation", __name__, url_prefix="/admin/automation")


def _require_admin():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))


@automation.route("/")
@login_required
def index():
    guard = _require_admin()
    if guard:
        return guard
    rules = AutomationRule.query.order_by(AutomationRule.run_order, AutomationRule.id).all()
    return render_template("admin/automation.html", rules=rules)


@automation.route("/create", methods=["GET", "POST"])
@login_required
def create():
    guard = _require_admin()
    if guard:
        return guard
    if request.method == "POST":
        rule = _build_rule_from_form(None)
        if rule is None:
            return redirect(url_for("automation.create"))
        db.session.add(rule)
        db.session.commit()
        flash(f"Rule '{rule.name}' created.", "success")
        return redirect(url_for("automation.index"))
    tags = Tag.query.order_by(Tag.name).all()
    users = User.query.filter(
        User.role.in_([Role.AGENT, Role.ADMIN, Role.SUPER_ADMIN]),
        User.is_active == True,
    ).order_by(User.full_name).all()
    return render_template("admin/automation_edit.html", rule=None, tags=tags, users=users,
                           trigger_events=_TRIGGER_EVENTS,
                           condition_fields=_CONDITION_FIELDS,
                           action_types=_ACTION_TYPES)


@automation.route("/<int:rule_id>/edit", methods=["GET", "POST"])
@login_required
def edit(rule_id):
    guard = _require_admin()
    if guard:
        return guard
    rule = AutomationRule.query.get_or_404(rule_id)
    if request.method == "POST":
        _build_rule_from_form(rule)
        db.session.commit()
        flash(f"Rule '{rule.name}' updated.", "success")
        return redirect(url_for("automation.index"))
    tags = Tag.query.order_by(Tag.name).all()
    users = User.query.filter(
        User.role.in_([Role.AGENT, Role.ADMIN, Role.SUPER_ADMIN]),
        User.is_active == True,
    ).order_by(User.full_name).all()
    return render_template("admin/automation_edit.html", rule=rule, tags=tags, users=users,
                           trigger_events=_TRIGGER_EVENTS,
                           condition_fields=_CONDITION_FIELDS,
                           action_types=_ACTION_TYPES)


@automation.route("/<int:rule_id>/delete", methods=["POST"])
@login_required
def delete(rule_id):
    guard = _require_admin()
    if guard:
        return guard
    rule = AutomationRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    flash("Rule deleted.", "success")
    return redirect(url_for("automation.index"))


@automation.route("/<int:rule_id>/toggle", methods=["POST"])
@login_required
def toggle(rule_id):
    guard = _require_admin()
    if guard:
        return guard
    rule = AutomationRule.query.get_or_404(rule_id)
    rule.is_active = not rule.is_active
    db.session.commit()
    return redirect(url_for("automation.index"))


@automation.route("/reorder", methods=["POST"])
@login_required
def reorder():
    if not current_user.is_admin():
        return jsonify({"error": "Forbidden"}), 403
    order = request.json.get("order", [])
    for i, rule_id in enumerate(order):
        AutomationRule.query.filter_by(id=rule_id).update({"run_order": i})
    db.session.commit()
    return jsonify({"ok": True})


def _build_rule_from_form(rule):
    name = request.form.get("name", "").strip()
    if not name:
        flash("Rule name is required.", "warning")
        return None

    conditions = []
    fields_list = request.form.getlist("cond_field")
    ops_list = request.form.getlist("cond_operator")
    vals_list = request.form.getlist("cond_value")
    for f, o, v in zip(fields_list, ops_list, vals_list):
        if f and o:
            conditions.append({"field": f, "operator": o, "value": v})

    actions = []
    atypes = request.form.getlist("action_type")
    aparams_raw = request.form.getlist("action_params")
    for at, ap_raw in zip(atypes, aparams_raw):
        if at:
            try:
                params = json.loads(ap_raw) if ap_raw.strip() else {}
            except (ValueError, AttributeError):
                params = {}
            actions.append({"type": at, "params": params})

    if rule is None:
        rule = AutomationRule(created_by_id=current_user.id)

    rule.name = name
    rule.description = request.form.get("description", "").strip()
    rule.trigger_event = request.form.get("trigger_event", "ticket_created")
    rule.conditions_json = conditions
    rule.actions_json = actions
    rule.run_order = int(request.form.get("run_order", 0) or 0)
    rule.continue_on_match = request.form.get("continue_on_match") != "stop"
    rule.is_active = request.form.get("is_active") == "on"
    rule.updated_at = datetime.utcnow()
    return rule


_TRIGGER_EVENTS = [
    ("ticket_created", "Ticket Created"),
    ("status_changed", "Status Changed"),
    ("priority_changed", "Priority Changed"),
    ("reply_received", "Reply / Comment Added"),
]

_CONDITION_FIELDS = [
    ("priority", "Priority"),
    ("current_status", "Status"),
    ("channel", "Channel"),
    ("category_id", "Category ID"),
    ("issue_type", "Issue Type"),
    ("problem_details", "Problem Details"),
    ("escalation_level", "Escalation Level"),
]

_ACTION_TYPES = [
    ("set_priority", "Set Priority"),
    ("set_status", "Set Status"),
    ("assign_to", "Assign To Agent"),
    ("add_tag", "Add Tag"),
    ("escalate", "Escalate"),
    ("add_internal_note", "Add Internal Note"),
    ("notify_staff", "Notify Staff"),
    ("send_email_reporter", "Send Email to Reporter"),
]
