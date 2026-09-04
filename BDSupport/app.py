# ============================================================
# SPICE Support – Production App Entrypoint
# ============================================================

# --- Fix for Windows / uvicorn module import issues ---
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.resolve()))

# --- Standard imports ---
import os
import json
import shutil
import tempfile
import logging
import base64
import hmac
from datetime import datetime
from typing import Optional, Tuple

import httpx

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    UploadFile,
    File,
    Request,
    Body,
    BackgroundTasks,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

# --- Core services ---
from core.knowledge.store_faiss import FaissStore
from core.llm.llm_service import LLMService
from core.whatsapp.whatsapp_service import WhatsAppService
from rag.flow import BotFlow

# Optional legacy WhatsApp adapter
try:
    from whatsapp import send_whatsapp_text
    HAS_WHATSAPP_ADAPTER = True
except Exception:
    HAS_WHATSAPP_ADAPTER = False

# Settings
from config.settings import settings

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SPICE")

# --- Initialize FastAPI ---
app = FastAPI(title="SPICE Support", version="1.4.0")

# --- CORS ---
if getattr(settings, "ALLOWED_ORIGINS", None):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_headers=["*"],
        allow_methods=["*"],
    )

# ============================================================
# Shared Components
# ============================================================

def _get_embedding_dim():
    em = (settings.EMBED_MODEL or "").lower()
    if "text-embedding-3-large" in em:
        return 3072
    return 1536

EMBEDDING_DIM = _get_embedding_dim()

faiss_store = FaissStore(dim=EMBEDDING_DIM)

llm_service = LLMService(
    model=settings.LLM_MODEL,
    temperature=settings.LLM_TEMPERATURE,
)

whatsapp_service = WhatsAppService(
    phone_id=os.getenv("WHATSAPP_PHONE_ID", ""),
    token=os.getenv("META_WHATSAPP_TOKEN", ""),
)

bot = BotFlow(faiss_store, llm_service, whatsapp_service)
app.state.bot = bot

# ============================================================
# WhatsApp Media Helpers
# ============================================================

def _download_whatsapp_media(media_id: str) -> Tuple[bytes, str]:
    # Sync on purpose: called from the background task thread, not the event loop.
    token = os.getenv("META_WHATSAPP_TOKEN", "")
    api_ver = os.getenv("WHATSAPP_API_VERSION", "v22.0")
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(timeout=60) as client:
        meta = client.get(
            f"https://graph.facebook.com/{api_ver}/{media_id}",
            headers=headers,
        )
        meta.raise_for_status()
        mjson = meta.json()
        media_url = mjson.get("url")
        mime_type = mjson.get("mime_type") or "application/octet-stream"

        blob = client.get(media_url, headers=headers)
        blob.raise_for_status()
        return blob.content, mime_type

def _guess_ext_from_mime(mime: str, default: str) -> str:
    m = (mime or "").lower()
    if "audio/ogg" in m or "opus" in m:
        return ".ogg"
    if "audio/mpeg" in m or "mp3" in m:
        return ".mp3"
    if "audio/wav" in m:
        return ".wav"
    if "image/png" in m:
        return ".png"
    if "image/jpeg" in m or "jpg" in m:
        return ".jpg"
    if "image/webp" in m:
        return ".webp"
    return default

def _safe_send_text(to: str, text: str):
    try:
        if hasattr(whatsapp_service, "send_message"):
            whatsapp_service.send_message(to, message=text)
        elif HAS_WHATSAPP_ADAPTER:
            send_whatsapp_text(to, text)
    except Exception:
        logger.exception("Failed to send WhatsApp message")

# ============================================================
# Startup diagnostics
# ============================================================

@app.on_event("startup")
def startup_diag():
    logger.info(
        "WhatsApp ready | token=%s phone_id=%s",
        bool(os.getenv("META_WHATSAPP_TOKEN")),
        bool(os.getenv("WHATSAPP_PHONE_ID")),
    )
    logger.info(
        "Confidence threshold=%s",
        getattr(settings, "ANSWER_CONFIDENCE_THRESHOLD", "not-set"),
    )

# ============================================================
# Health
# ============================================================

@app.get("/health")
def health():
    return {"status": "ok"}

# ============================================================
# WhatsApp Webhook Verification (GET)
# ============================================================

@app.get("/whatsapp/webhook", tags=["WhatsApp Gateway"])
async def whatsapp_webhook_verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == settings.META_VERIFY_TOKEN:
        return Response(content=challenge or "", media_type="text/plain")

    return Response(status_code=403)

# ============================================================
# WhatsApp Webhook (POST)
# ============================================================

def _process_incoming_message(msg: dict, from_: str):
    """Runs off the request/response cycle (FastAPI executes sync background tasks in a
    thread pool), so one user's slow voice transcription or LLM call never blocks other
    users' webhook requests from being accepted.
    """
    try:
        msg_type = msg.get("type")

        # ---- TEXT / INTERACTIVE ----
        body = (
            (msg.get("text") or {}).get("body")
            or (msg.get("interactive") or {}).get("button_reply", {}).get("title")
            or (msg.get("interactive") or {}).get("list_reply", {}).get("title")
            or (msg.get("button") or {}).get("text")
        )

        # ---- AUDIO ----
        if not body and msg_type == "audio":
            media_id = (msg.get("audio") or {}).get("id")
            if media_id:
                audio_bytes, mime = _download_whatsapp_media(media_id)
                ext = _guess_ext_from_mime(mime, ".ogg")
                from adapters.llm.openai_client import whisper_transcribe
                body = whisper_transcribe(audio_bytes, filename=f"voice{ext}")

        # ---- IMAGE / SCREENSHOT ----
        if not body and msg_type == "image":
            media_id = (msg.get("image") or {}).get("id")
            if media_id:
                img_bytes, mime = _download_whatsapp_media(media_id)
                from adapters.llm.openai_client import analyze_image
                body = analyze_image(img_bytes, mime)

        if not from_ or not body:
            return

        # ✅ CRITICAL: Do NOT mutate user text
        handler_bot = getattr(app.state, "bot", None) or bot

        handler_bot.handle_message(
            user_id=from_,
            message=body,
            session_id=from_,  # ✅ stable session key
        )

    except Exception:
        logger.exception("Background WhatsApp message processing failed | from=%s", from_)


@app.post("/whatsapp/webhook", tags=["WhatsApp Gateway"])
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    from_: str = Query(None, alias="from"),
    payload: dict = Body(None),
):
    try:
        j = payload or await request.json()

        # ACK non-message payloads (delivery receipts, status updates)
        try:
            value = j["entry"][0]["changes"][0]["value"]
            if value.get("statuses") and not value.get("messages"):
                return JSONResponse(content={"status": "acknowledged"})
        except Exception:
            pass

        msg = None
        if j.get("entry"):
            value = j["entry"][0]["changes"][0]["value"]
            if value.get("messages"):
                msg = value["messages"][0]

        if not msg:
            return JSONResponse(content={"status": "acknowledged"})

        from_ = from_ or msg.get("from")
        logger.info("Incoming WhatsApp message | type=%s from=%s", msg.get("type"), from_)

        if not from_:
            return JSONResponse(content={"status": "acknowledged"})

        # Respond to WhatsApp immediately; transcription/RAG/LLM work happens in the
        # background so this endpoint stays fast under concurrent load and WhatsApp
        # never times out waiting on a slow voice-note transcription.
        background_tasks.add_task(_process_incoming_message, msg, from_)

        return JSONResponse(content={"ok": True})

    except Exception:
        logger.exception("WhatsApp webhook failed")
        raise HTTPException(status_code=500, detail="Internal server error")

# ============================================================
# Internal API — called by the main ticketing tool to relay an agent's
# reply back out over WhatsApp for tickets raised through this bot.
# See routes/bd_support_api.py / whatsapp_client.send_to_ticket in that repo.
# ============================================================

@app.post("/internal/whatsapp/send", tags=["Internal"])
async def internal_whatsapp_send(request: Request):
    api_key = request.headers.get("X-API-Key", "")
    expected = getattr(settings, "BD_SUPPORT_API_KEY", "") or ""
    if not expected or not hmac.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")

    payload = await request.json()
    phone = (payload.get("phone") or "").strip()
    message = (payload.get("message") or "").strip()
    if not phone or not message:
        raise HTTPException(status_code=400, detail="phone and message are required")

    from config.rate_limit import allow
    if not allow(phone):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    result = whatsapp_service.send_message(phone, message=message)
    return {"ok": bool(result.get("ok"))}


# ============================================================
# Knowledge Base Ops
# ============================================================

@app.post("/kb/reindex", tags=["Knowledge Base"])
def reindex():
    faiss_store.save()
    return {"reindexed": len(faiss_store.docs)}

@app.post("/kb/reload", tags=["Knowledge Base"])
def reload_kb(admin_key: str = Query(None)):
    if settings.KB_RELOAD_KEY and admin_key != settings.KB_RELOAD_KEY:
        raise HTTPException(status_code=403)
    faiss_store._load_if_exists()
    return {"reloaded": len(faiss_store.docs)}

@app.get("/kb/status", tags=["Knowledge Base"])
def kb_status():
    return {
        "doc_count": len(faiss_store.docs),
        "embedding_dim": EMBEDDING_DIM,
        "confidence_threshold": getattr(settings, "ANSWER_CONFIDENCE_THRESHOLD", None),
    }