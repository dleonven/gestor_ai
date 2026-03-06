import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.config import Settings
from app.schemas import extract_incoming_messages
from app.users_repo import ROLE_LANDLORD, ROLE_TENANT, get_user_by_phone
from app.whatsapp import send_text_reply


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
LOGGER = logging.getLogger("whatsapp_bot")
TENANT_REPLY = "hello arrendatario"
LANDLORD_REPLY = "hello arrendador"
UNAUTHORIZED_REPLY = "no autorizado"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = Settings.from_env()
    yield


app = FastAPI(title="WhatsApp Role-Based MVP", lifespan=lifespan)


@app.get("/health")
async def health() -> PlainTextResponse:
    return PlainTextResponse("ok")


@app.get("/webhook")
async def verify_webhook(
    request: Request,
    hub_mode: Optional[str] = Query(default=None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(default=None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    settings: Settings = request.app.state.settings

    if hub_mode != "subscribe" or hub_verify_token != settings.verify_token:
        raise_forbidden = PlainTextResponse("forbidden", status_code=403)
        return raise_forbidden

    return PlainTextResponse(hub_challenge or "")


@app.post("/webhook")
async def receive_webhook(request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    payload: dict[str, Any] = await request.json()
    incoming_messages = extract_incoming_messages(payload)

    if not incoming_messages:
        LOGGER.info("webhook_received status=ignored reason=no_text_messages")
        return JSONResponse({"status": "ok"})

    for incoming in incoming_messages:
        reply_body = await resolve_reply_body(incoming.sender_phone, settings)
        LOGGER.info(
            "incoming_message from=%s message_id=%s message=%s reply=%s",
            incoming.sender_phone,
            incoming.message_id,
            incoming.message_body,
            reply_body,
        )
        await send_text_reply(
            incoming.sender_phone, settings=settings, reply_body=reply_body
        )

    return JSONResponse({"status": "ok"})


async def resolve_reply_body(sender_phone: str, settings: Settings) -> str:
    try:
        user = await asyncio.to_thread(get_user_by_phone, sender_phone, settings)
    except Exception:
        LOGGER.exception("user_lookup status=error from=%s", sender_phone)
        return UNAUTHORIZED_REPLY

    if user is None or not user.is_active:
        return UNAUTHORIZED_REPLY
    if user.role == ROLE_TENANT:
        return TENANT_REPLY
    if user.role == ROLE_LANDLORD:
        return LANDLORD_REPLY
    return UNAUTHORIZED_REPLY
