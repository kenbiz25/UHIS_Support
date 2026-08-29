from datetime import datetime

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, jsonify,
)
from flask_login import login_required, current_user

from models import (
    db, Ticket, User, Role, Tag, CannedResponse, SLAPolicy,
    TicketWatcher, CSATRating, TicketHistory, BrandingSettings,
    Country, AdminLevel1, AdminLevel2, AdminLevel3,
    IssueCategory, IssueSubcategory,
    SavedView, CustomField, TicketFieldValue,
)
from utils import create_notification, notify_staff, log_history, send_notification

admin_tools = Blueprint("admin_tools", __name__, url_prefix="/admin")


def _require_staff():
    if not current_user.can_update_tickets():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))


def _require_admin():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))


# ── Tags ───────────────────────────────────────────────────────────────────────

@admin_tools.route("/tags")
@login_required
def tags():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    all_tags = Tag.query.order_by(Tag.name).all()
    return render_template("admin/tags.html", tags=all_tags)


@admin_tools.route("/tags/create", methods=["POST"])
@login_required
def create_tag():
    if not current_user.is_admin():
        return jsonify({"error": "Forbidden"}), 403
    name = request.form.get("name", "").strip()
    color = request.form.get("color", "secondary")
    if not name:
        flash("Tag name is required.", "warning")
        return redirect(url_for("admin_tools.tags"))
    if Tag.query.filter_by(name=name).first():
        flash(f"Tag '{name}' already exists.", "warning")
        return redirect(url_for("admin_tools.tags"))
    db.session.add(Tag(name=name, color=color))
    db.session.commit()
    flash(f"Tag '{name}' created.", "success")
    return redirect(url_for("admin_tools.tags"))


@admin_tools.route("/tags/<int:tag_id>/delete", methods=["POST"])
@login_required
def delete_tag(tag_id):
    if not current_user.is_admin():
        return jsonify({"error": "Forbidden"}), 403
    tag = Tag.query.get_or_404(tag_id)
    db.session.delete(tag)
    db.session.commit()
    flash(f"Tag '{tag.name}' deleted.", "success")
    return redirect(url_for("admin_tools.tags"))


@admin_tools.route("/tickets/<int:ticket_id>/tags", methods=["POST"])
@login_required
def update_ticket_tags(ticket_id):
    if not current_user.can_update_tickets():
        return jsonify({"error": "Forbidden"}), 403
    ticket = Ticket.query.get_or_404(ticket_id)
    tag_ids = request.form.getlist("tag_ids", type=int)
    ticket.tags = Tag.query.filter(Tag.id.in_(tag_ids)).all() if tag_ids else []
    db.session.commit()
    flash("Tags updated.", "success")
    return redirect(url_for("tickets.detail", ticket_id=ticket_id))


# ── Canned Responses ───────────────────────────────────────────────────────────

@admin_tools.route("/canned-responses")
@login_required
def canned_responses():
    if not current_user.can_update_tickets():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    responses = CannedResponse.query.order_by(CannedResponse.category, CannedResponse.title).all()
    return render_template("admin/canned_responses.html", responses=responses)


@admin_tools.route("/canned-responses/create", methods=["POST"])
@login_required
def create_canned_response():
    if not current_user.can_update_tickets():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    category = request.form.get("category", "General").strip()
    if not title or not body:
        flash("Title and body are required.", "warning")
        return redirect(url_for("admin_tools.canned_responses"))
    db.session.add(CannedResponse(
        title=title, body=body, category=category,
        created_by_id=current_user.id,
    ))
    db.session.commit()
    flash(f"Canned response '{title}' created.", "success")
    return redirect(url_for("admin_tools.canned_responses"))


@admin_tools.route("/canned-responses/<int:resp_id>/delete", methods=["POST"])
@login_required
def delete_canned_response(resp_id):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    resp = CannedResponse.query.get_or_404(resp_id)
    db.session.delete(resp)
    db.session.commit()
    flash("Canned response deleted.", "success")
    return redirect(url_for("admin_tools.canned_responses"))


@admin_tools.route("/canned-responses/<int:resp_id>/toggle", methods=["POST"])
@login_required
def toggle_canned_response(resp_id):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    resp = CannedResponse.query.get_or_404(resp_id)
    resp.is_active = not resp.is_active
    db.session.commit()
    return redirect(url_for("admin_tools.canned_responses"))


@admin_tools.route("/canned-responses/api")
@login_required
def api_canned_responses():
    """JSON endpoint for JS quick-insert in comment form."""
    if not current_user.can_update_tickets():
        return jsonify([])
    responses = CannedResponse.query.filter_by(is_active=True).order_by(CannedResponse.category, CannedResponse.title).all()
    return jsonify([
        {"id": r.id, "title": r.title, "body": r.body, "category": r.category}
        for r in responses
    ])


# ── SLA Policies ───────────────────────────────────────────────────────────────

@admin_tools.route("/sla")
@login_required
def sla():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    policies = SLAPolicy.query.order_by(SLAPolicy.display_order, SLAPolicy.priority).all()
    return render_template("admin/sla.html", policies=policies)


@admin_tools.route("/sla/save", methods=["POST"])
@login_required
def save_sla():
    from models import Role
    if current_user.role != Role.SUPER_ADMIN:
        flash("Only Super Admin can modify SLA policies.", "danger")
        return redirect(url_for("admin_tools.sla"))

    def _float(val):
        try:
            return float(val) if val and val.strip() else None
        except (ValueError, AttributeError):
            return None

    all_policies = SLAPolicy.query.all()
    for policy in all_policies:
        p = policy.priority
        first_h = _float(request.form.get(f"first_{p}"))
        res_h   = _float(request.form.get(f"res_{p}"))
        l2_h    = _float(request.form.get(f"l2_{p}"))
        l3_h    = _float(request.form.get(f"l3_{p}"))
        l4_h    = _float(request.form.get(f"l4_{p}"))
        l1_own  = request.form.get(f"l1_owner_{p}", "").strip() or policy.l1_owner
        notif   = request.form.get(f"notif_{p}", "").strip() or policy.notification_rule
        is_247  = request.form.get(f"is_24_7_{p}") == "on"
        auto_e  = request.form.get(f"auto_escalate_{p}") == "on"

        if first_h is not None:
            policy.first_response_hours = first_h
        if res_h is not None:
            policy.resolution_hours = res_h
        policy.l2_resolution_hours = l2_h
        policy.l3_resolution_hours = l3_h
        policy.l4_resolution_hours = l4_h
        policy.l1_owner = l1_own
        policy.notification_rule = notif
        policy.is_24_7 = is_247
        policy.auto_escalate = auto_e
        policy.updated_at = datetime.utcnow()

    db.session.commit()
    flash("SLA escalation matrix saved.", "success")
    return redirect(url_for("admin_tools.sla"))


# ── Ticket Watchers ────────────────────────────────────────────────────────────

@admin_tools.route("/tickets/<int:ticket_id>/watch", methods=["POST"])
@login_required
def watch_ticket(ticket_id):
    Ticket.query.get_or_404(ticket_id)
    existing = TicketWatcher.query.filter_by(ticket_id=ticket_id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash("Stopped watching this ticket.", "info")
    else:
        db.session.add(TicketWatcher(ticket_id=ticket_id, user_id=current_user.id))
        db.session.commit()
        flash("You are now watching this ticket.", "success")
    return redirect(url_for("tickets.detail", ticket_id=ticket_id))


# ── Bulk Actions ───────────────────────────────────────────────────────────────

@admin_tools.route("/tickets/bulk-action", methods=["POST"])
@login_required
def bulk_action():
    if not current_user.can_update_tickets():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))

    action = request.form.get("bulk_action")
    ticket_ids = request.form.getlist("ticket_ids", type=int)

    if not ticket_ids:
        flash("No tickets selected.", "warning")
        return redirect(url_for("dashboard.main"))

    tickets = Ticket.query.filter(Ticket.id.in_(ticket_ids)).all()
    count = len(tickets)

    if action == "resolve":
        for t in tickets:
            if t.current_status not in ("Resolved", "Closed"):
                old = t.current_status
                t.current_status = "Resolved"
                t.solved_status = True
                t.solved_date = datetime.utcnow()
                t.solved_by = current_user.full_name
                t.updated_at = datetime.utcnow()
                log_history(t.id, current_user.id, "Status changed", old, "Resolved")
        flash(f"{count} ticket(s) resolved.", "success")

    elif action == "close":
        for t in tickets:
            old = t.current_status
            t.current_status = "Closed"
            t.updated_at = datetime.utcnow()
            log_history(t.id, current_user.id, "Status changed", old, "Closed")
        flash(f"{count} ticket(s) closed.", "success")

    elif action == "assign" and request.form.get("assign_to"):
        assignee_id = int(request.form["assign_to"])
        assignee = User.query.get(assignee_id)
        for t in tickets:
            old_id = t.assigned_to_id
            t.assigned_to_id = assignee_id
            t.updated_at = datetime.utcnow()
            log_history(t.id, current_user.id, "Assigned", str(old_id), str(assignee_id))
        if assignee:
            create_notification(
                assignee_id,
                f"{count} ticket(s) assigned to you by {current_user.full_name}",
                notif_type="warning",
            )
        flash(f"{count} ticket(s) assigned to {assignee.full_name if assignee else 'user'}.", "success")

    elif action == "set_priority" and request.form.get("new_priority"):
        new_prio = request.form["new_priority"]
        for t in tickets:
            old = t.priority
            t.priority = new_prio
            t.updated_at = datetime.utcnow()
            log_history(t.id, current_user.id, "Priority changed", old, new_prio)
        flash(f"Priority set to {new_prio} for {count} ticket(s).", "success")

    elif action == "add_tag" and request.form.get("bulk_tag_id"):
        tag = Tag.query.get(int(request.form["bulk_tag_id"]))
        if tag:
            for t in tickets:
                if tag not in t.tags.all():
                    t.tags.append(tag)
                    t.updated_at = datetime.utcnow()
            flash(f"Tag '{tag.name}' added to {count} ticket(s).", "success")
        else:
            flash("Tag not found.", "warning")

    elif action == "remove_tag" and request.form.get("bulk_tag_id"):
        tag = Tag.query.get(int(request.form["bulk_tag_id"]))
        if tag:
            for t in tickets:
                if tag in t.tags.all():
                    t.tags.remove(tag)
                    t.updated_at = datetime.utcnow()
            flash(f"Tag '{tag.name}' removed from {count} ticket(s).", "success")
        else:
            flash("Tag not found.", "warning")

    else:
        flash("Invalid action.", "warning")
        return redirect(url_for("dashboard.main"))

    db.session.commit()
    return redirect(url_for("dashboard.main"))


# ── CSAT Rating ────────────────────────────────────────────────────────────────

@admin_tools.route("/rate/<token>", methods=["GET", "POST"])
def csat_rate(token):
    rating_obj = CSATRating.query.filter_by(token=token).first_or_404()
    ticket = rating_obj.ticket
    if rating_obj.submitted_at:
        return render_template("csat_done.html", ticket=ticket, already=True)
    if request.method == "POST":
        score = request.form.get("rating", type=int)
        feedback = request.form.get("feedback", "").strip()
        if not score or score < 1 or score > 5:
            flash("Please select a rating.", "warning")
            return render_template("csat_rate.html", rating_obj=rating_obj, ticket=ticket)
        rating_obj.rating = score
        rating_obj.feedback = feedback
        rating_obj.submitted_at = datetime.utcnow()
        db.session.commit()
        return render_template("csat_done.html", ticket=ticket, already=False)
    return render_template("csat_rate.html", rating_obj=rating_obj, ticket=ticket)


# ── Integration Settings ───────────────────────────────────────────────────────

@admin_tools.route("/integrations")
@login_required
def integrations_page():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    from flask import current_app
    wa_configured = bool(
        current_app.config.get("WHATSAPP_TOKEN") or
        current_app.config.get("TWILIO_ACCOUNT_SID")
    )
    email_configured = bool(current_app.config.get("IMAP_USER"))
    countries = Country.query.order_by(Country.name).all()
    return render_template(
        "admin/integrations.html",
        wa_configured=wa_configured,
        email_configured=email_configured,
        countries=countries,
    )


# ── Locations Management ───────────────────────────────────────────────────────

@admin_tools.route("/locations")
@login_required
def manage_locations():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    countries = Country.query.order_by(Country.name).all()
    return render_template("admin/locations.html", countries=countries)


@admin_tools.route("/locations/add-unit", methods=["POST"])
@login_required
def add_admin_unit():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    level = request.form.get("level", type=int)
    name = request.form.get("name", "").strip()
    country_id = request.form.get("country_id", type=int)
    parent_id = request.form.get("parent_id", type=int)
    if not name:
        flash("Name is required.", "warning")
        return redirect(url_for("admin_tools.manage_locations"))
    if level == 1:
        db.session.add(AdminLevel1(name=name, country_id=country_id))
    elif level == 2:
        db.session.add(AdminLevel2(name=name, level1_id=parent_id, country_id=country_id))
    elif level == 3:
        db.session.add(AdminLevel3(name=name, level2_id=parent_id, country_id=country_id))
    db.session.commit()
    flash(f"Administrative unit '{name}' added.", "success")
    return redirect(url_for("admin_tools.manage_locations"))


# ── Saved Views ────────────────────────────────────────────────────────────────

@admin_tools.route("/saved-views")
@login_required
def saved_views():
    mine = SavedView.query.filter_by(owner_id=current_user.id).order_by(SavedView.name).all()
    shared = SavedView.query.filter_by(is_shared=True).filter(SavedView.owner_id != current_user.id).order_by(SavedView.name).all()
    return render_template("admin/saved_views.html", mine=mine, shared=shared)


@admin_tools.route("/saved-views/create", methods=["POST"])
@login_required
def create_saved_view():
    name = request.form.get("name", "").strip()
    if not name:
        flash("View name is required.", "warning")
        return redirect(request.referrer or url_for("dashboard.main"))
    filters_json = {
        k: request.form.get(k, "")
        for k in ("status", "priority", "assigned", "sla", "date_from", "date_to", "search", "district")
        if request.form.get(k, "")
    }
    db.session.add(SavedView(
        name=name,
        owner_id=current_user.id,
        is_shared=request.form.get("is_shared") == "on",
        filters_json=filters_json,
    ))
    db.session.commit()
    flash(f"View '{name}' saved.", "success")
    return redirect(url_for("admin_tools.saved_views"))


@admin_tools.route("/saved-views/<int:view_id>/delete", methods=["POST"])
@login_required
def delete_saved_view(view_id):
    view = SavedView.query.get_or_404(view_id)
    if view.owner_id != current_user.id and not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("admin_tools.saved_views"))
    db.session.delete(view)
    db.session.commit()
    flash("View deleted.", "success")
    return redirect(url_for("admin_tools.saved_views"))


# ── Custom Fields ───────────────────────────────────────────────────────────────

@admin_tools.route("/custom-fields")
@login_required
def custom_fields():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    fields = CustomField.query.order_by(CustomField.display_order, CustomField.name).all()
    return render_template("admin/custom_fields.html", fields=fields)


@admin_tools.route("/custom-fields/create", methods=["POST"])
@login_required
def create_custom_field():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    name = request.form.get("name", "").strip().replace(" ", "_").lower()
    label = request.form.get("label", "").strip()
    field_type = request.form.get("field_type", "text")
    options_raw = request.form.get("options", "").strip()
    options = [o.strip() for o in options_raw.split("\n") if o.strip()] if options_raw else []
    if not name or not label:
        flash("Name and label are required.", "warning")
        return redirect(url_for("admin_tools.custom_fields"))
    if CustomField.query.filter_by(name=name).first():
        flash(f"Field '{name}' already exists.", "warning")
        return redirect(url_for("admin_tools.custom_fields"))
    db.session.add(CustomField(
        name=name, label=label, field_type=field_type, options=options,
        is_required=request.form.get("is_required") == "on",
    ))
    db.session.commit()
    flash(f"Custom field '{label}' created.", "success")
    return redirect(url_for("admin_tools.custom_fields"))


@admin_tools.route("/custom-fields/<int:field_id>/toggle", methods=["POST"])
@login_required
def toggle_custom_field(field_id):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    field = CustomField.query.get_or_404(field_id)
    field.is_active = not field.is_active
    db.session.commit()
    return redirect(url_for("admin_tools.custom_fields"))


@admin_tools.route("/custom-fields/<int:field_id>/delete", methods=["POST"])
@login_required
def delete_custom_field(field_id):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    field = CustomField.query.get_or_404(field_id)
    db.session.delete(field)
    db.session.commit()
    flash("Custom field deleted.", "success")
    return redirect(url_for("admin_tools.custom_fields"))


@admin_tools.route("/tickets/<int:ticket_id>/custom-fields", methods=["POST"])
@login_required
def update_ticket_custom_fields(ticket_id):
    if not current_user.can_update_tickets():
        flash("Access denied.", "danger")
        return redirect(url_for("tickets.detail", ticket_id=ticket_id))
    ticket = Ticket.query.get_or_404(ticket_id)
    for field in CustomField.query.filter_by(is_active=True).all():
        val = request.form.get(f"cf_{field.id}", "").strip()
        existing = TicketFieldValue.query.filter_by(ticket_id=ticket.id, field_id=field.id).first()
        if existing:
            existing.value = val
        elif val:
            db.session.add(TicketFieldValue(ticket_id=ticket.id, field_id=field.id, value=val))
    db.session.commit()
    flash("Custom fields updated.", "success")
    return redirect(url_for("tickets.detail", ticket_id=ticket_id))


# ── Issue Taxonomy Management ──────────────────────────────────────────────────

@admin_tools.route("/taxonomy")
@login_required
def taxonomy():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    categories = IssueCategory.query.order_by(IssueCategory.display_order, IssueCategory.name).all()
    return render_template("admin/taxonomy.html", categories=categories)


@admin_tools.route("/taxonomy/category/create", methods=["POST"])
@login_required
def create_category():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    name = request.form.get("name", "").strip()
    if not name:
        flash("Name required.", "warning")
        return redirect(url_for("admin_tools.taxonomy"))
    if IssueCategory.query.filter_by(name=name).first():
        flash(f"Category '{name}' already exists.", "warning")
        return redirect(url_for("admin_tools.taxonomy"))
    db.session.add(IssueCategory(
        name=name,
        icon=request.form.get("icon", "tag"),
        color=request.form.get("color", "primary"),
    ))
    db.session.commit()
    flash(f"Category '{name}' created.", "success")
    return redirect(url_for("admin_tools.taxonomy"))


@admin_tools.route("/taxonomy/subcategory/create", methods=["POST"])
@login_required
def create_subcategory():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    name = request.form.get("name", "").strip()
    category_id = request.form.get("category_id", type=int)
    if not name or not category_id:
        flash("Name and category required.", "warning")
        return redirect(url_for("admin_tools.taxonomy"))
    db.session.add(IssueSubcategory(name=name, category_id=category_id))
    db.session.commit()
    flash(f"Sub-category '{name}' created.", "success")
    return redirect(url_for("admin_tools.taxonomy"))


@admin_tools.route("/taxonomy/subcategory/<int:sub_id>/delete", methods=["POST"])
@login_required
def delete_subcategory(sub_id):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    sub = IssueSubcategory.query.get_or_404(sub_id)
    db.session.delete(sub)
    db.session.commit()
    flash("Sub-category deleted.", "success")
    return redirect(url_for("admin_tools.taxonomy"))


@admin_tools.route("/taxonomy/category/<int:cat_id>/delete", methods=["POST"])
@login_required
def delete_category(cat_id):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    cat = IssueCategory.query.get_or_404(cat_id)
    db.session.delete(cat)
    db.session.commit()
    flash("Category and all sub-categories deleted.", "success")
    return redirect(url_for("admin_tools.taxonomy"))


# ── Branding Settings ──────────────────────────────────────────────────────────

@admin_tools.route("/branding", methods=["GET", "POST"])
@login_required
def branding():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    settings = BrandingSettings.get()
    if request.method == "POST":
        settings.app_name = request.form.get("app_name", "Bangladesh UHIS").strip() or "Bangladesh UHIS"
        settings.tagline = request.form.get("tagline", "").strip()
        settings.logo_url = request.form.get("logo_url", "").strip() or None
        settings.favicon_url = request.form.get("favicon_url", "").strip() or None
        settings.primary_color = request.form.get("primary_color", "#2514BE").strip()
        settings.nav_bg = request.form.get("nav_bg", "#1e2a38").strip()
        settings.support_email = request.form.get("support_email", "").strip() or None
        from datetime import datetime
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        flash("Branding settings saved.", "success")
        return redirect(url_for("admin_tools.branding"))
    return render_template("admin/branding.html", settings=settings)


# ── Country Escalation Matrices ────────────────────────────────────────────────

@admin_tools.route("/escalation-matrices")
@login_required
def escalation_matrices():
    if not current_user.can_update_tickets():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    from models import CountryEscalationMatrix, Country
    countries = Country.query.filter_by(is_active=True).order_by(Country.name).all()
    matrices = {m.country_id: m for m in CountryEscalationMatrix.query.all()}
    return render_template("admin/escalation_matrices.html",
                           countries=countries, matrices=matrices)


@admin_tools.route("/escalation-matrices/<int:country_id>")
@login_required
def escalation_matrix_detail(country_id):
    if not current_user.can_update_tickets():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    from models import CountryEscalationMatrix, Country
    country = Country.query.get_or_404(country_id)
    matrix = CountryEscalationMatrix.query.filter_by(country_id=country_id).first()
    return render_template("admin/escalation_matrix_detail.html",
                           country=country, matrix=matrix)
