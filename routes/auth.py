import re
import secrets
from urllib.parse import urlparse, urljoin

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Role, Country, AdminLevel1, AdminLevel2, AdminLevel3, LoginAuditLog
from utils import generate_reset_token, verify_reset_token, send_reset_email, send_notification
from extensions import limiter, oauth
from translation import SUPPORTED_LANGUAGES


def _is_safe_redirect(target):
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc


def _unique_username_from_email(email):
    """Derive a unique username from an SSO email's local-part, e.g.
    'rahim.uddin@gmail.com' -> 'rahim.uddin', appending a numeric suffix
    on collision."""
    base = re.sub(r"[^a-z0-9._-]", "", email.split("@")[0].lower()) or "user"
    candidate = base
    n = 1
    while User.query.filter_by(username=candidate).first():
        n += 1
        candidate = f"{base}{n}"
    return candidate

auth = Blueprint("auth", __name__)


@auth.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute; 30 per hour")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.main"))
    if request.method == "POST":
        form_username = request.form.get("username", "").strip()
        username = form_username
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.is_active and check_password_hash(user.password_hash, password):
            login_user(user, remember=request.form.get("remember") == "on")
            session["lang"] = user.language or "en"
            from models import LoginAuditLog, db
            db.session.add(LoginAuditLog(
                user_id=user.id, username=user.username,
                event="login_success",
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent", "")[:300],
            ))
            db.session.commit()
            next_page = request.args.get("next")
            if next_page and not _is_safe_redirect(next_page):
                next_page = None
            return redirect(next_page or url_for("dashboard.main"))
        from models import LoginAuditLog, db
        db.session.add(LoginAuditLog(
            username=form_username, event="login_failed",
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", "")[:300],
        ))
        db.session.commit()
        flash("Invalid username or password.", "danger")
    countries = Country.query.filter_by(is_active=True).order_by(Country.name).all()
    return render_template("auth.html", active_view="login", countries=countries)


@auth.route("/login/oauth/<provider>")
@limiter.limit("10 per minute; 30 per hour")
def oauth_login(provider):
    if provider not in ("google", "microsoft"):
        flash("Unknown sign-in provider.", "danger")
        return redirect(url_for("auth.login"))
    client = oauth.create_client(provider)
    if not client:
        flash(f"{provider.title()} sign-in isn't configured yet. Contact your administrator.", "warning")
        return redirect(url_for("auth.login"))
    redirect_uri = url_for("auth.oauth_callback", provider=provider, _external=True)
    return client.authorize_redirect(redirect_uri)


@auth.route("/login/oauth/<provider>/callback")
def oauth_callback(provider):
    client = oauth.create_client(provider)
    if not client:
        flash("Unknown sign-in provider.", "danger")
        return redirect(url_for("auth.login"))

    token = client.authorize_access_token()

    if provider == "google":
        profile = token.get("userinfo") or client.get("userinfo", token=token).json()
        email = profile.get("email")
        display_name = profile.get("name") or email
    else:  # microsoft
        profile = client.get("https://graph.microsoft.com/v1.0/me", token=token).json()
        email = profile.get("mail") or profile.get("userPrincipalName")
        display_name = profile.get("displayName") or email

    if not email:
        flash(f"{provider.title()} did not return an email address. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
    created_now = False
    if not user:
        # Self-service account creation via SSO, same role a regular signup
        # gets (Role.REPORTER) - reduces admin overhead of pre-creating every
        # staff account by hand. No country/region assignment is possible
        # here (SSO doesn't tell us that); an admin can add it later via
        # Admin -> Users -> Manage Regions if needed.
        user = User(
            username=_unique_username_from_email(email),
            password_hash=generate_password_hash(secrets.token_urlsafe(32)),
            full_name=display_name or email,
            role=Role.REPORTER,
            email=email,
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(LoginAuditLog(
            user_id=user.id, username=user.username, event="account_created",
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", "")[:300],
        ))
        created_now = True
    if not user.is_active:
        flash("Your account is deactivated. Contact your administrator.", "danger")
        return redirect(url_for("auth.login"))

    login_user(user)
    session["lang"] = user.language or "en"
    db.session.add(LoginAuditLog(
        user_id=user.id, username=user.username,
        event="login_success",
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "")[:300],
    ))
    db.session.commit()
    if created_now:
        flash(
            f"Welcome, {display_name}! Your account has been created. "
            "Please take a moment to add your division/district in Preferences.",
            "success",
        )
        return redirect(url_for("auth.preferences"))
    flash(f"Welcome back, {display_name}!", "success")
    return redirect(url_for("dashboard.main"))


@auth.route("/set-language/<lang>")
def set_language(lang):
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"
    session["lang"] = lang
    if current_user.is_authenticated:
        current_user.language = lang
        db.session.commit()
    target = request.args.get("next") or request.referrer
    if not target or not _is_safe_redirect(target):
        target = url_for("dashboard.main")
    return redirect(target)


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth.route("/register", methods=["GET", "POST"])
@login_required
def register():
    if not current_user.is_admin():
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for("dashboard.main"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return render_template("register.html", roles=Role)

        email = request.form.get("email", "").strip() or None
        if email and User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return render_template("register.html", roles=Role)

        try:
            role = Role(request.form.get("role"))
        except ValueError:
            flash("Invalid role selected.", "danger")
            return render_template("register.html", roles=Role)

        if role == Role.SUPER_ADMIN and current_user.role != Role.SUPER_ADMIN:
            flash("Only Super Admin can create Super Admin accounts.", "danger")
            return render_template("register.html", roles=Role)

        country_id = request.form.get("country_id", type=int)
        admin1_id = request.form.get("admin1_id", type=int) or None
        admin2_id = request.form.get("admin2_id", type=int) or None
        admin3_id = request.form.get("admin3_id", type=int) or None

        # Build legacy district string from structured location
        district_str = request.form.get("district", "").strip() or None
        if not district_str and admin2_id:
            a2 = AdminLevel2.query.get(admin2_id)
            district_str = a2.name if a2 else None

        agent_level = request.form.get("agent_level", type=int) if role == Role.AGENT else None
        if role == Role.AGENT and agent_level not in (1, 2, 3, 4):
            agent_level = 1

        user = User(
            username=username,
            password_hash=generate_password_hash(request.form.get("password")),
            full_name=request.form.get("full_name", "").strip(),
            role=role,
            agent_level=agent_level,
            district=district_str,
            country_id=country_id or None,
            admin1_id=admin1_id,
            admin2_id=admin2_id,
            admin3_id=admin3_id,
            contact=request.form.get("contact", "").strip() or None,
            email=email,
        )
        db.session.add(user)
        db.session.flush()  # get user.id

        # Handle regional role assignments submitted with the form
        # Form fields: region_role[] (role value), region_country[] (country id), region_admin1[] (admin1 id)
        region_roles = request.form.getlist("region_role")
        region_countries = request.form.getlist("region_country")
        region_admin1s = request.form.getlist("region_admin1")
        from models import UserRegionRole
        for r_role_str, r_country_str, r_admin1_str in zip(region_roles, region_countries, region_admin1s):
            if not r_role_str:
                continue
            try:
                r_role = Role(r_role_str)
            except ValueError:
                continue
            r_country = int(r_country_str) if r_country_str and r_country_str.isdigit() else None
            r_admin1  = int(r_admin1_str)  if r_admin1_str  and r_admin1_str.isdigit()  else None
            existing = UserRegionRole.query.filter_by(
                user_id=user.id, role=r_role, country_id=r_country
            ).first()
            if not existing:
                db.session.add(UserRegionRole(
                    user_id=user.id, role=r_role,
                    country_id=r_country, admin1_id=r_admin1,
                    granted_by_id=current_user.id,
                ))

        db.session.commit()
        flash(f"User '{username}' registered successfully.", "success")
        return redirect(url_for("dashboard.users"))

    countries = Country.query.filter_by(is_active=True).order_by(Country.name).all()
    from models import AdminLevel1
    return render_template("register.html", roles=Role, countries=countries)


# ── Public Self-Registration ──────────────────────────────────────────────────

@auth.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.main"))

    countries = Country.query.filter_by(is_active=True).order_by(Country.name).all()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip() or None
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not full_name or not password:
            flash("Full name, username and password are required.", "danger")
            return render_template("auth.html", active_view="signup", countries=countries)

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("auth.html", active_view="signup", countries=countries)

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("auth.html", active_view="signup", countries=countries)

        if User.query.filter_by(username=username).first():
            flash("That username is already taken. Please choose another.", "danger")
            return render_template("auth.html", active_view="signup", countries=countries)

        if email and User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
            return render_template("auth.html", active_view="signup", countries=countries)

        country_id = request.form.get("country_id", type=int) or None
        admin1_id  = request.form.get("admin1_id",  type=int) or None
        admin2_id  = request.form.get("admin2_id",  type=int) or None
        admin3_id  = request.form.get("admin3_id",  type=int) or None

        district_str = None
        if admin2_id:
            a2 = AdminLevel2.query.get(admin2_id)
            district_str = a2.name if a2 else None

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            full_name=full_name,
            role=Role.REPORTER,
            email=email,
            contact=request.form.get("contact", "").strip() or None,
            district=district_str,
            country_id=country_id,
            admin1_id=admin1_id,
            admin2_id=admin2_id,
            admin3_id=admin3_id,
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f"Welcome, {full_name}! Your account has been created.", "success")
        return redirect(url_for("dashboard.main"))

    return render_template("auth.html", active_view="signup", countries=countries)


# ── Forgot Password ────────────────────────────────────────────────────────────

@auth.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.main"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user and user.is_active:
            token = generate_reset_token(user.email)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            send_reset_email(user.email, reset_url, user.full_name)
        # Always show same message — prevents email enumeration
        flash("If that email is registered, a reset link has been sent. Check your inbox.", "info")
        return redirect(url_for("auth.login"))
    return render_template("forgot_password.html")


# ── Reset Password ─────────────────────────────────────────────────────────────

@auth.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.main"))
    email = verify_reset_token(token)
    if not email:
        flash("This reset link is invalid or has expired (links are valid for 1 hour).", "danger")
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("reset_password.html", token=token)
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("reset_password.html", token=token)
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Account not found.", "danger")
            return redirect(url_for("auth.login"))
        user.password_hash = generate_password_hash(password)
        db.session.commit()
        flash("Password reset successfully. Please log in with your new password.", "success")
        return redirect(url_for("auth.login"))
    return render_template("reset_password.html", token=token)


# ── User Preferences ───────────────────────────────────────────────────────────

@auth.route("/account/preferences", methods=["GET", "POST"])
@login_required
def preferences():
    # Reporters (the role every self-service signup and SSO auto-created
    # account gets) don't get any regional-scoping benefit from their own
    # admin1/admin2 - they only ever see their own tickets regardless of
    # region - so letting them self-declare it here is a convenience, not a
    # privilege-escalation surface. Every other role's region is admin-
    # assigned (see Admin -> Users -> Manage Regions) and stays read-only.
    can_self_locate = current_user.role == Role.REPORTER

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        if full_name:
            current_user.full_name = full_name
        current_user.contact = request.form.get("contact", "").strip() or None
        current_user.timezone = request.form.get("timezone", "UTC")
        current_user.language = request.form.get("language", "en")
        session["lang"] = current_user.language

        if can_self_locate:
            admin1_id = request.form.get("admin1_id", type=int) or None
            admin2_id = request.form.get("admin2_id", type=int) or None
            admin3_id = request.form.get("admin3_id", type=int) or None
            current_user.admin1_id = admin1_id
            current_user.admin2_id = admin2_id
            current_user.admin3_id = admin3_id
            if admin2_id:
                a2 = AdminLevel2.query.get(admin2_id)
                current_user.district = a2.name if a2 else None
            else:
                current_user.district = None
            if not current_user.country_id:
                country = Country.query.filter_by(is_active=True).first()
                current_user.country_id = country.id if country else None

        db.session.commit()
        flash("Preferences saved.", "success")
        return redirect(url_for("auth.preferences"))
    import pytz
    timezones = sorted(pytz.common_timezones)
    languages = [
        ("en", "English"),
        ("fr", "Français"),
        ("ar", "العربية"),
        ("hi", "हिन्दी"),
        ("sw", "Kiswahili"),
        ("bn", "বাংলা"),
    ]
    country = Country.query.filter_by(is_active=True).first() if can_self_locate else None
    return render_template("account/preferences.html",
                           timezones=timezones, languages=languages,
                           can_self_locate=can_self_locate, country=country)


@auth.route("/account/request-deletion", methods=["POST"])
@login_required
def request_account_deletion():
    reason = request.form.get("reason", "").strip()
    user = current_user
    body = (
        f"Account deletion requested via Account Preferences.\n\n"
        f"Name: {user.full_name}\n"
        f"Username: {user.username}\n"
        f"Email: {user.email or '—'}\n"
        f"Role: {user.role.value}\n"
        f"Reason given by user: {reason or '(none provided)'}\n"
    )
    sent = send_notification(
        "support@medtroniclabs.org",
        f"Account deletion request — {user.username}",
        body,
    )
    if sent:
        flash("Your account deletion request has been sent to support. They'll follow up with you by email.", "success")
    else:
        flash("Couldn't send the request right now — please email support@medtroniclabs.org directly.", "danger")
    return redirect(url_for("auth.preferences"))


# ── GDPR Data Export ───────────────────────────────────────────────────────────

@auth.route("/account/gdpr-export")
@login_required
def gdpr_export():
    import json
    from flask import current_app
    from models import Ticket, TicketComment, TicketHistory

    profile = {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "role": current_user.role.value,
        "contact": current_user.contact,
        "created_at": str(current_user.created_at),
    }
    tickets = [
        {
            "sl_no": t.sl_no, "status": t.current_status, "priority": t.priority,
            "issue_type": t.issue_type, "problem_details": t.problem_details,
            "created_at": str(t.created_at), "solved_date": str(t.solved_date),
        }
        for t in Ticket.query.filter_by(reporter_id=current_user.id).all()
    ]
    comments = [
        {"ticket_sl": c.ticket.sl_no, "body": c.body, "created_at": str(c.created_at)}
        for c in TicketComment.query.filter_by(author_id=current_user.id).all()
    ]
    export = {"profile": profile, "tickets": tickets, "comments": comments}
    import io
    buf = io.BytesIO(json.dumps(export, indent=2, default=str).encode())
    buf.seek(0)
    from flask import send_file
    return send_file(buf, as_attachment=True,
                     download_name=f"my_data_{current_user.username}.json",
                     mimetype="application/json")


# ── GDPR Right to be Forgotten (admin action) ────────────────────────────────

@auth.route("/admin/users/<int:user_id>/anonymize", methods=["POST"])
@login_required
def anonymize_user(user_id):
    from models import db, Ticket, TicketComment
    if not current_user.is_admin():
        from flask import flash, redirect, url_for
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard.main"))
    from models import User
    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        flash("Cannot anonymize your own account.", "warning")
        from flask import redirect, url_for
        return redirect(url_for("dashboard.users"))
    import secrets
    anon_id = secrets.token_hex(4)
    # Anonymize personal data
    target.username = f"deleted_{anon_id}"
    target.full_name = "Anonymized User"
    target.email = f"deleted_{anon_id}@anon.invalid"
    target.contact = None
    target.is_active = False
    # Anonymize their tickets
    Ticket.query.filter_by(reporter_id=target.id).update({
        "issue_reporter_name": "Anonymized",
        "issue_reporter_contact": None,
        "form_submit_email": None,
    })
    # Anonymize their comments
    TicketComment.query.filter_by(author_id=target.id).update({
        "body": "[Content removed — GDPR request]"
    })
    db.session.commit()
    from utils import log_history
    flash(f"User anonymized (GDPR right to be forgotten).", "success")
    from flask import redirect, url_for
    return redirect(url_for("dashboard.users"))
