from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import db, User, Role, Country, Ticket, NudgeLog, BroadcastMessage, CSATRating, Notification
from datetime import datetime, timedelta, date as date_type
from whatsapp_client import send as _wa_send_broadcast

nudges = Blueprint('nudges', __name__, url_prefix='/admin')


# ── GET /admin/broadcasts ────────────────────────────────────────────────────────

@nudges.route('/broadcasts', methods=['GET'])
@login_required
def broadcasts():
    if not current_user.role in (Role.SUPER_ADMIN, Role.ADMIN):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.index'))

    broadcast_list = (
        BroadcastMessage.query
        .order_by(BroadcastMessage.sent_at.desc())
        .limit(50)
        .all()
    )
    countries = Country.query.order_by(Country.name).all()
    roles = list(Role)

    return render_template(
        'admin/broadcasts.html',
        broadcasts=broadcast_list,
        countries=countries,
        roles=roles,
    )


# ── POST /admin/broadcasts/send ─────────────────────────────────────────────────

@nudges.route('/broadcasts/send', methods=['POST'])
@login_required
def send_broadcast():
    if not current_user.role in (Role.SUPER_ADMIN, Role.ADMIN):
        flash('Access denied.', 'danger')
        return redirect(url_for('nudges.broadcasts'))

    title = request.form.get('title', '').strip()
    message = request.form.get('message', '').strip()
    country_ids = request.form.getlist('country_ids')   # list of str, empty = all
    role_values = request.form.getlist('roles')         # list of str, empty = all

    if not title or not message:
        flash('Title and message are required.', 'warning')
        return redirect(url_for('nudges.broadcasts'))

    # Build base query for active users
    query = User.query.filter_by(is_active=True)

    if country_ids:
        try:
            cid_ints = [int(c) for c in country_ids]
        except ValueError:
            cid_ints = []
        if cid_ints:
            query = query.filter(User.country_id.in_(cid_ints))

    if role_values:
        # Convert string values back to Role enum members
        role_enums = []
        for rv in role_values:
            for r in Role:
                if r.value == rv or r.name == rv:
                    role_enums.append(r)
                    break
        if role_enums:
            query = query.filter(User.role.in_(role_enums))

    target_users = query.all()

    recipient_count = 0
    for user in target_users:
        phone = user.contact
        if not phone:
            continue

        _wa_send_broadcast(phone, message)

        nudge = NudgeLog(
            ticket_id=None,
            nudge_type='broadcast',
            recipient=phone,
            channel='whatsapp',
            message_preview=message[:200],
            status='sent',
            sent_at=datetime.utcnow(),
        )
        db.session.add(nudge)
        recipient_count += 1

    # Coerce IDs/values to plain lists for JSON storage
    stored_country_ids = [int(c) for c in country_ids] if country_ids else []
    stored_roles = role_values if role_values else []

    broadcast_record = BroadcastMessage(
        title=title,
        message=message,
        target_country_ids=stored_country_ids,
        target_roles=stored_roles,
        sent_by_id=current_user.id,
        sent_at=datetime.utcnow(),
        recipient_count=recipient_count,
        status='sent',
    )
    db.session.add(broadcast_record)

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error('send_broadcast commit failed: %s', exc)
        flash('Broadcast failed to save. Please try again.', 'danger')
        return redirect(url_for('nudges.broadcasts'))

    flash(f'Broadcast sent to {recipient_count} recipient(s).', 'success')
    return redirect(url_for('nudges.broadcasts'))


# ── GET /admin/nudge-log ─────────────────────────────────────────────────────────

@nudges.route('/nudge-log', methods=['GET'])
@login_required
def nudge_log():
    if not current_user.role in (Role.SUPER_ADMIN, Role.ADMIN):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.index'))

    logs = (
        NudgeLog.query
        .order_by(NudgeLog.sent_at.desc())
        .limit(200)
        .all()
    )

    return render_template('admin/nudge_log.html', logs=logs)


# ── GET /admin/csat ──────────────────────────────────────────────────────────────

@nudges.route('/csat', methods=['GET'])
@login_required
def csat_dashboard():
    if not current_user.can_view_reports():
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard.index'))

    submitted = CSATRating.query.filter(CSATRating.submitted_at.isnot(None)).all()
    total_created = CSATRating.query.count()
    total_submitted = len(submitted)

    # Average score
    if submitted:
        avg_score = round(sum(r.rating for r in submitted if r.rating) / total_submitted, 2)
    else:
        avg_score = 0.0

    # Score distribution
    score_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r in submitted:
        if r.rating and r.rating in score_counts:
            score_counts[r.rating] += 1

    # Response rate
    if total_created > 0:
        response_rate = round((total_submitted / total_created) * 100, 1)
    else:
        response_rate = 0.0

    # By agent: aggregate through ticket.assigned_to
    agent_stats = {}
    for r in submitted:
        if not r.rating:
            continue
        ticket = r.ticket
        if not ticket or not ticket.assigned_to_id:
            continue
        agent_id = ticket.assigned_to_id
        if agent_id not in agent_stats:
            agent = User.query.get(agent_id)
            agent_stats[agent_id] = {
                'agent_name': agent.full_name if agent else 'Unknown',
                'scores': [],
            }
        agent_stats[agent_id]['scores'].append(r.rating)

    by_agent = []
    for agent_id, data in agent_stats.items():
        scores = data['scores']
        by_agent.append({
            'agent_name': data['agent_name'],
            'avg_score': round(sum(scores) / len(scores), 2),
            'count': len(scores),
        })
    by_agent.sort(key=lambda x: x['avg_score'], reverse=True)

    # Recent 20 submitted ratings
    recent_ratings = (
        CSATRating.query
        .filter(CSATRating.submitted_at.isnot(None))
        .order_by(CSATRating.submitted_at.desc())
        .limit(20)
        .all()
    )

    # 30-day trend
    today = date_type.today()
    trend_labels = []
    trend_scores = []
    for i in range(29, -1, -1):
        day = today - timedelta(days=i)
        trend_labels.append(day.strftime('%d %b'))
        day_ratings = [r.rating for r in submitted
                       if r.submitted_at and r.submitted_at.date() == day and r.rating]
        trend_scores.append(round(sum(day_ratings) / len(day_ratings), 2) if day_ratings else None)

    return render_template(
        'admin/csat_dashboard.html',
        avg_score=avg_score,
        score_counts=score_counts,
        total_ratings=total_submitted,
        response_rate=response_rate,
        by_agent=by_agent,
        recent_ratings=recent_ratings,
        trend_labels=trend_labels,
        trend_scores=trend_scores,
    )


# ── POST /admin/nudge/aging-check ────────────────────────────────────────────────

@nudges.route('/nudge/aging-check', methods=['POST'])
@login_required
def aging_check():
    if current_user.role != Role.SUPER_ADMIN:
        return jsonify({'error': 'Super Admin access required.'}), 403

    resolved_statuses = ('Resolved', 'Closed')
    urgent_priorities = ('Critical', 'High', 'Urgent')
    cutoff = datetime.utcnow() - timedelta(hours=4)

    tickets = (
        Ticket.query
        .filter(
            ~Ticket.current_status.in_(resolved_statuses),
            Ticket.priority.in_(urgent_priorities),
            Ticket.first_response_at.is_(None),
            Ticket.created_at <= cutoff,
        )
        .all()
    )

    checked = len(tickets)
    alerted = 0

    for ticket in tickets:
        if not ticket.assigned_to_id:
            continue

        notif = Notification(
            user_id=ticket.assigned_to_id,
            ticket_id=ticket.id,
            message=(
                f'Aging alert: Ticket {ticket.sl_no} ({ticket.priority}) has had no first '
                f'response for over 4 hours.'
            ),
            notif_type='warning',
        )
        db.session.add(notif)
        alerted += 1

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error('aging_check commit failed: %s', exc)
        return jsonify({'error': 'Database error during aging check.'}), 500

    return jsonify({'checked': checked, 'alerted': alerted})
