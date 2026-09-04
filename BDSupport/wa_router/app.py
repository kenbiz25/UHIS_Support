"""wa_router/app.py — WhatsApp webhook dispatcher.

Meta allows only ONE webhook URL per WABA/App, shared across every phone
number registered under it. This tiny service IS that one URL. It does
nothing but look at which phone_number_id an inbound message is addressed
to and forward the raw request to whichever backend bot owns that number,
so multiple independent bots (e.g. ComEMR and the Bangladesh SPICE bot) can
share one Meta app without either bot's own code needing to know the other
exists. Deliberately dependency-light (fastapi/uvicorn/httpx only) since its
only job is routing, not RAG/KB/WhatsApp-send logic.

Configure via environment variables:
  WA_VERIFY_TOKEN   Must match whatever's registered as the webhook's verify
                     token in Meta's dashboard.
  WA_ROUTES          JSON map of phone_number_id -> backend webhook URL, e.g.
                     '{"804213596118945": "http://127.0.0.1:8002/whatsapp/webhook",
                       "967321976462732": "http://127.0.0.1:8000/whatsapp/webhook"}'
  WA_DEFAULT_ROUTE   Optional fallback backend URL for a phone_number_id not
                     listed in WA_ROUTES (leave unset to just drop those).
"""
import json
import logging
import os

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wa_router")

app = FastAPI(title="WhatsApp Webhook Router")

VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN", "")
ROUTES = json.loads(os.getenv("WA_ROUTES", "{}"))
DEFAULT_ROUTE = os.getenv("WA_DEFAULT_ROUTE", "")


@app.get("/health")
def health():
    return {"status": "ok", "routes": list(ROUTES.keys())}


@app.get("/whatsapp/webhook")
async def verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return Response(content=hub_challenge or "", media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


def _extract_phone_number_id(payload: dict) -> str:
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        return value.get("metadata", {}).get("phone_number_id", "")
    except Exception:
        return ""


@app.post("/whatsapp/webhook")
async def dispatch(request: Request):
    body = await request.body()
    try:
        payload = json.loads(body)
    except Exception:
        logger.warning("Non-JSON webhook payload received")
        return {"status": "ignored"}

    phone_number_id = _extract_phone_number_id(payload)
    target = ROUTES.get(phone_number_id) or DEFAULT_ROUTE

    if not target:
        logger.error("No route configured for phone_number_id=%s", phone_number_id)
        return {"status": "no_route"}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                target,
                content=body,
                headers={"Content-Type": "application/json"},
            )
        logger.info(
            "Routed phone_number_id=%s -> %s (status=%s)",
            phone_number_id, target, resp.status_code,
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type", "application/json"),
        )
    except Exception:
        logger.exception(
            "Failed forwarding to %s for phone_number_id=%s", target, phone_number_id,
        )
        # Still ack Meta with 200 so it doesn't retry-storm us over a
        # transient backend hiccup - the message is lost for this bot either
        # way, retry-storming just adds load without recovering it.
        return {"status": "forward_failed"}
