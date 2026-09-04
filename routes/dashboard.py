from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timedelta

from models import db, Ticket, User, Role, Notification, CSATRating, TicketHistory, SavedView, Tag, CallLog, IssueCategory, AdminLevel1

dashboard = Blueprint("dashboard", __name__)

# Cadre hierarchy — higher number = higher authority
ROLE_LEVEL = {
    Role.SUPER_ADMIN: 4,
    Role.ADMIN:       3,
    Role.AGENT:       2,
    Role.REPORTER:    1,
    Role.VIEWER:      0,
}


# ── Regional visibility filter ────────────────────────────────────────────────

def _region_filter(query, user):
    """
    Return (filtered_query, scope_label).
    Super Admins see everything. Admins/Agents are scoped to their location
    (primary country/admin1 on their User record + any UserRegionRole entries).
    Users with no location configured retain global access.
    """
    from models import Role, UserRegionRole

    if user.role == Role.SUPER_ADMIN:
        return query, None

    regions = []   # list of (country_id, admin1_id_or_None, label)

    # 1. Primary location from the user's own profile
    if user.country_id:
        label = user.country.name if user.country else str(user.country_id)
        if user.admin1_id and user.admin1:
            label += f" / {user.admin1.name}"
        regions.append((user.country_id, user.admin1_id, label))

    # 2. Additional regional role scopes
    for rr in (user.region_roles or []):
        if rr.country_id:
            lbl = rr.country.name if rr.country else str(rr.country_id)
            if rr.admin1_id and rr.admin1:
                lbl += f" / {rr.admin1.name}"
            # avoid duplicates
            entry = (rr.country_id, rr.admin1_id, lbl)
            if entry not in regions:
                regions.append(entry)

    # No region configured → retain global access (safe fallback)
    if not regions:
        return query, None

    # Build OR conditions across all allowed regions
    conditions = []
    for country_id, admin1_id, _ in regions:
        if admin1_id:
            conditions.append(
                db.and_(Ticket.country_id == country_id, Ticket.admin1_id == admin1_id)
            )
        else:
            conditions.append(Ticket.country_id == country_id)

    scope_label = " · ".join(r[2] for r in regions)
    return query.filter(db.or_(*conditions)), scope_label


@dashboard.route("/")
@login_required
def index():
    return redirect(url_for("dashboard.main"))


# ── Main dashboard — role-aware ────────────────────────────────────────────────

@dashboard.route("/dashboard")
@login_required
def main():
    if current_user.role == Role.SUPER_ADMIN:
        return _superadmin_view()
    if current_user.role == Role.ADMIN:
        return _admin_view()
    if current_user.role == Role.AGENT:
        return _admin_view(agent_mode=True)
    if current_user.role == Role.VIEWER:
        return _viewer_view()
    return _reporter_view()


# ── Reporter view ──────────────────────────────────────────────────────────────

def _reporter_view():
    q = Ticket.query.filter_by(reporter_id=current_user.id)

    status_f   = request.args.get("status", "")
    priority_f = request.args.get("priority", "")
    search_f   = request.args.get("search", "")

    if status_f:
        q = q.filter(Ticket.current_status == status_f)
    if priority_f:
        q = q.filter(Ticket.priority == priority_f)
    if search_f:
        t = f"%{search_f}%"
        q = q.filter(db.or_(Ticket.sl_no.ilike(t), Ticket.problem_details.ilike(t),
                             Ticket.issue_type.ilike(t)))

    my_tickets = q.order_by(Ticket.created_at.desc()).all()
    base = Ticket.query.filter_by(reporter_id=current_user.id)
    stats = {
        "total":       base.count(),
        "open":        base.filter(Ticket.current_status == "Open").count(),
        "in_progress": base.filter(Ticket.current_status == "In Progress").count(),
        "resolved":    base.filter(Ticket.current_status == "Resolved").count(),
        "critical":    base.filter(Ticket.priority == "Critical").count(),
    }
    recent_notifs = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc()).limit(5).all()
    )
    import json as _json
    tickets_json = _json.dumps([{
        "id": t.id, "sl_no": t.sl_no or f"#{t.id}",
        "issue_type": t.issue_type or "General Issue",
        "priority": t.priority,
        "priority_badge": t.priority_badge(),
        "status": t.current_status,
        "status_badge": t.status_badge(),
        "district": t.district or "",
        "created_at": t.created_at.strftime("%b %d, %Y") if t.created_at else "",
        "reporter": t.issue_reporter_name or "",
        "comments": len(t.ticket_comments),
        "solved_by": t.solved_by or "",
    } for t in my_tickets])
    return render_template(
        "portal/reporter_dashboard.html",
        tickets=my_tickets, stats=stats, recent_notifs=recent_notifs,
        statuses=["Open", "In Progress", "Pending", "Resolved", "Closed", "Reopened"],
        priorities=["Low", "Medium", "High", "Critical", "Urgent"],
        filters={"status": status_f, "priority": priority_f, "search": search_f},
        tickets_json=tickets_json,
    )


# ── Admin / Agent view ─────────────────────────────────────────────────────────

def _admin_view(agent_mode=False):
    status_f     = request.args.get("status", "")
    priority_f   = request.args.get("priority", "")
    district_f   = request.args.get("district", "")
    search_f     = request.args.get("search", "")
    # Agents land on their own queue by default; Admins/Super Admins see everything.
    assigned_f   = request.args.get("assigned", "mine" if agent_mode else "")
    reporter_f   = request.args.get("reporter_id", "", type=str)   # reporter user_id
    country_f    = request.args.get("country_id", "", type=str)    # country_id
    resolved_by_f= request.args.get("resolved_by", "", type=str)   # agent user_id who resolved
    date_from_f  = request.args.get("date_from", "")
    date_to_f    = request.args.get("date_to", "")
    sla_f        = request.args.get("sla", "")

    # Apply regional visibility scope
    base_q, scope_label = _region_filter(Ticket.query, current_user)

    q = base_q
    if status_f:
        q = q.filter(Ticket.current_status == status_f)
    if priority_f:
        q = q.filter(Ticket.priority == priority_f)
    if district_f:
        q = q.filter(Ticket.district.ilike(f"%{district_f}%"))
    if search_f:
        t = f"%{search_f}%"
        q = q.filter(db.or_(Ticket.sl_no.ilike(t), Ticket.issue_reporter_name.ilike(t),
                             Ticket.problem_details.ilike(t), Ticket.district.ilike(t)))
    # Filter by specific assigned agent (numeric id), mine, or unassigned
    if assigned_f == "unassigned":
        q = q.filter(Ticket.assigned_to_id.is_(None))
    elif assigned_f == "mine":
        q = q.filter(Ticket.assigned_to_id == current_user.id)
    elif assigned_f and assigned_f.isdigit():
        q = q.filter(Ticket.assigned_to_id == int(assigned_f))
    # Filter by who raised the ticket
    if reporter_f and reporter_f.isdigit():
        q = q.filter(Ticket.reporter_id == int(reporter_f))
    # Filter by country
    if country_f and country_f.isdigit():
        q = q.filter(Ticket.country_id == int(country_f))
    # Filter by who resolved (solved_by is a name string; also check assigned agent)
    if resolved_by_f and resolved_by_f.isdigit():
        q = q.filter(Ticket.assigned_to_id == int(resolved_by_f), Ticket.solved_status == True)
    if date_from_f:
        try:
            q = q.filter(Ticket.created_at >= datetime.strptime(date_from_f, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to_f:
        try:
            q = q.filter(Ticket.created_at <= datetime.strptime(date_to_f, "%Y-%m-%d") + timedelta(days=1))
        except ValueError:
            pass
    if sla_f == "breached":
        q = q.filter(Ticket.sla_breached == True, Ticket.current_status.notin_(["Resolved", "Closed"]))
    elif sla_f == "warning":
        cutoff = datetime.utcnow() + timedelta(hours=4)
        q = q.filter(
            Ticket.due_date.isnot(None),
            Ticket.due_date > datetime.utcnow(),
            Ticket.due_date <= cutoff,
            Ticket.current_status.notin_(["Resolved", "Closed"]),
        )

    tickets = q.order_by(
        Ticket.escalation_level.desc(), Ticket.priority.desc(), Ticket.created_at.desc()
    ).all()

    # Admins/Super Admins get region-wide stats; Agents get personal + pickup-queue stats.
    if agent_mode:
        mine_q = base_q.filter(Ticket.assigned_to_id == current_user.id)
        my_level = current_user.agent_level or 1
        stats = {
            "total":       mine_q.count(),
            "open":        mine_q.filter(Ticket.current_status == "Open").count(),
            "in_progress": mine_q.filter(Ticket.current_status == "In Progress").count(),
            "critical":    mine_q.filter(Ticket.priority.in_(["Critical", "Urgent"])).count(),
            "unassigned":  base_q.filter(
                Ticket.assigned_to_id.is_(None),
                Ticket.current_status.notin_(["Resolved", "Closed"]),
                Ticket.escalation_level == my_level - 1,
            ).count(),
            "escalated":   mine_q.filter(Ticket.escalation_level > 0).count(),
            "resolved_today": mine_q.filter(
                Ticket.solved_status == True,
                func.date(Ticket.solved_date) == func.date(func.now())
            ).count(),
        }
    else:
        all_q = base_q
        stats = {
            "total":       all_q.count(),
            "open":        all_q.filter(Ticket.current_status == "Open").count(),
            "in_progress": all_q.filter(Ticket.current_status == "In Progress").count(),
            "critical":    all_q.filter(Ticket.priority.in_(["Critical", "Urgent"])).count(),
            "unassigned":  all_q.filter(Ticket.assigned_to_id.is_(None),
                                        Ticket.current_status.notin_(["Resolved", "Closed"])).count(),
            "escalated":   all_q.filter(Ticket.escalation_level > 0).count(),
            "resolved_today": all_q.filter(
                Ticket.solved_status == True,
                func.date(Ticket.solved_date) == func.date(func.now())
            ).count(),
        }

    assignable = User.query.filter(
        User.role.in_([Role.AGENT, Role.ADMIN, Role.SUPER_ADMIN]), User.is_active == True
    ).all()
    reporters = User.query.filter(
        User.role.in_([Role.REPORTER, Role.AGENT, Role.ADMIN]), User.is_active == True
    ).order_by(User.full_name).all()
    from models import Country
    countries = Country.query.filter_by(is_active=True).order_by(Country.name).all()
    districts = [r[0] for r in db.session.query(Ticket.district).distinct()
                 .filter(Ticket.district.isnot(None), Ticket.district != "").all()]
    saved_views = SavedView.query.filter(
        db.or_(SavedView.owner_id == current_user.id, SavedView.is_shared == True)
    ).order_by(SavedView.name).all()
    all_tags = Tag.query.order_by(Tag.name).all()

    import json as _json
    tickets_json = _json.dumps([{
        "id": t.id, "sl_no": t.sl_no or f"#{t.id}",
        "issue_type": t.issue_type or "General Issue",
        "priority": t.priority,
        "priority_badge": t.priority_badge(),
        "status": t.current_status,
        "status_badge": t.status_badge(),
        "district": t.district or "",
        "created_at": t.created_at.strftime("%b %d, %Y") if t.created_at else "",
        "reporter": t.issue_reporter_name or "",
        "comments": len(t.ticket_comments),
        "solved_by": t.solved_by or "",
    } for t in tickets])
    return render_template(
        "portal/admin_dashboard.html",
        tickets=tickets, stats=stats, assignable=assignable, districts=districts,
        statuses=["Open", "In Progress", "Pending", "Resolved", "Closed", "Reopened"],
        priorities=["Low", "Medium", "High", "Critical", "Urgent"],
        filters={
            "status": status_f, "priority": priority_f,
            "district": district_f, "search": search_f, "assigned": assigned_f,
            "date_from": date_from_f, "date_to": date_to_f, "sla": sla_f,
            "reporter_id": reporter_f, "country_id": country_f, "resolved_by": resolved_by_f,
        },
        saved_views=saved_views,
        all_tags=all_tags,
        scope_label=scope_label,
        reporters=reporters,
        countries=countries,
        tickets_json=tickets_json,
        agent_mode=agent_mode,
    )


# ── Super Admin view ───────────────────────────────────────────────────────────

def _superadmin_view():
    all_q = Ticket.query
    stats = {
        "total":        all_q.count(),
        "open":         all_q.filter(Ticket.current_status == "Open").count(),
        "in_progress":  all_q.filter(Ticket.current_status == "In Progress").count(),
        "resolved":     all_q.filter(Ticket.current_status == "Resolved").count(),
        "critical":     all_q.filter(Ticket.priority == "Critical").count(),
        "escalated":    all_q.filter(Ticket.escalation_level > 0).count(),
        "unassigned":   all_q.filter(Ticket.assigned_to_id.is_(None),
                                     Ticket.current_status.notin_(["Resolved", "Closed"])).count(),
    }
    resolution_rate = (
        round(stats["resolved"] / stats["total"] * 100, 1) if stats["total"] else 0
    )

    district_breakdown = (
        db.session.query(
            Ticket.district,
            func.count(Ticket.id).label("total"),
            func.sum(db.case((Ticket.current_status == "Open", 1), else_=0)).label("open"),
            func.sum(db.case((Ticket.priority == "Critical", 1), else_=0)).label("critical"),
        )
        .filter(Ticket.district.isnot(None), Ticket.district != "")
        .group_by(Ticket.district)
        .order_by(func.count(Ticket.id).desc())
        .limit(15)
        .all()
    )

    escalated = (
        Ticket.query.filter(Ticket.escalation_level > 0)
        .order_by(Ticket.escalation_level.desc(), Ticket.created_at.desc())
        .limit(10)
        .all()
    )

    critical_open = (
        Ticket.query.filter(
            Ticket.priority == "Critical",
            Ticket.current_status.notin_(["Resolved", "Closed"])
        )
        .order_by(Ticket.created_at.asc())
        .limit(10)
        .all()
    )

    # Platform breakdown
    platform_data = (
        db.session.query(Ticket.spice_platform, func.count(Ticket.id))
        .filter(Ticket.spice_platform.isnot(None), Ticket.spice_platform != "")
        .group_by(Ticket.spice_platform)
        .all()
    )

    # Recent activity (last history entries)
    recent_activity = (
        TicketHistory.query
        .order_by(TicketHistory.created_at.desc())
        .limit(15)
        .all()
    )

    # CSAT average for super admin dashboard
    csat_avg = db.session.query(func.avg(CSATRating.rating)).filter(CSATRating.rating.isnot(None)).scalar()

    # SLA breached count
    sla_breached_count = Ticket.query.filter(Ticket.sla_breached == True, Ticket.current_status.notin_(["Resolved", "Closed"])).count()

    # Team stats
    team_stats = (
        db.session.query(
            User.full_name, User.role,
            func.count(Ticket.id).label("assigned"),
            func.sum(db.case((Ticket.solved_status == True, 1), else_=0)).label("resolved"),
        )
        .outerjoin(Ticket, Ticket.assigned_to_id == User.id)
        .filter(User.role.in_([Role.ADMIN, Role.AGENT]), User.is_active == True)
        .group_by(User.id)
        .all()
    )

    # All tickets (filterable)
    status_f   = request.args.get("status", "")
    priority_f = request.args.get("priority", "")
    district_f = request.args.get("district", "")
    search_f   = request.args.get("search", "")

    tq = Ticket.query
    if status_f:
        tq = tq.filter(Ticket.current_status == status_f)
    if priority_f:
        tq = tq.filter(Ticket.priority == priority_f)
    if district_f:
        tq = tq.filter(Ticket.district.ilike(f"%{district_f}%"))
    if search_f:
        t = f"%{search_f}%"
        tq = tq.filter(db.or_(Ticket.sl_no.ilike(t), Ticket.issue_reporter_name.ilike(t),
                               Ticket.problem_details.ilike(t), Ticket.district.ilike(t)))
    all_tickets = tq.order_by(
        Ticket.escalation_level.desc(), Ticket.priority.desc(), Ticket.created_at.desc()
    ).all()

    districts = [r[0] for r in db.session.query(Ticket.district).distinct()
                 .filter(Ticket.district.isnot(None), Ticket.district != "").all()]

    return render_template(
        "portal/superadmin_dashboard.html",
        stats=stats,
        resolution_rate=resolution_rate,
        district_breakdown=district_breakdown,
        escalated=escalated,
        critical_open=critical_open,
        platform_data=platform_data,
        recent_activity=recent_activity,
        team_stats=team_stats,
        all_tickets=all_tickets,
        districts=districts,
        statuses=["Open", "In Progress", "Pending", "Resolved", "Closed", "Reopened"],
        priorities=["Low", "Medium", "High", "Critical", "Urgent"],
        filters={"status": status_f, "priority": priority_f,
                 "district": district_f, "search": search_f},
        csat_avg=round(csat_avg, 1) if csat_avg else None,
        sla_breached_count=sla_breached_count,
    )


# ── Unified Inbox ──────────────────────────────────────────────────────────────

@dashboard.route("/inbox")
@login_required
def unified_inbox():
    if not current_user.can_update_tickets():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))

    channel_f  = request.args.get("channel", "")
    status_f   = request.args.get("status", "")
    priority_f = request.args.get("priority", "")
    search_f   = request.args.get("search", "")

    base_q, scope_label = _region_filter(Ticket.query, current_user)

    q = base_q
    if channel_f:
        q = q.filter(Ticket.channel == channel_f)
    if status_f:
        q = q.filter(Ticket.current_status == status_f)
    if priority_f:
        q = q.filter(Ticket.priority == priority_f)
    if search_f:
        t = f"%{search_f}%"
        q = q.filter(db.or_(
            Ticket.sl_no.ilike(t),
            Ticket.issue_reporter_name.ilike(t),
            Ticket.problem_details.ilike(t),
        ))

    tickets = q.order_by(Ticket.created_at.desc()).limit(200).all()

    # Channel breakdown counts scoped to user's region
    channel_counts = {
        r[0]: r[1]
        for r in base_q.filter(Ticket.current_status.notin_(["Resolved", "Closed"]))
        .with_entities(Ticket.channel, func.count(Ticket.id))
        .group_by(Ticket.channel).all()
    }
    return render_template(
        "inbox.html",
        tickets=tickets,
        channel_counts=channel_counts,
        channel_f=channel_f,
        status_f=status_f,
        priority_f=priority_f,
        search_f=search_f,
        statuses=["Open", "In Progress", "Pending", "Resolved", "Closed", "Reopened"],
        priorities=["Low", "Medium", "High", "Critical", "Urgent"],
        channels=["web", "email", "whatsapp", "telegram", "api"],
        scope_label=scope_label,
    )


# ── Admin: User management ─────────────────────────────────────────────────────

@dashboard.route("/admin/users")
@login_required
def users():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    from models import Country
    all_users = User.query.order_by(User.created_at.desc()).all()
    all_countries = Country.query.filter_by(is_active=True).order_by(Country.name).all()

    my_level = ROLE_LEVEL.get(current_user.role, 0)

    # IDs of users whose regional roles the current user may manage
    manageable_ids = {u.id for u in all_users if ROLE_LEVEL.get(u.role, 0) < my_level}

    # Roles the current user is allowed to grant (only roles below their own)
    assignable_roles = [r for r in Role if ROLE_LEVEL.get(r, 0) < my_level]

    # Countries the current user can assign regions in
    # Super Admin → all countries; scoped → only their own
    if current_user.role == Role.SUPER_ADMIN:
        accessible_countries = all_countries
    else:
        allowed_cids = set()
        if current_user.country_id:
            allowed_cids.add(current_user.country_id)
        for rr in (current_user.region_roles or []):
            if rr.country_id and ROLE_LEVEL.get(rr.role, 0) >= ROLE_LEVEL.get(Role.ADMIN, 0):
                allowed_cids.add(rr.country_id)
        accessible_countries = [c for c in all_countries if c.id in allowed_cids] if allowed_cids else all_countries

    return render_template(
        "admin/users.html",
        users=all_users,
        roles=Role,
        countries=accessible_countries,
        manageable_ids=manageable_ids,
        assignable_roles=assignable_roles,
        my_level=my_level,
    )


@dashboard.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@login_required
def toggle_user(user_id):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "warning")
        return redirect(url_for("dashboard.users"))
    user.is_active = not user.is_active
    db.session.commit()
    flash(f"User '{user.username}' {'activated' if user.is_active else 'deactivated'}.", "success")
    return redirect(url_for("dashboard.users"))


@dashboard.route("/admin/users/<int:user_id>/agent-level", methods=["POST"])
@login_required
def set_agent_level(user_id):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    user = User.query.get_or_404(user_id)
    if user.role != Role.AGENT:
        flash("Only Agents have a tier level.", "warning")
        return redirect(url_for("dashboard.users"))
    level = request.form.get("agent_level", type=int)
    if level not in (1, 2, 3, 4):
        flash("Invalid tier — choose L1 through L4.", "warning")
        return redirect(url_for("dashboard.users"))
    user.agent_level = level
    db.session.commit()
    flash(f"{user.full_name} set to L{level}.", "success")
    return redirect(url_for("dashboard.users"))


# ── Reports ────────────────────────────────────────────────────────────────────

@dashboard.route("/admin/reports")
@login_required
def reports():
    if not current_user.can_view_reports():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))

    status_data   = db.session.query(Ticket.current_status, func.count(Ticket.id)).group_by(Ticket.current_status).all()
    priority_data = db.session.query(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority).all()
    district_data = (db.session.query(Ticket.district, func.count(Ticket.id))
                     .group_by(Ticket.district)
                     .filter(Ticket.district.isnot(None), Ticket.district != "")
                     .order_by(func.count(Ticket.id).desc()).limit(10).all())
    # Division-level breakdown via the structured admin1_id FK - catches tickets
    # from channels that only capture Division (AI Assistant widget, WhatsApp
    # bot intake), which never populate the legacy district string above.
    division_data = (db.session.query(AdminLevel1.name, func.count(Ticket.id))
                     .join(Ticket, Ticket.admin1_id == AdminLevel1.id)
                     .group_by(AdminLevel1.name)
                     .order_by(func.count(Ticket.id).desc()).all())
    platform_data = (db.session.query(Ticket.spice_platform, func.count(Ticket.id))
                     .group_by(Ticket.spice_platform)
                     .filter(Ticket.spice_platform.isnot(None), Ticket.spice_platform != "").all())
    issue_type_data = (db.session.query(Ticket.issue_type, func.count(Ticket.id))
                       .group_by(Ticket.issue_type)
                       .filter(Ticket.issue_type.isnot(None), Ticket.issue_type != "")
                       .order_by(func.count(Ticket.id).desc()).all())

    total    = Ticket.query.count()
    resolved = Ticket.query.filter_by(solved_status=True).count()

    # CSAT average
    csat_avg = db.session.query(func.avg(CSATRating.rating)).filter(CSATRating.rating.isnot(None)).scalar()
    csat_count = CSATRating.query.filter(CSATRating.rating.isnot(None)).count()

    # SLA compliance: tickets resolved before due_date
    sla_compliant = Ticket.query.filter(
        Ticket.solved_status == True,
        Ticket.due_date.isnot(None),
        Ticket.solved_date <= Ticket.due_date,
    ).count()
    sla_eligible = Ticket.query.filter(Ticket.solved_status == True, Ticket.due_date.isnot(None)).count()
    sla_rate = round(sla_compliant / sla_eligible * 100, 1) if sla_eligible else None

    # Avg resolution time (hours)
    resolved_with_dates = Ticket.query.filter(
        Ticket.solved_status == True,
        Ticket.solved_date.isnot(None),
    ).all()
    if resolved_with_dates:
        avg_res_hours = sum(
            (t.solved_date - t.created_at).total_seconds() / 3600
            for t in resolved_with_dates
        ) / len(resolved_with_dates)
    else:
        avg_res_hours = None

    # Avg first response time (hours)
    with_response = Ticket.query.filter(Ticket.first_response_at.isnot(None)).all()
    if with_response:
        avg_resp_hours = sum(
            (t.first_response_at - t.created_at).total_seconds() / 3600
            for t in with_response
        ) / len(with_response)
    else:
        avg_resp_hours = None

    # ── Escalation pyramid: resolved tickets by escalation level ─────────────
    # L1 = resolved with no escalation (escalation_level=0)
    # L2 = escalated once, L3 = twice, L4 = three or more times
    pyramid = [
        {
            "level": "L1 — First Level",
            "owner": "First-Level Support",
            "total":    Ticket.query.filter(Ticket.escalation_level == 0).count(),
            "resolved": Ticket.query.filter(Ticket.escalation_level == 0, Ticket.solved_status == True).count(),
            "color": "#10b981",  # green
            "bg": "success",
        },
        {
            "level": "L2 — Technical Support",
            "owner": "Technical Support Engineers",
            "total":    Ticket.query.filter(Ticket.escalation_level == 1).count(),
            "resolved": Ticket.query.filter(Ticket.escalation_level == 1, Ticket.solved_status == True).count(),
            "color": "#3b82f6",  # blue
            "bg": "primary",
        },
        {
            "level": "L3 — Expert Level Support",
            "owner": "SPICE / Platform Experts",
            "total":    Ticket.query.filter(Ticket.escalation_level == 2).count(),
            "resolved": Ticket.query.filter(Ticket.escalation_level == 2, Ticket.solved_status == True).count(),
            "color": "#f59e0b",  # amber
            "bg": "warning",
        },
        {
            "level": "L4 — Internal (Executive)",
            "owner": "Internal Senior Leadership",
            "total":    Ticket.query.filter(Ticket.escalation_level >= 3).count(),
            "resolved": Ticket.query.filter(Ticket.escalation_level >= 3, Ticket.solved_status == True).count(),
            "color": "#ef4444",  # red
            "bg": "danger",
        },
    ]
    pyramid_max = max((p["total"] for p in pyramid), default=1) or 1

    return render_template(
        "admin/reports.html",
        status_data=status_data, priority_data=priority_data,
        district_data=district_data, division_data=division_data, platform_data=platform_data,
        issue_type_data=issue_type_data,
        total=total, resolved=resolved,
        resolution_rate=round(resolved / total * 100, 1) if total else 0,
        csat_avg=round(csat_avg, 2) if csat_avg else None,
        csat_count=csat_count,
        sla_rate=sla_rate,
        avg_res_hours=round(avg_res_hours, 1) if avg_res_hours else None,
        avg_resp_hours=round(avg_resp_hours, 1) if avg_resp_hours else None,
        pyramid=pyramid,
        pyramid_max=pyramid_max,
    )


# ── Analytics Dashboard ────────────────────────────────────────────────────────

@dashboard.route("/admin/analytics")
@login_required
def analytics():
    if not current_user.can_view_reports():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))

    from models import Country, IssueCategory

    # ── Filters ────────────────────────────────────────────────────────────────
    date_from_f = request.args.get("date_from", "")
    date_to_f   = request.args.get("date_to", "")
    country_f   = request.args.get("country_id", type=int) or None
    assigned_f  = request.args.get("assigned_id", type=int) or None
    status_f    = request.args.get("status", "")
    priority_f  = request.args.get("priority", "")
    channel_f   = request.args.get("channel", "")
    days        = int(request.args.get("days", 30))
    days        = max(7, min(days, 365))

    try:
        since = datetime.strptime(date_from_f, "%Y-%m-%d") if date_from_f else datetime.utcnow() - timedelta(days=days)
    except ValueError:
        since = datetime.utcnow() - timedelta(days=days)
    try:
        until = datetime.strptime(date_to_f, "%Y-%m-%d") + timedelta(days=1) if date_to_f else datetime.utcnow()
    except ValueError:
        until = datetime.utcnow()

    # ── Base filtered query factory ────────────────────────────────────────────
    def bq():
        q = Ticket.query.filter(Ticket.created_at >= since, Ticket.created_at < until)
        if country_f:  q = q.filter(Ticket.country_id == country_f)
        if assigned_f: q = q.filter(Ticket.assigned_to_id == assigned_f)
        if status_f:   q = q.filter(Ticket.current_status == status_f)
        if priority_f: q = q.filter(Ticket.priority == priority_f)
        if channel_f:  q = q.filter(Ticket.channel == channel_f)
        return q

    def bf():
        f = [Ticket.created_at >= since, Ticket.created_at < until]
        if country_f:  f.append(Ticket.country_id == country_f)
        if assigned_f: f.append(Ticket.assigned_to_id == assigned_f)
        if status_f:   f.append(Ticket.current_status == status_f)
        if priority_f: f.append(Ticket.priority == priority_f)
        if channel_f:  f.append(Ticket.channel == channel_f)
        return f

    # ── KPI stats ──────────────────────────────────────────────────────────────
    total          = bq().count()
    total_open     = bq().filter(Ticket.current_status == "Open").count()
    total_inprog   = bq().filter(Ticket.current_status == "In Progress").count()
    total_resolved = bq().filter(Ticket.solved_status == True).count()
    total_critical = bq().filter(Ticket.priority.in_(["Critical", "Urgent"])).count()
    total_breached = bq().filter(Ticket.sla_breached == True,
                                  Ticket.current_status.notin_(["Resolved","Closed"])).count()

    days = days  # keep for template

    # ── Time-series ────────────────────────────────────────────────────────────
    raw_created = (db.session.query(func.date(Ticket.created_at).label("day"), func.count(Ticket.id))
                   .filter(*bf()).group_by(func.date(Ticket.created_at))
                   .order_by(func.date(Ticket.created_at)).all())
    res_f = bf() + [Ticket.solved_status == True, Ticket.solved_date.isnot(None)]
    raw_resolved = (db.session.query(func.date(Ticket.solved_date).label("day"), func.count(Ticket.id))
                    .filter(*res_f).group_by(func.date(Ticket.solved_date))
                    .order_by(func.date(Ticket.solved_date)).all())
    created_map  = {str(r[0]): r[1] for r in raw_created}
    resolved_map = {str(r[0]): r[1] for r in raw_resolved}
    date_labels, created_series, resolved_series = [], [], []
    cur = since.date()
    end = until.date()
    while cur <= end:
        s = str(cur)
        date_labels.append(s)
        created_series.append(created_map.get(s, 0))
        resolved_series.append(resolved_map.get(s, 0))
        cur += timedelta(days=1)

    # ── Breakdown data ──────────────────────────────────────────────────────────
    f = bf()
    status_data   = (db.session.query(Ticket.current_status, func.count(Ticket.id))
                     .filter(*f).group_by(Ticket.current_status).all())
    priority_data = (db.session.query(Ticket.priority, func.count(Ticket.id))
                     .filter(*f).group_by(Ticket.priority).all())
    channel_data  = (db.session.query(Ticket.channel, func.count(Ticket.id))
                     .filter(*f).group_by(Ticket.channel)
                     .order_by(func.count(Ticket.id).desc()).all())
    country_data  = (db.session.query(Country.name, func.count(Ticket.id))
                     .join(Ticket, Ticket.country_id == Country.id).filter(*f)
                     .group_by(Country.name).order_by(func.count(Ticket.id).desc()).all())
    category_data = (db.session.query(IssueCategory.name, func.count(Ticket.id))
                     .join(Ticket, Ticket.category_id == IssueCategory.id).filter(*f)
                     .group_by(IssueCategory.name).order_by(func.count(Ticket.id).desc()).limit(10).all())

    # ── SLA ────────────────────────────────────────────────────────────────────
    sla_base = bf() + [Ticket.solved_status == True, Ticket.due_date.isnot(None)]
    sla_compliant = Ticket.query.filter(*sla_base, Ticket.solved_date <= Ticket.due_date).count()
    sla_failed    = Ticket.query.filter(*sla_base, Ticket.solved_date > Ticket.due_date).count()
    sla_eligible  = sla_compliant + sla_failed
    sla_rate      = round(sla_compliant / sla_eligible * 100, 1) if sla_eligible else None

    # ── CSAT ───────────────────────────────────────────────────────────────────
    csat_f     = [CSATRating.rating.isnot(None), CSATRating.created_at >= since, CSATRating.created_at < until]
    csat_avg   = db.session.query(func.avg(CSATRating.rating)).filter(*csat_f).scalar()
    csat_count = CSATRating.query.filter(*csat_f).count()
    csat_dist  = (db.session.query(CSATRating.rating, func.count(CSATRating.id))
                  .filter(*csat_f).group_by(CSATRating.rating).order_by(CSATRating.rating).all())

    # ── Avg resolution time ────────────────────────────────────────────────────
    res_tickets   = bq().filter(Ticket.solved_status == True, Ticket.solved_date.isnot(None)).all()
    avg_res_hours = None
    if res_tickets:
        avg_res_hours = round(
            sum((t.solved_date - t.created_at).total_seconds() / 3600 for t in res_tickets)
            / len(res_tickets), 1)

    # ── Agent performance ──────────────────────────────────────────────────────
    agent_rows = (
        db.session.query(User.id, User.full_name, User.role,
                         func.count(Ticket.id).label("total"),
                         func.sum(db.case((Ticket.solved_status == True, 1), else_=0)).label("resolved"))
        .outerjoin(Ticket, db.and_(Ticket.assigned_to_id == User.id,
                                   Ticket.created_at >= since, Ticket.created_at < until,
                                   *([Ticket.country_id == country_f] if country_f else [])))
        .filter(User.role.in_([Role.ADMIN, Role.AGENT]), User.is_active == True)
        .group_by(User.id).all()
    )
    agent_res_map = dict(
        db.session.query(Ticket.assigned_to_id,
                         func.avg((func.julianday(Ticket.solved_date) - func.julianday(Ticket.created_at)) * 24))
        .filter(Ticket.solved_status == True, Ticket.solved_date.isnot(None),
                Ticket.created_at >= since, Ticket.created_at < until)
        .group_by(Ticket.assigned_to_id).all())
    csat_agent_map = dict(
        db.session.query(Ticket.assigned_to_id, func.avg(CSATRating.rating))
        .join(CSATRating, CSATRating.ticket_id == Ticket.id)
        .filter(CSATRating.rating.isnot(None), Ticket.assigned_to_id.isnot(None),
                Ticket.created_at >= since, Ticket.created_at < until)
        .group_by(Ticket.assigned_to_id).all())
    agents = sorted([{
        "name": r.full_name, "role": r.role.value,
        "total": r.total or 0, "resolved": r.resolved or 0,
        "rate": round((r.resolved or 0) / (r.total or 1) * 100),
        "avg_hours": round(agent_res_map.get(r.id) or 0, 1),
        "csat": round(csat_agent_map.get(r.id) or 0, 2) if csat_agent_map.get(r.id) else None,
    } for r in agent_rows], key=lambda a: a["resolved"], reverse=True)

    # ── Filter dropdown data ───────────────────────────────────────────────────
    countries  = Country.query.filter_by(is_active=True).order_by(Country.name).all()
    assignable = User.query.filter(
        User.role.in_([Role.AGENT, Role.ADMIN, Role.SUPER_ADMIN]), User.is_active == True
    ).order_by(User.full_name).all()

    return render_template(
        "admin/analytics.html",
        # Filters
        date_from_f=date_from_f, date_to_f=date_to_f,
        days=days, since=since, until=until,
        country_f=country_f, assigned_f=assigned_f,
        status_f=status_f, priority_f=priority_f, channel_f=channel_f,
        # KPIs
        total=total, total_open=total_open, total_inprog=total_inprog,
        total_resolved=total_resolved, total_critical=total_critical,
        total_breached=total_breached, avg_res_hours=avg_res_hours,
        csat_avg=round(csat_avg, 2) if csat_avg else None,
        csat_count=csat_count, csat_dist=csat_dist,
        sla_rate=sla_rate, sla_compliant=sla_compliant,
        sla_failed=sla_failed,
        # Charts
        date_labels=date_labels, created_series=created_series,
        resolved_series=resolved_series, status_data=status_data,
        priority_data=priority_data, channel_data=channel_data,
        country_data=country_data, category_data=category_data,
        # Agent table
        agents=agents,
        # Resolved display names for filter chips
        country_name=next((c.name for c in countries if c.id == country_f), None),
        agent_name=next((a.full_name for a in assignable if a.id == assigned_f), None),
        # Dropdowns
        countries=countries, assignable=assignable,
        statuses=["Open","In Progress","Pending","Resolved","Closed","Reopened"],
        priorities=["Urgent","Critical","High","Medium","Low"],
        channels=["web","email","whatsapp","telegram","api"],
    )


# ── Audit Log ──────────────────────────────────────────────────────────────────

@dashboard.route("/admin/audit-log")
@login_required
def audit_log():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    from models import LoginAuditLog
    page = request.args.get("page", 1, type=int)
    event_f = request.args.get("event", "")
    user_f = request.args.get("user", "")

    q = TicketHistory.query.order_by(TicketHistory.created_at.desc())
    login_q = LoginAuditLog.query.order_by(LoginAuditLog.created_at.desc())

    if event_f:
        login_q = login_q.filter(LoginAuditLog.event == event_f)
    if user_f:
        login_q = login_q.filter(LoginAuditLog.username.ilike(f"%{user_f}%"))

    ticket_events = q.limit(200).all()
    login_events = login_q.limit(200).all()

    return render_template(
        "admin/audit_log.html",
        ticket_events=ticket_events,
        login_events=login_events,
        event_f=event_f,
        user_f=user_f,
    )


# ── Viewer dashboard ───────────────────────────────────────────────────────────

def _viewer_view():
    from models import IssueCategory, CSATRating
    from datetime import date as _date

    days = int(request.args.get("days", 30))
    days = max(7, min(days, 365))
    since = datetime.utcnow() - timedelta(days=days)

    # Aggregate KPIs only — no ticket rows, no PII
    all_q = Ticket.query
    stats = {
        "total":      all_q.count(),
        "open":       all_q.filter(Ticket.current_status == "Open").count(),
        "in_progress":all_q.filter(Ticket.current_status == "In Progress").count(),
        "resolved":   all_q.filter(Ticket.solved_status == True).count(),
        "critical":   all_q.filter(Ticket.priority.in_(["Critical", "Urgent"])).count(),
        "sla_breached":all_q.filter(Ticket.sla_breached == True,
                                    Ticket.current_status.notin_(["Resolved","Closed"])).count(),
    }
    resolution_rate = round(stats["resolved"] / stats["total"] * 100, 1) if stats["total"] else 0

    # Time-series
    raw_created = (
        db.session.query(func.date(Ticket.created_at).label("day"), func.count(Ticket.id))
        .filter(Ticket.created_at >= since)
        .group_by(func.date(Ticket.created_at))
        .order_by(func.date(Ticket.created_at))
        .all()
    )
    raw_resolved = (
        db.session.query(func.date(Ticket.solved_date).label("day"), func.count(Ticket.id))
        .filter(Ticket.solved_status == True, Ticket.solved_date >= since)
        .group_by(func.date(Ticket.solved_date))
        .order_by(func.date(Ticket.solved_date))
        .all()
    )
    created_map = {str(r[0]): r[1] for r in raw_created}
    resolved_map = {str(r[0]): r[1] for r in raw_resolved}
    date_labels, created_series, resolved_series = [], [], []
    cur = since.date()
    end = datetime.utcnow().date()
    while cur <= end:
        s = str(cur)
        date_labels.append(s)
        created_series.append(created_map.get(s, 0))
        resolved_series.append(resolved_map.get(s, 0))
        cur += timedelta(days=1)

    # By status
    status_data = db.session.query(Ticket.current_status, func.count(Ticket.id)).group_by(Ticket.current_status).all()
    # By priority
    priority_data = db.session.query(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority).all()
    # By channel
    channel_data = db.session.query(Ticket.channel, func.count(Ticket.id)).group_by(Ticket.channel).all()
    # By country
    from models import Country
    country_data = (
        db.session.query(Country.name, func.count(Ticket.id))
        .join(Ticket, Ticket.country_id == Country.id)
        .group_by(Country.name)
        .order_by(func.count(Ticket.id).desc())
        .all()
    )
    # CSAT
    csat_avg = db.session.query(func.avg(CSATRating.rating)).filter(CSATRating.rating.isnot(None)).scalar()
    sla_compliant = Ticket.query.filter(
        Ticket.solved_status == True, Ticket.due_date.isnot(None),
        Ticket.solved_date <= Ticket.due_date,
    ).count()
    sla_eligible = Ticket.query.filter(Ticket.solved_status == True, Ticket.due_date.isnot(None)).count()
    sla_rate = round(sla_compliant / sla_eligible * 100, 1) if sla_eligible else None

    return render_template(
        "portal/viewer_dashboard.html",
        stats=stats,
        resolution_rate=resolution_rate,
        days=days,
        since=since,
        date_labels=date_labels,
        created_series=created_series,
        resolved_series=resolved_series,
        status_data=status_data,
        priority_data=priority_data,
        channel_data=channel_data,
        country_data=country_data,
        csat_avg=round(csat_avg, 2) if csat_avg else None,
        sla_rate=sla_rate,
    )


# ── Region Role Management ─────────────────────────────────────────────────────

@dashboard.route("/admin/users/<int:user_id>/region-roles/add", methods=["POST"])
@login_required
def add_region_role(user_id):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    from models import UserRegionRole, Country
    target = User.query.get_or_404(user_id)

    # ── Cadre check: can only manage users strictly below your level ──────────
    my_level     = ROLE_LEVEL.get(current_user.role, 0)
    target_level = ROLE_LEVEL.get(target.role, 0)
    if my_level <= target_level:
        flash(f"You cannot assign regions to a {target.role.value} — that role is at or above yours.", "danger")
        return redirect(url_for("dashboard.users"))

    try:
        role = Role(request.form.get("role"))
    except ValueError:
        flash("Invalid role.", "warning")
        return redirect(url_for("dashboard.users"))

    # Cannot grant a role at or above your own level
    if ROLE_LEVEL.get(role, 0) >= my_level:
        flash(f"You cannot grant the {role.value} role — it is at or above your own level.", "danger")
        return redirect(url_for("dashboard.users"))

    country_id = request.form.get("country_id", type=int) or None
    admin1_id  = request.form.get("admin1_id",  type=int) or None

    # ── Scope check: non-super-admins can only assign within their own region ─
    if current_user.role != Role.SUPER_ADMIN and country_id:
        allowed_cids = set()
        if current_user.country_id:
            allowed_cids.add(current_user.country_id)
        for rr in (current_user.region_roles or []):
            if rr.country_id:
                allowed_cids.add(rr.country_id)
        if allowed_cids and country_id not in allowed_cids:
            flash("You can only assign regions within your own scope.", "danger")
            return redirect(url_for("dashboard.users"))

    existing = UserRegionRole.query.filter_by(
        user_id=target.id, role=role, country_id=country_id
    ).first()
    if existing:
        flash("That role/region combination already exists for this user.", "warning")
        return redirect(url_for("dashboard.users"))

    db.session.add(UserRegionRole(
        user_id=target.id, role=role,
        country_id=country_id, admin1_id=admin1_id,
        granted_by_id=current_user.id,
    ))
    db.session.commit()
    scope = Country.query.get(country_id).name if country_id else "Global"
    flash(f"{role.value} role ({scope}) granted to {target.full_name}.", "success")
    return redirect(url_for("dashboard.users"))


@dashboard.route("/admin/region-roles/<int:role_id>/delete", methods=["POST"])
@login_required
def delete_region_role(role_id):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    from models import UserRegionRole
    rr = UserRegionRole.query.get_or_404(role_id)
    # Cadre check: can only remove roles from users below your level
    target = rr.user
    if target and ROLE_LEVEL.get(target.role, 0) >= ROLE_LEVEL.get(current_user.role, 0):
        flash("You cannot modify regional roles for a user at or above your level.", "danger")
        return redirect(url_for("dashboard.users"))
    db.session.delete(rr)
    db.session.commit()
    flash("Regional role removed.", "success")
    return redirect(url_for("dashboard.users"))
