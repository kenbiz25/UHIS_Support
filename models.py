from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
import enum
import secrets

db = SQLAlchemy()


class Role(enum.Enum):
    SUPER_ADMIN = "Super Admin"
    ADMIN = "Admin"
    AGENT = "Agent"     # tiered L1-L4; L1 handles first contact, escalates up to L4
    REPORTER = "Reporter"
    VIEWER = "Viewer"


# ── Administrative Units ───────────────────────────────────────────────────────

class Country(db.Model):
    __tablename__ = "countries"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(5), unique=True)          # ISO 3166-1 alpha-2
    admin1_label = db.Column(db.String(50), default="Region")
    admin2_label = db.Column(db.String(50), default="District")
    admin3_label = db.Column(db.String(50), default="Sub-district")
    is_active = db.Column(db.Boolean, default=True)

    # Business hours configuration for SLA calculation
    timezone = db.Column(db.String(50), default="Africa/Nairobi")   # pytz timezone name
    work_start_hour = db.Column(db.Integer, default=8)               # 08:00 local time
    work_end_hour = db.Column(db.Integer, default=17)                # 17:00 local time
    working_days = db.Column(db.String(20), default="Mon-Fri")       # Mon-Fri | Sun-Thu | Mon-Sat

    level1_units = db.relationship("AdminLevel1", backref="country", lazy=True, cascade="all, delete-orphan")


class AdminLevel1(db.Model):
    __tablename__ = "admin_level1"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"), nullable=False)

    level2_units = db.relationship("AdminLevel2", backref="level1", lazy=True, cascade="all, delete-orphan")


class AdminLevel2(db.Model):
    __tablename__ = "admin_level2"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    level1_id = db.Column(db.Integer, db.ForeignKey("admin_level1.id"), nullable=False)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"), nullable=False)

    level3_units = db.relationship("AdminLevel3", backref="level2", lazy=True, cascade="all, delete-orphan")


class AdminLevel3(db.Model):
    __tablename__ = "admin_level3"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    level2_id = db.Column(db.Integer, db.ForeignKey("admin_level2.id"), nullable=False)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"), nullable=False)


# ── Issue Taxonomy ─────────────────────────────────────────────────────────────

class IssueCategory(db.Model):
    __tablename__ = "issue_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    icon = db.Column(db.String(50), default="bug")
    color = db.Column(db.String(20), default="primary")
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)

    subcategories = db.relationship(
        "IssueSubcategory", backref="category", lazy=True,
        cascade="all, delete-orphan", order_by="IssueSubcategory.display_order"
    )


class IssueSubcategory(db.Model):
    __tablename__ = "issue_subcategories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("issue_categories.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)


# ── WhatsApp Conversation Sessions ────────────────────────────────────────────

class WhatsAppSession(db.Model):
    __tablename__ = "whatsapp_sessions"

    phone = db.Column(db.String(30), primary_key=True)
    state = db.Column(db.String(50), default="INIT")
    data = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── User ───────────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.Enum(Role), nullable=False, default=Role.REPORTER)

    # Legacy string field (kept for backward compat)
    district = db.Column(db.String(100))

    # Structured location
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"))
    admin1_id = db.Column(db.Integer, db.ForeignKey("admin_level1.id"))
    admin2_id = db.Column(db.Integer, db.ForeignKey("admin_level2.id"))
    admin3_id = db.Column(db.Integer, db.ForeignKey("admin_level3.id"))

    country = db.relationship("Country", foreign_keys=[country_id])
    admin1 = db.relationship("AdminLevel1", foreign_keys=[admin1_id])
    admin2 = db.relationship("AdminLevel2", foreign_keys=[admin2_id])
    admin3 = db.relationship("AdminLevel3", foreign_keys=[admin3_id])

    contact = db.Column(db.String(20))
    email = db.Column(db.String(120), unique=True)
    timezone = db.Column(db.String(50), default="UTC")
    language = db.Column(db.String(10), default="en")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Agent tier (1-4). Only meaningful when role == Role.AGENT.
    agent_level = db.Column(db.Integer, nullable=True)

    reported_tickets = db.relationship(
        "Ticket", foreign_keys="Ticket.reporter_id", backref="reporter_user", lazy=True
    )
    assigned_tickets = db.relationship(
        "Ticket", foreign_keys="Ticket.assigned_to_id", backref="assignee", lazy=True
    )

    def is_admin(self):
        return self.role in (Role.SUPER_ADMIN, Role.ADMIN)

    def is_agent(self):
        return self.role == Role.AGENT

    def agent_level_label(self):
        return f"L{self.agent_level}" if self.agent_level else None

    def can_update_tickets(self):
        return self.role in (Role.SUPER_ADMIN, Role.ADMIN, Role.AGENT)

    def can_view_reports(self):
        return self.role in (Role.SUPER_ADMIN, Role.ADMIN, Role.AGENT, Role.VIEWER)

    def has_regional_role(self, role, country_id=None):
        q = UserRegionRole.query.filter_by(user_id=self.id, role=role)
        if country_id:
            q = q.filter(
                db.or_(
                    UserRegionRole.country_id == country_id,
                    UserRegionRole.country_id.is_(None),
                )
            )
        return q.first() is not None

    def all_roles_display(self):
        result = [(self.role.value, "Global")]
        for rr in self.region_roles:
            scope = rr.country.name if rr.country else "Global"
            if rr.admin1:
                scope += f" / {rr.admin1.name}"
            result.append((rr.role.value, scope))
        return result


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    sl_no = db.Column(db.String(50), unique=True)

    # Intake channel
    channel = db.Column(db.String(20), default="web")   # web | whatsapp | email | api | widget
    external_id = db.Column(db.String(200))              # dedup key for whatsapp/email
    whatsapp_phone = db.Column(db.String(30))             # set when channel='whatsapp'; agent replies relay here

    # Widget metadata (set when channel='widget')
    widget_app = db.Column(db.String(100))               # which app the widget is embedded in
    widget_page = db.Column(db.String(500))              # page URL where the widget was used

    # Location (string legacy)
    district = db.Column(db.String(100))
    upazila = db.Column(db.String(100))

    # Structured location
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id"))
    admin1_id = db.Column(db.Integer, db.ForeignKey("admin_level1.id"))
    admin2_id = db.Column(db.Integer, db.ForeignKey("admin_level2.id"))
    admin3_id = db.Column(db.Integer, db.ForeignKey("admin_level3.id"))

    ticket_country = db.relationship("Country", foreign_keys=[country_id])
    ticket_admin1 = db.relationship("AdminLevel1", foreign_keys=[admin1_id])
    ticket_admin2 = db.relationship("AdminLevel2", foreign_keys=[admin2_id])
    ticket_admin3 = db.relationship("AdminLevel3", foreign_keys=[admin3_id])

    # Issue taxonomy
    category_id = db.Column(db.Integer, db.ForeignKey("issue_categories.id"))
    subcategory_id = db.Column(db.Integer, db.ForeignKey("issue_subcategories.id"))

    ticket_category = db.relationship("IssueCategory", foreign_keys=[category_id])
    ticket_subcategory = db.relationship("IssueSubcategory", foreign_keys=[subcategory_id])

    # Reporter
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    issue_reported_by_role = db.Column(db.String(50))
    issue_reporter_name = db.Column(db.String(150))
    issue_reporter_contact = db.Column(db.String(20))
    reporting_date = db.Column(db.DateTime, default=datetime.utcnow)
    issue_start_date = db.Column(db.DateTime)
    form_submit_email = db.Column(db.String(120))

    # Issue details
    spice_platform = db.Column(db.String(100))
    issue_type = db.Column(db.String(100))
    problem_details = db.Column(db.Text)
    problem_faced_by = db.Column(db.String(150))
    app_user_information = db.Column(db.Text)
    app_version = db.Column(db.String(50))
    product = db.Column(db.String(100))
    dso_name = db.Column(db.String(150))

    # Media & notes
    screenshot_path = db.Column(db.String(300))
    comments = db.Column(db.Text)

    # Assignment
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Status tracking
    task_initial_status = db.Column(db.String(50), default="New")
    current_status = db.Column(db.String(50), default="Open")
    priority = db.Column(db.String(20), default="Medium")
    escalation_level = db.Column(db.Integer, default=0)

    # Resolution
    solved_status = db.Column(db.Boolean, default=False)
    solved_date = db.Column(db.DateTime)
    solved_by = db.Column(db.String(150))
    remarks = db.Column(db.Text)

    # Notifications
    notification_sent = db.Column(db.Boolean, default=False)
    last_notification_at = db.Column(db.DateTime)

    # SLA tracking
    due_date = db.Column(db.DateTime)
    first_response_at = db.Column(db.DateTime)
    sla_breached = db.Column(db.Boolean, default=False)

    # Collision detection
    locked_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    locked_at = db.Column(db.DateTime, nullable=True)

    # Hierarchy
    parent_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tags = db.relationship("Tag", secondary="ticket_tags", backref="tickets", lazy="dynamic")
    watchers = db.relationship("TicketWatcher", backref="ticket", cascade="all, delete-orphan", lazy=True)
    attachments = db.relationship("TicketAttachment", backref="ticket", cascade="all, delete-orphan", lazy=True)
    locked_by = db.relationship("User", foreign_keys=[locked_by_id])
    children = db.relationship("Ticket", backref=db.backref("parent", remote_side="Ticket.id"), lazy=True)
    custom_values = db.relationship("TicketFieldValue", backref="ticket", cascade="all, delete-orphan", lazy=True)
    time_entries = db.relationship("TimeEntry", backref="ticket", cascade="all, delete-orphan", lazy=True)

    @staticmethod
    def generate_sl_no():
        count = Ticket.query.count() + 1
        return f"TKT-{datetime.utcnow().strftime('%Y%m%d')}-{count:04d}"

    def priority_badge(self):
        return {
            "Urgent": "danger",
            "Critical": "danger",
            "High": "warning",
            "Medium": "info",
            "Low": "success",
        }.get(self.priority, "secondary")

    def status_badge(self):
        return {
            "Open": "danger",
            "In Progress": "warning",
            "Pending": "info",
            "Resolved": "success",
            "Closed": "secondary",
            "Reopened": "danger",
        }.get(self.current_status, "secondary")

    def required_agent_level(self):
        """Agent tier this ticket currently needs — L1 at creation, +1 per escalation, capped at L4."""
        return min(self.escalation_level + 1, 4)

    def level_label(self):
        return f"L{self.required_agent_level()}"

    def sla_status(self):
        if not self.due_date or self.current_status in ("Resolved", "Closed"):
            return "ok"
        now = datetime.utcnow()
        remaining = self.due_date - now
        if remaining.total_seconds() < 0:
            return "breached"
        if remaining.total_seconds() < 3600 * 4:
            return "warning"
        return "ok"

    def sla_remaining_str(self):
        if not self.due_date or self.current_status in ("Resolved", "Closed"):
            return None
        now = datetime.utcnow()
        diff = self.due_date - now
        if diff.total_seconds() < 0:
            secs = abs(diff.total_seconds())
            h = int(secs // 3600)
            m = int((secs % 3600) // 60)
            return f"Breached {h}h {m}m ago"
        h = int(diff.total_seconds() // 3600)
        m = int((diff.total_seconds() % 3600) // 60)
        return f"{h}h {m}m remaining"


# ── Comments ───────────────────────────────────────────────────────────────────

class TicketComment(db.Model):
    __tablename__ = "ticket_comments"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(
        db.Integer, db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False)  # Admin-only note
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship("User", backref="comments_written")
    ticket = db.relationship(
        "Ticket",
        backref=db.backref("ticket_comments", order_by="TicketComment.created_at", lazy=True),
    )


# ── Audit trail ────────────────────────────────────────────────────────────────

class TicketHistory(db.Model):
    __tablename__ = "ticket_history"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(
        db.Integer, db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    changed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(200), nullable=False)
    old_value = db.Column(db.String(300))
    new_value = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    changed_by = db.relationship("User", backref="history_actions")
    ticket = db.relationship(
        "Ticket",
        backref=db.backref("ticket_history", order_by="TicketHistory.created_at.desc()", lazy=True),
    )


# ── In-app notifications ───────────────────────────────────────────────────────

class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticket_id = db.Column(
        db.Integer, db.ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True
    )
    message = db.Column(db.String(400), nullable=False)
    notif_type = db.Column(db.String(20), default="info")
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="user_notifications")
    ticket = db.relationship("Ticket", backref="ticket_notifications")


# ── Tags ───────────────────────────────────────────────────────────────────────

ticket_tags = db.Table(
    "ticket_tags",
    db.Column("ticket_id", db.Integer, db.ForeignKey("tickets.id", ondelete="CASCADE"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    color = db.Column(db.String(20), default="secondary")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ── Canned Responses ───────────────────────────────────────────────────────────

class CannedResponse(db.Model):
    __tablename__ = "canned_responses"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    body = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default="General")
    is_active = db.Column(db.Boolean, default=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    created_by = db.relationship("User", backref="canned_responses")


# ── SLA Policies ───────────────────────────────────────────────────────────────

class SLAPolicy(db.Model):
    __tablename__ = "sla_policies"

    id = db.Column(db.Integer, primary_key=True)
    priority = db.Column(db.String(20), unique=True, nullable=False)   # ticket priority key
    code = db.Column(db.String(10))                                     # P1, P2, P3, P4, P5, OTP, OUTAGE
    severity = db.Column(db.String(30))                                 # CRITICAL, HIGH, MEDIUM, LOW, ENHANCEMENT
    definition = db.Column(db.Text)                                     # trigger description
    l1_owner = db.Column(db.String(100))
    first_response_hours = db.Column(db.Float, default=4.0)            # max first response (hours)
    resolution_hours = db.Column(db.Float, default=24.0)               # L1 resolution (hours)
    l2_resolution_hours = db.Column(db.Float)
    l3_resolution_hours = db.Column(db.Float)
    l4_resolution_hours = db.Column(db.Float)
    auto_escalate = db.Column(db.Boolean, default=False)
    auto_escalate_note = db.Column(db.String(100))
    notification_rule = db.Column(db.Text)
    is_24_7 = db.Column(db.Boolean, default=False)                     # True = clock never stops
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Ticket Watchers ────────────────────────────────────────────────────────────

class TicketWatcher(db.Model):
    __tablename__ = "ticket_watchers"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("ticket_id", "user_id"),)
    user = db.relationship("User", backref="watching")


# ── Ticket Attachments ─────────────────────────────────────────────────────────

class TicketAttachment(db.Model):
    __tablename__ = "ticket_attachments"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey("ticket_comments.id", ondelete="SET NULL"), nullable=True)
    filename = db.Column(db.String(300), nullable=False)
    original_name = db.Column(db.String(300))
    file_size = db.Column(db.Integer)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploaded_by = db.relationship("User", backref="uploaded_attachments")


# ── Ticket Links ───────────────────────────────────────────────────────────────

class TicketLink(db.Model):
    __tablename__ = "ticket_links"

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    target_id = db.Column(db.Integer, db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    link_type = db.Column(db.String(30), default="related")  # related | blocks | duplicates
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("source_id", "target_id"),)
    source = db.relationship("Ticket", foreign_keys=[source_id], backref="outgoing_links")
    target = db.relationship("Ticket", foreign_keys=[target_id], backref="incoming_links")
    created_by = db.relationship("User", foreign_keys=[created_by_id])


# ── Saved Views ────────────────────────────────────────────────────────────────

class SavedView(db.Model):
    __tablename__ = "saved_views"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_shared = db.Column(db.Boolean, default=False)
    filters_json = db.Column(db.JSON, default=dict)  # {status, priority, assigned, sla, date_from, date_to, search}
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship("User", backref="saved_views")


# ── Custom Fields ──────────────────────────────────────────────────────────────

class CustomField(db.Model):
    __tablename__ = "custom_fields"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    label = db.Column(db.String(100), nullable=False)
    field_type = db.Column(db.String(20), default="text")  # text | textarea | dropdown | checkbox | date | number
    options = db.Column(db.JSON, default=list)              # for dropdown: list of option strings
    is_required = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    values = db.relationship("TicketFieldValue", backref="field", cascade="all, delete-orphan", lazy=True)


class TicketFieldValue(db.Model):
    __tablename__ = "ticket_field_values"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey("custom_fields.id", ondelete="CASCADE"), nullable=False)
    value = db.Column(db.Text)

    __table_args__ = (db.UniqueConstraint("ticket_id", "field_id"),)


# ── Time Tracking ──────────────────────────────────────────────────────────────

class TimeEntry(db.Model):
    __tablename__ = "time_entries"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    minutes = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(300))
    logged_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="time_entries")


# ── CSAT Ratings ───────────────────────────────────────────────────────────────

class CSATRating(db.Model):
    __tablename__ = "csat_ratings"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, unique=True)
    rating = db.Column(db.Integer)  # 1-5
    feedback = db.Column(db.Text)
    token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(32))
    submitted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ticket = db.relationship("Ticket", backref=db.backref("csat_rating", uselist=False))


# ── Live Chat ──────────────────────────────────────────────────────────────────

class ChatSession(db.Model):
    __tablename__ = "chat_sessions"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False,
                      default=lambda: secrets.token_urlsafe(32))
    visitor_name = db.Column(db.String(150))
    visitor_email = db.Column(db.String(120))
    status = db.Column(db.String(20), default="open")  # open | assigned | closed
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assigned_to = db.relationship("User", backref="chat_sessions")
    ticket = db.relationship("Ticket", backref=db.backref("chat_session", uselist=False))
    messages = db.relationship("ChatMessage", backref="session", cascade="all, delete-orphan",
                               order_by="ChatMessage.created_at", lazy=True)


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    sender_type = db.Column(db.String(10), nullable=False)  # visitor | agent
    sender_name = db.Column(db.String(150))
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ── Telegram Sessions ──────────────────────────────────────────────────────────

class TelegramSession(db.Model):
    __tablename__ = "telegram_sessions"

    chat_id = db.Column(db.String(30), primary_key=True)
    username = db.Column(db.String(100))
    state = db.Column(db.String(50), default="INIT")
    data = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Call Logs ──────────────────────────────────────────────────────────────────

class CallLog(db.Model):
    __tablename__ = "call_logs"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True)
    agent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    caller_name = db.Column(db.String(150))
    caller_phone = db.Column(db.String(30))
    direction = db.Column(db.String(10), default="inbound")   # inbound | outbound
    duration_minutes = db.Column(db.Integer, default=0)
    outcome = db.Column(db.String(50), default="resolved")    # resolved | follow_up | no_answer | escalated
    notes = db.Column(db.Text)
    logged_at = db.Column(db.DateTime, default=datetime.utcnow)

    agent = db.relationship("User", backref="call_logs")
    ticket = db.relationship("Ticket", backref="call_logs")


# ── Automation Rules ───────────────────────────────────────────────────────────

class AutomationRule(db.Model):
    __tablename__ = "automation_rules"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, default=True)
    trigger_event = db.Column(db.String(40), nullable=False)
    # e.g. "ticket_created" | "status_changed" | "priority_changed" | "reply_received"
    conditions_json = db.Column(db.JSON, default=list)
    # [{field, operator, value}, ...]
    actions_json = db.Column(db.JSON, default=list)
    # [{type, params}, ...]
    run_order = db.Column(db.Integer, default=0)
    continue_on_match = db.Column(db.Boolean, default=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = db.relationship("User", backref="automation_rules")


# ── Knowledge Base ─────────────────────────────────────────────────────────────

class KBCategory(db.Model):
    __tablename__ = "kb_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50), default="book")
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    articles = db.relationship(
        "KBArticle", backref="category", lazy="dynamic",
        order_by="KBArticle.title"
    )

    def published_count(self):
        return self.articles.filter_by(is_published=True).count()


class KBArticle(db.Model):
    __tablename__ = "kb_articles"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    meta_description = db.Column(db.String(300))
    category_id = db.Column(db.Integer, db.ForeignKey("kb_categories.id"), nullable=False)
    is_published = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)
    helpful_yes = db.Column(db.Integer, default=0)
    helpful_no = db.Column(db.Integer, default=0)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author = db.relationship("User", backref="kb_articles")
    feedbacks = db.relationship("KBArticleFeedback", backref="article",
                                cascade="all, delete-orphan", lazy=True)

    def helpful_pct(self):
        total = self.helpful_yes + self.helpful_no
        return round(self.helpful_yes * 100 / total) if total else None


class KBArticleFeedback(db.Model):
    __tablename__ = "kb_article_feedback"

    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("kb_articles.id", ondelete="CASCADE"), nullable=False)
    ip_address = db.Column(db.String(45))
    is_helpful = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ── Branding Settings ──────────────────────────────────────────────────────────

class BrandingSettings(db.Model):
    __tablename__ = "branding_settings"

    id = db.Column(db.Integer, primary_key=True)
    app_name = db.Column(db.String(100), default="Bangladesh UHIS")
    tagline = db.Column(db.String(200), default="Multi-channel support platform")
    logo_url = db.Column(db.String(300))
    favicon_url = db.Column(db.String(300))
    primary_color = db.Column(db.String(20), default="#2514BE")
    nav_bg = db.Column(db.String(20), default="#1e2a38")
    support_email = db.Column(db.String(120))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get(cls):
        obj = cls.query.first()
        if not obj:
            obj = cls()
            db.session.add(obj)
            db.session.commit()
        return obj



# ── User Region Roles ──────────────────────────────────────────────────────────

class UserRegionRole(db.Model):
    __tablename__ = "user_region_roles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = db.Column(db.Enum(Role), nullable=False)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id", ondelete="CASCADE"), nullable=True)
    admin1_id = db.Column(db.Integer, db.ForeignKey("admin_level1.id", ondelete="CASCADE"), nullable=True)
    granted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "role", "country_id"),)

    user = db.relationship("User", foreign_keys=[user_id], backref="region_roles")
    country = db.relationship("Country", foreign_keys=[country_id])
    admin1 = db.relationship("AdminLevel1", foreign_keys=[admin1_id])
    granted_by = db.relationship("User", foreign_keys=[granted_by_id])


# ── Login Audit Log ────────────────────────────────────────────────────────────

class LoginAuditLog(db.Model):
    __tablename__ = "login_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = db.Column(db.String(80))
    event = db.Column(db.String(30))   # login_success | login_failed | logout | password_reset
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="login_logs")


# ── Country Escalation Matrices ────────────────────────────────────────────────

class CountryEscalationMatrix(db.Model):
    __tablename__ = "country_escalation_matrices"

    id = db.Column(db.Integer, primary_key=True)
    country_id = db.Column(db.Integer, db.ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)
    levels_json = db.Column(db.JSON, default=list)  # list of level dicts
    streams_json = db.Column(db.JSON, default=list)  # for multi-stream escalation flows
    notes = db.Column(db.Text)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    country = db.relationship("Country", backref=db.backref("escalation_matrix", uselist=False))
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])


# ── Nudge Logs ─────────────────────────────────────────────────────────────────

class NudgeLog(db.Model):
    __tablename__ = "nudge_logs"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True)
    nudge_type = db.Column(db.String(50))   # csat_whatsapp | aging_alert | broadcast | csat_email
    recipient = db.Column(db.String(100))   # phone or email
    channel = db.Column(db.String(20), default="whatsapp")
    message_preview = db.Column(db.String(200))
    status = db.Column(db.String(20), default="sent")  # sent | failed | responded
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    response = db.Column(db.Text)
    responded_at = db.Column(db.DateTime)
    ticket = db.relationship("Ticket", backref="nudge_logs")


# ── Broadcast Messages ─────────────────────────────────────────────────────────

class BroadcastMessage(db.Model):
    __tablename__ = "broadcast_messages"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    target_country_ids = db.Column(db.JSON, default=list)
    target_roles = db.Column(db.JSON, default=list)
    sent_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    recipient_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="sent")
    sent_by = db.relationship("User", backref="broadcasts_sent")


# ── UI Translation Cache ────────────────────────────────────────────────────────

class TranslationCache(db.Model):
    __tablename__ = "translation_cache"
    id = db.Column(db.Integer, primary_key=True)
    lang = db.Column(db.String(10), nullable=False)
    text_hash = db.Column(db.String(64), nullable=False)
    source_text = db.Column(db.Text, nullable=False)
    translated_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("lang", "text_hash", name="uq_translation_cache_lang_hash"),
    )
