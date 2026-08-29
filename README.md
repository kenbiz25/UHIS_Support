# Bangladesh UHIS — Medtronic LABS Support Ticketing System

A multi-channel, intelligent support platform built for Medtronic LABS' Bangladesh field operations (built in partnership with BRAC and the Ministry of Health, part of the SPICE digital health platform). Supports ticket intake via web form, WhatsApp conversational bot, embeddable in-app widget, email, and REST API — with proactive nudges, CSAT tracking, and an escalation flow tailored to Bangladesh's administrative structure.

---

## Table of Contents

1. [Features](#features)
2. [Tech Stack](#tech-stack)
3. [Getting Started](#getting-started)
4. [Environment Variables](#environment-variables)
5. [Project Structure](#project-structure)
6. [Default Credentials](#default-credentials)
7. [Roles & Permissions](#roles--permissions)
8. [SLA Policies](#sla-policies)
9. [Escalation Matrix](#escalation-matrix)
10. [Channels & Integrations](#channels--integrations)
11. [Intelligent Support Features](#intelligent-support-features)
12. [Feature Reference](#feature-reference)

---

## Features

### Ticket Management

- **Multi-channel intake** — web form, WhatsApp (conversational bot), embeddable widget, email, and REST API
- **Three ticket views** — List, Split (LinkedIn-style preview), and Kanban (Jira-style columns)
- **SLA tracking** — seven priority tiers (P1–P5, OTP, OUTAGE) with automatic breach detection and countdown timers
- **Status workflow** — Open → In Progress → Pending → Resolved → Closed → Reopened
- **Merge, duplicate, and link tickets** — parent/child hierarchy, related/blocks/duplicates link types
- **Custom fields** — admin-configurable text, dropdown, checkbox, date, number fields per ticket
- **Auto-assignment** — new tickets route to the least-loaded active **L1 agent** (first contact); one-click **Escalate** auto-routes to the least-loaded agent at the next tier (L2–L4), falling back to Admins if none are available
- **Fixed sidebar** — always visible, toggleable, never moves with scroll

### Intelligent Support Layer

- **WhatsApp conversational bot** — 5-step guided ticket creation via any WhatsApp number (Meta Cloud API or Twilio); agents reply from the dashboard; status updates pushed back to the user
- **Embeddable in-app widget** — single `<script>` tag drops a floating support widget into SPICE, Tiberbu, or Afyangu, with three touchpoints: self-service Knowledge Base search + ticket form, a "Chat on WhatsApp" quick link, and an AI Assistant that answers from the KB then collects contact info and files a ticket (falls back to a guided, non-AI intake if no OpenAI key is configured)
- **SSO login** — optional "Continue with Google" / "Continue with Microsoft" on the login page, signing in to existing accounts matched by email
- **Proactive nudges** — automatic aging alerts for P1/P2 tickets with no agent response after 2 hours; CSAT surveys pushed to WhatsApp 1 hour after ticket resolution
- **Broadcast messaging** — admins send proactive WhatsApp messages to Agents filtered by country and role
- **CSAT tracking** — 1–5 star ratings via WhatsApp reply, widget, or email link; agent leaderboard, 30-day trend chart, response rate analytics

### Communication

- **In-app notifications** — real-time bell with unread count; polling every 30 seconds
- **Telegram bot** — conversational ticket creation via webhook
- **Slack / Microsoft Teams** — outbound webhook notifications for critical tickets and SLA breaches
- **Real-time translation** — translate ticket descriptions via Google Translate or LibreTranslate
- **Call logging** — log inbound/outbound calls against tickets with duration, outcome, and notes

### Automation & Workflows

- **Visual rule builder** — if/then automation rules at `/admin/automation` with 7 condition fields and 8 action types
- **Trigger events** — ticket created, status changed, priority changed, reply received
- **Actions** — set priority/status, assign agent, add tag, escalate, add internal note, notify staff, send email to reporter
- **Background scheduler** — APScheduler runs aging checks every 30 min and CSAT dispatch every 60 min automatically. A file lock (`.scheduler.lock`) ensures only one worker process runs it, even with multiple workers — otherwise every worker would fire its own aging/CSAT jobs.

### Knowledge Base

- **Public help center** at `/kb/` — searchable homepage, category pages, article detail
- **Widget integration** — KB articles surface inside the embeddable widget before the ticket form
- **Article feedback** — "Was this helpful?" thumbs up/down (IP-deduplicated)
- **Admin management** — HTML article editor, category CRUD at `/admin/kb`

### Dashboards & Analytics

- **Role-aware dashboards** — Super Admin, Admin (country/region queue), Agent (own tickets + pickup queue, tiered L1–L4), Reporter, and Viewer (reports-only) views
- **Analytics dashboard** at `/admin/analytics` — date range (7/30/90/180 days/custom), volume chart, SLA compliance, channel/category breakdowns, agent performance table
- **Reports** at `/admin/reports` — status, priority, escalation pyramid (L1–L4), district, and platform charts
- **CSAT dashboard** at `/admin/csat` — average score, score distribution, 30-day trend, agent leaderboard, recent feedback
- **Export** — CSV and Excel with styled headers and colour-coding
- **WhatsApp Inbox** at `/admin/whatsapp` — all WhatsApp conversations, state per session, agent reply from dashboard

### UI/UX

- **Dark / Light mode** — Bootstrap 5.3 native, toggle in navbar, persisted in `localStorage` with no flash on load
- **Keyboard shortcuts** — `N` New Ticket, `I` Inbox, `D` Dashboard, `R` Reports, `/` focus search, `Alt+T` toggle theme, `?` help
- **Drag-and-drop attachments** — any file input wrapped in a `.drop-zone` div
- **Mobile-first** — responsive across all screen sizes; widget goes full-screen on mobile
- **Custom branding** — app name, logo, tagline, primary colour, nav background at `/admin/branding`

### Operations

- **Multi-level RBAC** — five roles with regional scoping (country / admin-level-1) via `UserRegionRole`
- **Collision detection** — 5-minute edit lock with warning banner
- **Time tracking** — log minutes worked per ticket with per-agent breakdowns
- **Saved views** — persist filter combinations as named views (private or shared)
- **Tags, canned responses, bulk actions, audit trail**
- **Ticket attachments** — viewable and downloadable by all levels with access

### Security & Compliance

- **Login audit log** — every login success/failure recorded with IP and user-agent at `/admin/audit-log`
- **Ticket change history** — full audit trail of all field changes
- **GDPR data export** — users download their data at `/account/gdpr-export`
- **Right to be forgotten** — admin anonymization of any user account
- **User preferences** — per-user timezone and display language at `/account/preferences`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask 3.0 |
| ORM | Flask-SQLAlchemy + SQLite (dev) / PostgreSQL (prod) |
| Auth | Flask-Login + Werkzeug password hashing; optional Google/Microsoft SSO via Authlib |
| Rate limiting | Flask-Limiter 3.x (per-IP; login + password-reset endpoints) |
| Frontend | Jinja2 + Bootstrap 5.3 + Chart.js 4.4 + Font Awesome 6.4 |
| File uploads | Werkzeug + Pillow |
| Email | SMTP (smtplib) |
| Excel export | openpyxl |
| Timezones | pytz |
| Background jobs | APScheduler 3.10 (in-process, no Redis required) |
| WhatsApp | Meta Cloud API (Graph v18) or Twilio |
| Widget | Vanilla JS, Shadow DOM, zero dependencies (AI Assistant touchpoint calls OpenAI server-side when configured) |

> **Production path**: Flask → FastAPI; SQLite → PostgreSQL; APScheduler → Celery + Redis for distributed workers. Rate limiting already supports Redis today (`REDIS_URL`) for multi-worker deployments — no code changes needed, just set the variable. Also set `SECRET_KEY`, `API_KEY`, and leave `FLASK_DEBUG` unset/`false`, and run behind a real WSGI server (gunicorn/waitress), not `python app.py`.

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- pip

### 1. Clone and create a virtual environment

```bash
git clone <repo-url>
cd User_Support

python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in the required values. At minimum set `SECRET_KEY`. Everything else has safe defaults for local development.

### 4. Run the application

```bash
# Development (auto-reload on file changes)
flask run --debug

# or
python -m flask run --debug
```

The app starts at **http://localhost:5000**.

On first run it automatically seeds:

- A default Super Admin account — username `superadmin`, password printed to stdout on first boot (set `SUPERADMIN_PASSWORD` in `.env` to control it; **change after first login**)
- Built-in SLA policies for all seven priority tiers (P1–P5, OTP, OUTAGE)
- Bangladesh's administrative location data (8 divisions)
- Issue taxonomy (6 categories, 23+ subcategories)

Bangladesh's own escalation matrix is entered by hand through the admin UI at `/admin/escalation-matrices`, not seeded — it isn't code-managed.

### 5. (Optional) Seed demo data

```bash
python seed_demo.py
```

Seeds 80 tickets, 200 comments, tags, canned responses, automation rules, and 12 KB articles for testing all features.

---

## Environment Variables

Copy `.env.example` to `.env`. Variables marked **required** must be set for that feature to work; others have working defaults.

### Core

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `SECRET_KEY` | *(insecure default)* | **Required** — Flask session signing key. Set to a long random string in production. |
| `DATABASE_URL` | `sqlite:///database.db` | SQLAlchemy connection URI. Use `postgresql://user:pass@host/db` for PostgreSQL. |
| `SUPERADMIN_PASSWORD` | *(random, printed on boot)* | Initial password for the `superadmin` account. Set before first run; otherwise a secure random password is generated and printed once to stdout. |
| `API_KEY` | *(insecure default)* | **Required** — used by internal automation endpoints. Set to a long random string in production. |
| `FLASK_DEBUG` | `false` | Set to `true` only for local development. Leave unset/`false` in production — debug mode exposes an interactive debugger on error pages. |
| `REDIS_URL` | *(blank — in-memory)* | Shared storage for the rate limiter. Only needed once you run more than one worker process; with it blank, each worker keeps its own counters. |

### Email / SMTP

| Variable | Default | Description |
|----------|---------|-------------|
| `MAIL_SERVER` | `smtp.gmail.com` | Outbound SMTP server |
| `MAIL_PORT` | `587` | SMTP port (TLS) |
| `MAIL_USERNAME` | — | SMTP username / sender address |
| `MAIL_PASSWORD` | — | SMTP password or app password |
| `ADMIN_EMAIL` | `admin@example.com` | Address that receives critical-ticket alerts |

### WhatsApp — Meta Cloud API or Twilio

One webhook family (`routes/webhooks.py`) supports both providers; `WA_PROVIDER` picks which credentials `_wa_send()` uses for outbound messages. Both providers share the same bot conversation, admin WhatsApp Inbox, and CSAT flow.

| Variable | Default | Description |
|----------|---------|-------------|
| `WA_PROVIDER` | `meta` | `meta` or `twilio` — which provider outbound sends use |
| `WHATSAPP_TOKEN` | — | Meta Cloud API permanent / system user token |
| `WHATSAPP_PHONE_ID` | — | Phone Number ID from Meta Business dashboard |
| `WHATSAPP_VERIFY_TOKEN` | — | **Required for Meta** — verification token you enter when registering the webhook on Meta. Set to any secret string. |
| `WHATSAPP_API_VERSION` | `v18.0` | Meta Graph API version used for outbound sends |
| `TWILIO_ACCOUNT_SID` | — | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | — | Twilio Auth Token |
| `TWILIO_WA_FROM` | `whatsapp:+14155238886` | Twilio WhatsApp sender number |

Register your webhook URL: Meta → `https://your-domain.com/webhooks/whatsapp`, Twilio → `https://your-domain.com/webhooks/whatsapp/twilio` ("When a Message Comes In" in the Twilio Console).

### SSO — Google / Microsoft (Outlook)

Optional "Continue with Google" / "Continue with Microsoft" buttons on the login page. Leave blank to keep them showing a friendly "not configured" message — no code changes needed either way. Signs in to an **existing** account matched by email; it never creates new accounts or roles.

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | — | From Google Cloud Console → APIs & Services → Credentials. Redirect URI: `https://your-domain.com/login/oauth/google/callback` |
| `MICROSOFT_CLIENT_ID` / `MICROSOFT_CLIENT_SECRET` | — | From Azure Portal → Entra ID → App registrations. Redirect URI: `https://your-domain.com/login/oauth/microsoft/callback` |
| `MICROSOFT_TENANT_ID` | `common` | Restrict to a specific Azure tenant if needed |

### Embeddable Widget

| Variable | Default | Description |
|----------|---------|-------------|
| `WIDGET_ALLOWED_ORIGINS` | `*` | CORS allowed origins for the widget API. Set to your app domains in production (e.g. `https://spice.medtroniclabs.org`). |
| `SUPPORT_WHATSAPP_NUMBER` | — | wa.me-format number (country code + digits, no `+`) for the widget's "Chat on WhatsApp" quick action |
| `OPENAI_API_KEY` | — | Powers the widget's "Ask AI Assistant" touchpoint (answers from the Knowledge Base, then collects contact info and files a ticket). Left blank, the touchpoint still works via a guided, non-AI intake flow. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model used for AI Assistant replies |

### Telegram Bot

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_WEBHOOK_SECRET` | Secret for validating Telegram webhook calls |

### Slack / Teams

| Variable | Description |
|----------|-------------|
| `SLACK_WEBHOOK_URL` | Incoming Webhook URL |
| `SLACK_SIGNING_SECRET` | For verifying Slash Command requests |
| `TEAMS_WEBHOOK_URL` | Microsoft Teams Incoming Webhook connector URL |

### Email Inbound (IMAP polling)

| Variable | Default | Description |
|----------|---------|-------------|
| `IMAP_HOST` | `imap.gmail.com` | IMAP server |
| `IMAP_PORT` | `993` | IMAP SSL port |
| `IMAP_USER` | — | IMAP login address |
| `IMAP_PASSWORD` | — | IMAP password or app password |
| `IMAP_MAILBOX` | `INBOX` | Mailbox folder to poll |

### Translation

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSLATE_API_KEY` | — | Google Cloud Translation API key |
| `TRANSLATE_PROVIDER` | `google` | `google` or `libretranslate` |

---

## Project Structure

```
User_Support/
├── app.py                    # Application factory, DB migrations, seeding, APScheduler
├── config.py                 # All configuration loaded from environment
├── models.py                 # SQLAlchemy models (26 models)
├── requirements.txt
├── .env.example
│
├── routes/
│   ├── auth.py               # Login, logout, register, preferences, GDPR export
│   ├── tickets.py            # Ticket CRUD, comments, SLA, CSV/Excel export, REST API
│   ├── dashboard.py          # Role-aware dashboards, analytics, reports, regional filter
│   ├── admin_tools.py        # Tags, canned responses, SLA, branding, escalation matrices
│   ├── webhooks.py           # WhatsApp Cloud API webhook + agent reply + inbox view
│   ├── widget_api.py         # CORS-enabled API for the embeddable support widget
│   ├── nudges.py             # Broadcasts, CSAT dashboard, nudge log, aging check
│   ├── automation.py         # Automation rules CRUD
│   ├── kb.py                 # Knowledge base (public + admin)
│   ├── notifications.py      # In-app notification inbox
│   └── integrations.py       # Email and Telegram intake webhooks
│
├── pages/
│   ├── base.html             # Shared layout: dark mode, shortcuts, fixed sidebar, widget
│   ├── portal/               # Reporter and Agent/Admin dashboards (list/split/kanban views)
│   ├── admin/
│   │   ├── analytics.html            # Full-filter analytics dashboard
│   │   ├── reports.html              # Reports + escalation pyramid
│   │   ├── sla.html                  # HMIS ITSM escalation matrix (P1–OUTAGE)
│   │   ├── whatsapp_inbox.html       # WhatsApp conversation view
│   │   ├── broadcasts.html           # Send / history of broadcast messages
│   │   ├── nudge_log.html            # Nudge delivery log
│   │   ├── csat_dashboard.html       # CSAT ratings, trend, agent leaderboard
│   │   ├── escalation_matrices.html  # Country escalation matrix list
│   │   ├── escalation_matrix_detail.html  # Bangladesh's escalation matrix (multi-stream)
│   │   └── ...                       # Other admin pages
│   ├── kb/                   # Public knowledge base
│   └── account/              # User preferences
│
├── static/
│   ├── widget/
│   │   └── support-widget.js   # Self-contained embeddable widget (shadow DOM)
│   └── screenshots/            # Uploaded file attachments
│
├── seed_demo.py              # Demo tickets, comments, KB articles, automation rules
└── run_seed.py               # Seeds/updates Bangladesh's escalation matrix
```

### Database Models

| Model | Purpose |
|-------|---------|
| `User` | Agents (tiered `agent_level` L1–L4), admins, reporters, viewers — with timezone/language preferences |
| `UserRegionRole` | Multi-region, multi-role assignments (country / admin-level-1 scoping) |
| `Ticket` | Core ticket with SLA, channel, widget context, WhatsApp phone |
| `TicketComment` | Public and internal notes (WhatsApp messages prefixed `[WhatsApp]`) |
| `TicketHistory` | Immutable change audit trail |
| `TicketAttachment` | File uploads linked to tickets or comments |
| `TicketWatcher` | Users subscribed to ticket updates |
| `TicketLink` | Related / blocks / duplicates relationships |
| `Tag` / `ticket_tags` | Tagging system |
| `CannedResponse` | Pre-written reply templates |
| `SLAPolicy` | Per-priority response/resolution targets (P1–P5, OTP, OUTAGE) with L1–L4 hours |
| `CustomField` / `TicketFieldValue` | Admin-defined extra fields |
| `SavedView` | Named filter presets (private or shared) |
| `CSATRating` | Customer satisfaction scores with secure token for email/widget submission |
| `NudgeLog` | Record of every nudge sent (CSAT surveys, aging alerts, broadcasts) |
| `BroadcastMessage` | Outbound WhatsApp broadcasts with targeting metadata |
| `AutomationRule` | If/then workflow automation |
| `KBCategory` / `KBArticle` / `KBArticleFeedback` | Knowledge base |
| `BrandingSettings` | App name, logo, colours (singleton) |
| `LoginAuditLog` | Authentication event log (IP + user-agent) |
| `TimeEntry` | Time tracking per ticket |
| `CallLog` | Call logging against tickets |
| `Notification` | In-app notification inbox |
| `WhatsAppSession` | Conversation state machine per phone number |
| `TelegramSession` | Conversation state for Telegram bot |
| `CountryEscalationMatrix` | Per-country support flow (streams + shared levels JSON) |
| `Country` / `AdminLevel1–3` | 8-country location hierarchy with business hours |

---

## Default Credentials

| Username | Password | Role |
| -------- | -------- | ---- |
| `superadmin` | Printed to stdout on first boot | Super Admin |

> Set `SUPERADMIN_PASSWORD` in `.env` before the first run to choose the password, or read the generated one from the startup log.  
> **Change it immediately after first login** — go to your username dropdown → **Preferences**, or navigate to `/account/preferences`.

---

## Roles & Permissions

| Role | Submit Tickets | Update / Assign | Reports / Analytics | User Management | System Config |
|------|:-:|:-:|:-:|:-:|:-:|
| Super Admin | Yes | Yes | Yes | Yes | Yes |
| Admin | Yes | Yes | Yes | Yes (limited) | No |
| Agent | Yes | Yes | Yes (own region) | No | No |
| Reporter | Yes (own only) | No | No | No | No |
| Viewer | No | No | Yes (read-only) | No | No |

### Regional Scoping

Admins and Agents see only tickets from countries/regions assigned to them via **Admin → Users → Manage Regions**. Super Admins bypass all regional filters. Users with no region configured retain global access as a safe fallback.

### Agent Tiers (L1–L4)

Agents carry a tier (`agent_level`, 1–4), set at registration or from **Admin → Users**:

- **L1** handles first contact — every new ticket auto-assigns to the least-loaded active L1 agent.
- A ticket's required tier is derived from its escalation level (`escalation_level + 1`, capped at L4) and shown as a badge on the ticket detail page and dashboard queue.
- The **Escalate** button on a ticket bumps it to the next tier and auto-routes it to the least-loaded active agent at that tier (falling back to any active agent, then an Admin, if none exist at that tier).
- Manual reassignment only offers agents at the ticket's current tier or higher, plus Admins/Super Admins — a ticket can't be quietly handed down a tier.
- Agents land on a **My Tickets** dashboard: their own assigned tickets plus an "in my queue" count of unassigned tickets at their tier. Admins/Super Admins still see the full country/region ticket queue.

---

## SLA Policies

Based on the HMIS ITSM Escalation Matrix. Edit at **Admin → SLA Policies** (`/admin/sla`). Only Super Admins can edit.

| Code | Priority | First Response | L1 Resolution | Auto-Escalate | 24/7 |
|------|----------|:-:|:-:|:-:|:-:|
| P1 | Critical | 15 min | 1 hour | Yes → L3 | Yes |
| P2 | High | 1 hour | 4 hours | Yes → L2 | Yes |
| P3 | Medium | 4 hours | 1 business day | If L2 breaches | No |
| P4 | Low | 1 business day | 3 business days | No | No |
| P5 | Enhancement | 2 business days | Roadmap | No | No |
| OTP | OTP Failure | 15 min | L3 direct (2h) | Yes → L3 | Yes |
| OUTAGE | Full Outage | ~5 min | L4 direct (2h) | Yes → L4 | Yes |

Business hours are configured **per country** (timezone, work start/end, working days) for accurate SLA calculation.

---

## Escalation Matrix

View at **Admin → Escalation Matrices** (`/admin/escalation-matrices`).

| Country | Streams | Description |
|---------|:-------:|-------------|
| Bangladesh | 2 | SPICE field support (Shashtya Kormi/CHCP) + Internal Technical Escalation (L1–L4) |

---

## Channels & Integrations

### WhatsApp (Conversational Bot)

**Setup (Meta Cloud API — default):**
1. Create a Meta Business account and a WhatsApp Business app at [developers.facebook.com](https://developers.facebook.com)
2. Add your phone number and get the Phone Number ID
3. Generate a system user token (permanent access token)
4. Set in `.env`:
   ```
   WHATSAPP_TOKEN=your_permanent_token
   WHATSAPP_PHONE_ID=your_phone_number_id
   WHATSAPP_VERIFY_TOKEN=your_custom_verify_token
   ```
5. Register the webhook URL on Meta: `https://your-domain.com/webhooks/whatsapp`
   - Verify token: the value of `WHATSAPP_VERIFY_TOKEN`
   - Subscribe to: `messages`

**Setup (Twilio — alternative):** set `WA_PROVIDER=twilio`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WA_FROM` in `.env`, then set your Twilio WhatsApp sandbox/sender's "When a Message Comes In" webhook to `https://your-domain.com/webhooks/whatsapp/twilio`. Same bot flow, admin inbox, and CSAT either way.

**User conversation flow:**

```
User: Hi
Bot:  Hello! Welcome to Medtronic LABS Support 🏥
      1️⃣ SPICE  2️⃣ Tiberbu  3️⃣ Afyangu  4️⃣ Other

User: 1
Bot:  Got it — SPICE. Describe your issue...

User: Cannot log in on the mobile app
Bot:  Summary: App=SPICE, Issue=Cannot log in...
      Reply YES to submit or NO to cancel.

User: YES
Bot:  ✅ Ticket TKT-20260609-0042 created. Reply STATUS to check.
```

Agents view all conversations at **Channels & Engagement → WhatsApp Inbox** and reply from the dashboard. When a ticket is resolved, a CSAT survey is automatically sent back to the user's WhatsApp.

### Embeddable In-App Widget

Drop one line into SPICE, Tiberbu, or any web app:

```html
<script src="https://your-support-domain.com/static/widget/support-widget.js"
        data-base-url="https://your-support-domain.com"
        data-app="SPICE"
        data-primary-color="#2514BE"
        data-whatsapp="254705091683">
</script>
```

The widget:
1. Shows a floating **?** button (bottom-right)
2. On click, opens a panel with KB article search, plus two quick-action touchpoints: **Chat on WhatsApp** (opens `wa.me/<data-whatsapp>`, hidden if that attribute is empty) and **Ask AI Assistant**
3. Search fallback: if no KB articles resolve the issue, presents a pre-filled ticket form (app name and current page URL captured automatically)
4. AI Assistant: answers from the Knowledge Base; when it can't help (or the user asks for a human), it collects name + contact, summarizes the conversation into the ticket description, and asks for a quick CSAT rating right after filing. Without `OPENAI_API_KEY` configured, the same flow runs as a guided, non-AI intake instead of dead-ending.
5. On ticket creation, switches to a status tracker with star rating

No dependencies. Uses Shadow DOM for full CSS isolation from the host app. Full-screen on mobile.

**Widget API endpoints** (CORS-enabled, no auth required):

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/widget/config` | Branding, categories, countries |
| `GET` | `/widget/search?q=` | Knowledge base article search |
| `POST` | `/widget/ai-chat` | AI Assistant turn (or guided-intake fallback without an OpenAI key) |
| `POST` | `/widget/ticket` | Create a ticket |
| `GET` | `/widget/ticket/<sl_no>` | Track ticket status |
| `POST` | `/widget/csat/<token>` | Submit a star rating |

### Email Inbound

| Mode | Endpoint |
|------|---------|
| Webhook | `POST /integrations/email/inbound` |
| IMAP polling | `GET /integrations/email/poll?key=<IMAP_POLL_KEY>` |

Duplicate emails are detected by `Message-ID` header.

### Telegram Bot

1. Create a bot via [@BotFather](https://t.me/BotFather) and copy the token to `TELEGRAM_BOT_TOKEN`.
2. Register the webhook:
   ```
   POST https://api.telegram.org/bot<TOKEN>/setWebhook
        ?url=https://your-domain/integrations/telegram/webhook
   ```

### REST API

```bash
curl -X POST https://your-domain/tickets/api/create \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "issue_type": "Login / Access",
    "problem_details": "Cannot log into SPICE mobile app.",
    "priority": "High",
    "reporter_name": "Jane Doe",
    "email": "jane@example.com"
  }'
```

Response: `{"status": "success", "ticket_id": 42, "sl_no": "TKT-20260609-0042"}`

---

## Intelligent Support Features

### Proactive Nudges (Automatic)

Two background jobs run continuously without any configuration:

| Job | Frequency | What it does |
|-----|-----------|-------------|
| Aging Alert | Every 30 min | Sends an in-app notification to the assigned agent for any P1/P2/Urgent ticket with no first response after 2 hours |
| CSAT Dispatch | Every 60 min | Sends a WhatsApp CSAT survey to any user whose ticket was resolved via WhatsApp >1 hour ago and has not yet received a survey |

### Broadcasts

Admins can send proactive WhatsApp messages to field staff at **Channels & Engagement → Broadcasts**:
- Filter recipients by country (multi-select or all)
- Filter by role (Agent, Reporter, Admin, or all)
- Preview the formatted WhatsApp message before sending
- Full delivery history with recipient count and status

### CSAT Tracking

Ratings are collected through three channels:
- **WhatsApp** — bot sends "rate 1–5" message after resolution; reply captured in state machine
- **Widget** — inline star rating shown after ticket status = Resolved
- **Email** — link to rating page included in resolution email

View the full CSAT dashboard at **Channels & Engagement → CSAT Ratings**:
- Average score with colour indicator (green ≥4, yellow 3–4, red <3)
- Score distribution horizontal bar chart
- 30-day trend line chart
- Agent performance leaderboard
- Recent ratings with feedback text

### Nudge Log

Every nudge sent — CSAT surveys, aging alerts, and broadcasts — is recorded at `/admin/nudge-log` with delivery status and any response received.

---

## Feature Reference

### Automation Rules (`/admin/automation`)

**Trigger events:** `ticket_created`, `status_changed`, `priority_changed`, `reply_received`

**Condition fields:** `priority`, `current_status`, `channel`, `category_id`, `issue_type`, `problem_details`, `escalation_level`

**Action types:**

| Action | Params |
|--------|--------|
| `set_priority` | `{"priority": "Critical"}` |
| `set_status` | `{"status": "In Progress"}` |
| `assign_to` | `{"user_id": 5}` |
| `add_tag` | `{"tag_id": 3}` |
| `escalate` | `{"level": 2}` |
| `add_internal_note` | `{"body": "Auto-escalated by rule"}` |
| `notify_staff` | `{"message": "Urgent ticket needs attention"}` |
| `send_email_reporter` | `{"subject": "Update on {sl_no}", "body": "We are investigating."}` |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `N` | New Ticket |
| `I` | Inbox |
| `D` | Dashboard |
| `R` | Reports |
| `/` | Focus search |
| `Alt+T` | Toggle dark/light mode |
| `?` | Show shortcuts help |

### Dark Mode

Click the moon icon in the top navbar or press `Alt+T`. Saved in `localStorage`, applied on page load with no flash.

### Excel Export

Download a formatted `.xlsx` file from the sidebar or `/tickets/export-excel`. Applies the same filters as the current view. Column headers are colour-coded by status.

### GDPR Compliance

- **Export your data** — `/account/preferences` → "Export My Data (JSON)"
- **Right to be forgotten** — Super Admins anonymize any account from `/admin/users`

---

## License

Internal use — Medtronic Labs.
