import asyncio
import logging
import unicodedata
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.bot_intent import (
    INTENT_CONTRACT_QA,
    INTENT_PROPERTY_LIST,
    INTENT_RENT_STATUS,
    INTENT_UTILITY_DEBT,
    classify_message,
)
from app.capabilities import build_supported_actions_reply
from app.config import Settings
from app.conversation_state import STATE_COLLECT_ENEL_CLIENT_ID, get_active_conversation_state
from app.contract_qa import answer_contract_question
from app.domain_repo import (
    get_latest_rent_status_for_landlord,
    list_active_properties_for_user,
)
from app.schemas import extract_incoming_messages
from app.users_repo import ROLE_LANDLORD, ROLE_TENANT, get_user_by_phone
from app.utility_agent import handle_utility_debt_task
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
        reply_body = await resolve_reply_body(
            incoming.sender_phone, incoming.message_body, settings
        )
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


async def resolve_reply_body(
    sender_phone: str, message_body: str, settings: Settings
) -> str:
    try:
        user = await asyncio.to_thread(get_user_by_phone, sender_phone, settings)
    except Exception:
        LOGGER.exception("user_lookup status=error from=%s", sender_phone)
        return UNAUTHORIZED_REPLY

    if user is None or not user.is_active:
        return UNAUTHORIZED_REPLY
    if await has_pending_utility_task(sender_phone, settings):
        return await resolve_enel_debt_status(sender_phone, message_body, settings)
    intent = classify_message(message_body)
    if intent.intent == INTENT_CONTRACT_QA:
        return await resolve_contract_question(message_body)
    if intent.intent == INTENT_PROPERTY_LIST:
        return await resolve_property_list(sender_phone, settings)
    if user.role == ROLE_LANDLORD and intent.intent == INTENT_RENT_STATUS:
        return await resolve_landlord_rent_status(sender_phone, settings)
    if intent.intent == INTENT_UTILITY_DEBT:
        return await resolve_enel_debt_status(
            sender_phone, message_body, settings, property_hint=intent.property_hint
        )
    if user.role in (ROLE_TENANT, ROLE_LANDLORD):
        return unknown_intent_reply(user.role)
    return UNAUTHORIZED_REPLY


async def resolve_landlord_rent_status(sender_phone: str, settings: Settings) -> str:
    try:
        rent_status = await asyncio.to_thread(
            get_latest_rent_status_for_landlord, sender_phone, settings
        )
    except Exception:
        LOGGER.exception("rent_status_lookup status=error from=%s", sender_phone)
        return "No pude revisar el estado del arriendo ahora."

    if rent_status is None:
        return "No encontré un arriendo activo asociado a tu usuario."

    status_map = {
        "PAID": "pagado",
        "PARTIALLY_PAID": "parcialmente pagado",
        "PENDING": "pendiente",
        "OVERDUE": "vencido",
        "CANCELLED": "cancelado",
    }
    status_text = status_map.get(rent_status.charge_status, rent_status.charge_status)
    amount_due = int(rent_status.amount_due)
    amount_paid = int(rent_status.amount_paid)
    return (
        f"Arriendo de {rent_status.property_name}: {status_text}. "
        f"Vence el {rent_status.due_date}. "
        f"Total {amount_due} {rent_status.currency}, pagado {amount_paid} {rent_status.currency}."
    )


async def resolve_property_list(sender_phone: str, settings: Settings) -> str:
    try:
        properties = await asyncio.to_thread(
            list_active_properties_for_user, sender_phone, settings
        )
    except Exception:
        LOGGER.exception("property_list_lookup status=error from=%s", sender_phone)
        return "No pude revisar tus departamentos registrados ahora."

    if not properties:
        return "No encontré departamentos activos asociados a tu usuario."

    if len(properties) == 1:
        return f"Tengo 1 departamento registrado: {properties[0].name}."

    property_names = "\n".join(
        f"{index}. {property_record.name}"
        for index, property_record in enumerate(properties, start=1)
    )
    return f"Tengo {len(properties)} departamentos registrados:\n{property_names}"


async def has_pending_utility_task(sender_phone: str, settings: Settings) -> bool:
    try:
        state = await asyncio.to_thread(
            get_active_conversation_state, sender_phone, settings
        )
    except Exception:
        LOGGER.exception("conversation_state_lookup status=error from=%s", sender_phone)
        return False
    return state is not None and state.state_type == STATE_COLLECT_ENEL_CLIENT_ID


async def resolve_enel_debt_status(
    sender_phone: str,
    message_body: str,
    settings: Settings,
    property_hint: Optional[str] = None,
) -> str:
    try:
        result = await asyncio.to_thread(
            handle_utility_debt_task,
            sender_phone,
            message_body,
            settings,
            property_hint=property_hint,
        )
    except Exception:
        LOGGER.exception("utility_agent status=error from=%s", sender_phone)
        return "No pude consultar ENEL en este momento. Inténtalo nuevamente en unos minutos."
    return result.reply


async def resolve_contract_question(message_body: str) -> str:
    try:
        return await asyncio.to_thread(answer_contract_question, message_body)
    except Exception:
        LOGGER.exception("contract_qa status=error question=%s", message_body)
        return "No pude revisar el contrato ahora."


def is_rent_status_question(message_body: str) -> bool:
    normalized = normalize_text(message_body)
    return (
        "pagaron el arriendo" in normalized
        or "se pago el arriendo" in normalized
        or "estado del arriendo" in normalized
        or "arriendo pagado" in normalized
    )


def is_contract_question(message_body: str) -> bool:
    normalized = normalize_text(message_body)
    return (
        "monto del arriendo" in normalized
        or "valor del arriendo" in normalized
        or "cuando puede dar aviso" in normalized
        or "cuando puedo dar aviso" in normalized
        or "garantia" in normalized
        or "deposito" in normalized
        or "gastos comunes" in normalized
        or "fecha de inicio" in normalized
        or "fecha de termino" in normalized
        or "reajusta el arriendo" in normalized
        or "reajuste del arriendo" in normalized
        or "contrato" in normalized
    )


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def format_clp(amount: int) -> str:
    return f"${amount:,.0f}".replace(",", ".")


def unknown_intent_reply(role: str) -> str:
    return build_supported_actions_reply("No pude identificar bien tu solicitud.", role)
