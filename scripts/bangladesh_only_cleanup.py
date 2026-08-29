"""
One-off migration: strip every non-Bangladesh country from the database so
the tool is Bangladesh-only end to end.

- Deletes all tickets (and every dependent row - comments, history,
  attachments, CSAT, time entries, call logs, watchers, links, notifications,
  nudge log entries, custom field values) for any ticket tagged to a
  non-Bangladesh country. Tickets with no country tag are left alone.
- Deletes escalation matrices for non-Bangladesh countries (Bangladesh's own
  matrix, entered by hand through the admin UI, is left untouched).
- Deletes UserRegionRole rows scoped to a non-Bangladesh country.
- Reassigns any user whose profile points at a non-Bangladesh country/admin
  region back to Bangladesh, clearing the more specific admin1/admin2 so
  nobody is left pointing at a region that no longer exists. No user
  accounts are deleted.
- Deletes the AdminLevel1/2/3 hierarchy and the Country rows themselves for
  every country except Bangladesh.

SQLite's ondelete="CASCADE" annotations in models.py are NOT enforced by this
app (foreign_keys pragma is never turned on), so every dependent table is
cleaned up explicitly here rather than relying on the database to cascade.

Usage:  python scripts/bangladesh_only_cleanup.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import (
    db, Country, AdminLevel1, AdminLevel2, AdminLevel3,
    Ticket, TicketComment, TicketHistory, TicketAttachment, CSATRating,
    TimeEntry, CallLog, TicketWatcher, TicketLink, Notification, NudgeLog,
    TicketFieldValue, CountryEscalationMatrix, UserRegionRole, User,
)

app = create_app()

with app.app_context():
    bd = Country.query.filter_by(code="BD").first()
    if not bd:
        raise SystemExit("Bangladesh country row not found - aborting.")

    non_bd = Country.query.filter(Country.code != "BD").all()
    non_bd_ids = [c.id for c in non_bd]
    print("Bangladesh id:", bd.id)
    print("Removing countries:", ", ".join(f"{c.name} ({c.id})" for c in non_bd))

    # ── 1. Delete every ticket tagged to a non-Bangladesh country ───────────
    doomed_tickets = Ticket.query.filter(Ticket.country_id.in_(non_bd_ids)).all()
    doomed_ids = [t.id for t in doomed_tickets]
    print(f"\nDeleting {len(doomed_ids)} non-Bangladesh tickets and their dependents...")

    if doomed_ids:
        TicketComment.query.filter(TicketComment.ticket_id.in_(doomed_ids)).delete(synchronize_session=False)
        TicketHistory.query.filter(TicketHistory.ticket_id.in_(doomed_ids)).delete(synchronize_session=False)
        TicketAttachment.query.filter(TicketAttachment.ticket_id.in_(doomed_ids)).delete(synchronize_session=False)
        CSATRating.query.filter(CSATRating.ticket_id.in_(doomed_ids)).delete(synchronize_session=False)
        TimeEntry.query.filter(TimeEntry.ticket_id.in_(doomed_ids)).delete(synchronize_session=False)
        CallLog.query.filter(CallLog.ticket_id.in_(doomed_ids)).delete(synchronize_session=False)
        TicketWatcher.query.filter(TicketWatcher.ticket_id.in_(doomed_ids)).delete(synchronize_session=False)
        TicketLink.query.filter(
            db.or_(TicketLink.source_id.in_(doomed_ids), TicketLink.target_id.in_(doomed_ids))
        ).delete(synchronize_session=False)
        Notification.query.filter(Notification.ticket_id.in_(doomed_ids)).delete(synchronize_session=False)
        NudgeLog.query.filter(NudgeLog.ticket_id.in_(doomed_ids)).delete(synchronize_session=False)
        TicketFieldValue.query.filter(TicketFieldValue.ticket_id.in_(doomed_ids)).delete(synchronize_session=False)

        # Defensive: any surviving ticket whose parent was just deleted loses the link, not itself
        Ticket.query.filter(Ticket.parent_id.in_(doomed_ids)).update({"parent_id": None}, synchronize_session=False)

        Ticket.query.filter(Ticket.id.in_(doomed_ids)).delete(synchronize_session=False)

    db.session.commit()
    print("Tickets remaining:", Ticket.query.count())

    # ── 2. Escalation matrices for removed countries ────────────────────────
    n_matrix = CountryEscalationMatrix.query.filter(
        CountryEscalationMatrix.country_id.in_(non_bd_ids)
    ).delete(synchronize_session=False)
    print(f"\nDeleted {n_matrix} non-Bangladesh escalation matrix row(s).")
    db.session.commit()

    # ── 3. UserRegionRole rows scoped to removed countries ──────────────────
    n_roles = UserRegionRole.query.filter(
        UserRegionRole.country_id.in_(non_bd_ids)
    ).delete(synchronize_session=False)
    print(f"Deleted {n_roles} non-Bangladesh UserRegionRole row(s).")
    db.session.commit()

    # ── 4. Reassign affected users back to Bangladesh (no accounts deleted) ─
    affected_users = User.query.filter(
        db.or_(
            User.country_id.in_(non_bd_ids),
            User.admin1_id.in_([a.id for a in AdminLevel1.query.filter(AdminLevel1.country_id.in_(non_bd_ids)).all()]),
        )
    ).all()
    print(f"\nReassigning {len(affected_users)} user(s) to Bangladesh:")
    for u in affected_users:
        print(f"  {u.username} was country_id={u.country_id} admin1_id={u.admin1_id}")
        u.country_id = bd.id
        u.admin1_id = None
        u.admin2_id = None
    db.session.commit()

    # ── 5. Admin hierarchy + country rows themselves ────────────────────────
    admin1_ids = [a.id for a in AdminLevel1.query.filter(AdminLevel1.country_id.in_(non_bd_ids)).all()]
    admin2_ids = [a.id for a in AdminLevel2.query.filter(AdminLevel2.level1_id.in_(admin1_ids)).all()] if admin1_ids else []

    if admin2_ids:
        n3 = AdminLevel3.query.filter(AdminLevel3.level2_id.in_(admin2_ids)).delete(synchronize_session=False)
        print(f"\nDeleted {n3} AdminLevel3 row(s).")
    if admin1_ids:
        n2 = AdminLevel2.query.filter(AdminLevel2.level1_id.in_(admin1_ids)).delete(synchronize_session=False)
        print(f"Deleted {n2} AdminLevel2 row(s).")
        n1 = AdminLevel1.query.filter(AdminLevel1.id.in_(admin1_ids)).delete(synchronize_session=False)
        print(f"Deleted {n1} AdminLevel1 row(s).")

    n_countries = Country.query.filter(Country.id.in_(non_bd_ids)).delete(synchronize_session=False)
    print(f"Deleted {n_countries} Country row(s).")
    db.session.commit()

    print("\nDone. Remaining countries:", [c.name for c in Country.query.all()])
    print("Remaining tickets:", Ticket.query.count())
