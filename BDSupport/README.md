
# BDSupport — SPICE Bangladesh WhatsApp Bot

AI-powered WhatsApp support bot for **SPICE Bangladesh** field users, built with **FastAPI**, the **WhatsApp Cloud API**, and **OpenAI**. Most real users here contact support by voice note and in Bangla, so the bot is Bengali-first rather than Bengali-as-an-afterthought. It runs as a separate service from the main ticketing tool ([`../README.md`](../README.md)) and reports tickets into it over a small internal API.

Uses Retrieval-Augmented Generation (RAG) over a FAISS-indexed knowledge base for context-aware answers, and sanitizes responses to avoid leaking internal KB details.

---

## ✅ Features

- **RAG-based answers** — retrieves from a FAISS knowledge base, composes a reply via LLM, sanitized to avoid leaking KB paths/internals
- **Bengali-first language handling**
  - Detects native Bangla script and romanized "Banglish" (e.g. "app ta kaj korche na"), each with its own confidence scoring
  - Voice notes are transcribed with a prompt steering the model to write Bangla speech in Bangla script
  - Banglish queries are normalized to English before KB retrieval (the KB itself is English), without altering what the user actually said for replies/logging
  - An explicit first-message language-selection step, skipped automatically when Bangla is already evident
- **Voice and image intake** — WhatsApp voice notes are transcribed (OpenAI Audio Transcriptions); images are analyzed by a vision model, with any caption text preserved and combined with the image description rather than discarded
- **Every conversation becomes a ticket** — auto-summarized (in the conversation's own language) and logged in the main ticketing tool when a chat closes, not only when the user explicitly asks; a repeat contact about the same unresolved issue is added to the existing open ticket instead of creating a duplicate
- **First-touch menu** — a short numbered menu (Report a Problem / Get Help / System Status / Suggest Improvement / Training) before falling through to free-form RAG
- **Human handoff** — explicit ("connect me to support") and mild ("talk to a human") hotwords, gated to avoid over-triggering on a single ambiguous phrase
- Configurable guardrails for security and compliance

---

## ✅ Project Structure
```
app.py               # FastAPI entry point - webhook, media download, transcription/vision dispatch
config/              # Settings (env-driven) and rate limit configs
core/
  i18n.py            # Bilingual (en/bn) copy for every hardcoded bot message
  contacts/          # Per-phone contact + language-preference state (JSON sidecar files)
  tickets/           # Ticket creation/state, main-app API client, per-phone open-ticket tracking
  knowledge/         # FAISS store + KB indexing
  memory/            # Conversation memory (JSONL) and summarization
  menu/              # First-touch menu routing
  whatsapp/          # WhatsApp Cloud API send/receive service
adapters/llm/        # OpenAI client - chat, transcription, vision, language detection
rag/                 # composer.py (retrieval + LLM composition), flow.py (BotFlow orchestration)
jobs/                # Background tasks (e.g., reindex KB)
docker/              # docker-compose.yml + Dockerfile used for the actual deployment (see below)
tests/               # pytest unit tests
prompts/             # System prompt templates
requirements.txt     # Dependencies
```

---

## ✅ Setup Instructions

### 1. Clone the Repo
```bash
git clone https://github.com/kenbiz25/BDSupport
cd BDSupport
```

### 2. Create Virtual Environment
```bash
python -m venv venv
# Activate:
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root:
```
WHATSAPP_PHONE_ID=<your-phone-id>
META_WHATSAPP_TOKEN=<your-meta-token>
META_VERIFY_TOKEN=SPICE1234
OPENAI_API_KEY=<your-openai-key>
KB_DIR=KB
TOP_K=3
ANSWER_CONFIDENCE_THRESHOLD=0.45

# Ticket integration with the main ticketing tool (../README.md)
MAIN_APP_BASE_URL=https://your-ticketing-domain.com
BD_SUPPORT_API_KEY=<shared secret - must match the main app's config>
ENABLE_TICKETING=true

# Bengali handling
BANGLA_TRANSLATION=true
BANGLA_NORMALIZE_AGGRESSIVE=true

# Voice transcription
ENABLE_STT=true
TRANSCRIBE_MODEL=gpt-4o-transcribe

# First-touch numbered menu before free-form RAG
ENABLE_FIRST_TOUCH_MENU=true
```
See `config/settings.py` for the full list of settings and their defaults — most have safe fallbacks and don't need to be set for local development.

---

## ✅ Running the Bot

### Local development

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### Expose via Ngrok (for local webhook testing)

```bash
ngrok http 8000
```

Copy the **Forwarding URL** and set it as your webhook in **Meta Developer Dashboard**.

### Production deployment (Docker Compose + systemd)

The actual production deployment runs the FastAPI app inside Docker via `docker/docker-compose.yml`, supervised by a systemd unit rather than a bare `uvicorn` process:

```bash
cd docker
COMPOSE_PROJECT_NAME=bdsupport docker compose build api
docker compose up -d api
```

The systemd unit (`bdsupport.service`) sets `COMPOSE_PROJECT_NAME=bdsupport` and runs from the `docker/` directory — **always build/restart using that same project name and working directory**, otherwise Docker's build cache produces a differently-tagged image that the running service never picks up (this has bitten a real deploy before: `docker compose build` from the wrong directory silently created an unused `docker-api:latest` image while the service kept running the stale `bdsupport-api:latest`).

After a code change: rebuild, then `sudo systemctl restart bdsupport.service`. Verify the new code actually landed inside the running container before considering the deploy done, e.g.:

```bash
docker compose -p bdsupport exec api python -c "from core.i18n import t; print(t('lang_prompt','en'))"
```

---

## ✅ WhatsApp Cloud API Integration

### Sending Text Messages
Example in `apps/whatsapp_gateway/send.py`:
```python
def send_whatsapp_text(to: str, text: str):
    url = f"https://graph.facebook.com/v20.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    requests.post(url, headers=headers, json=payload)
```

### Sending Media (Images, PDFs)
```python
def send_whatsapp_media(to: str, media_url: str, media_type="image"):
    url = f"https://graph.facebook.com/v20.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": media_type,
        media_type: {"link": media_url}
    }
    requests.post(url, headers=headers, json=payload)
```

---

## ✅ Adding a New WhatsApp Number
1. Go to **Meta Business Manager → WhatsApp Accounts → Add Phone Number**.
2. Verify via SMS or voice call.
3. Update `.env` with the new `WHATSAPP_PHONE_ID`.

---

## ✅ Troubleshooting
- **Ngrok not recognized**: Ensure ngrok is installed and added to PATH.
- **Webhook not validating**: Check `META_VERIFY_TOKEN` matches your Meta settings.
- **401 Unauthorized**: Verify `META_WHATSAPP_TOKEN` is correct and not expired.
- **No response on WhatsApp**: Confirm webhook URL is active and reachable.

---

## ✅ Deployment Tips
- Use **Docker** for containerized deployment:
  ```bash
  docker-compose up --build
  ```
- Use **systemd** or **PM2** for process management in production.
- Rotate tokens regularly for security.

---

## ✅ License
Apache 2.0
