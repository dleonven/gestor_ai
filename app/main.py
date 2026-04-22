import asyncio
import logging
import unicodedata
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.bot_intent import (
    INTENT_CONTRACT_QA,
    INTENT_RENT_STATUS,
    INTENT_UTILITY_DEBT,
    classify_message,
)
from app.config import Settings
from app.contract_qa import answer_contract_question
from app.domain_repo import (
    get_enel_electricity_account_for_user,
    get_latest_rent_status_for_landlord,
)
from app.grounded_response import compose_grounded_response
from app.sencillito import fetch_sencillito_enel_debt_status
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
    intent = classify_message(message_body)
    if intent.intent == INTENT_CONTRACT_QA:
        return await resolve_contract_question(message_body)
    if user.role == ROLE_LANDLORD and intent.intent == INTENT_RENT_STATUS:
        return await resolve_landlord_rent_status(sender_phone, settings)
    if intent.intent == INTENT_UTILITY_DEBT:
        return await resolve_enel_debt_status(
            sender_phone, settings, property_hint=intent.property_hint
        )
    if user.role == ROLE_TENANT:
        return TENANT_REPLY
    if user.role == ROLE_LANDLORD:
        return LANDLORD_REPLY
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


async def resolve_enel_debt_status(
    sender_phone: str, settings: Settings, property_hint: Optional[str] = None
) -> str:
    try:
        utility_account = await asyncio.to_thread(
            get_enel_electricity_account_for_user,
            sender_phone,
            settings,
            property_hint,
        )
    except Exception:
        LOGGER.exception("enel_account_lookup status=error from=%s", sender_phone)
        return "No pude revisar la cuenta de luz ahora."

    if utility_account is None:
        if property_hint:
            return (
                "No encontré una cuenta ENEL activa asociada a esa propiedad. "
                "Revisa si el nombre del departamento está bien escrito."
            )
        return "No encontré una cuenta ENEL activa asociada a tu usuario."

    try:
        debt_status = await asyncio.to_thread(
            fetch_sencillito_enel_debt_status,
            utility_account.service_account_number,
        )
    except Exception:
        LOGGER.exception(
            "enel_debt_lookup status=error account=%s",
            utility_account.service_account_number,
        )
        return "No pude consultar ENEL en este momento. Inténtalo nuevamente en unos minutos."

    invoice = debt_status.invoices[0] if debt_status.invoices else None
    amount_text = format_clp(debt_status.total_amount)
    if debt_status.total_amount > 0:
        fallback_text = (
            f"Para {utility_account.property_name}, la cuenta ENEL "
            f"{utility_account.service_account_number} aparece con deuda actual de "
            f"{amount_text}."
        )
        if invoice and invoice.document_number:
            fallback_text += f" Documento asociado: {invoice.document_number}."
    else:
        fallback_text = (
            f"Para {utility_account.property_name}, no aparece deuda actual en la "
            f"cuenta ENEL {utility_account.service_account_number}."
        )

    facts = {
        "capability": "enel_electricity_debt",
        "property_name": utility_account.property_name,
        "provider": utility_account.provider_name,
        "utility_type": utility_account.utility_type,
        "client_identifier": utility_account.service_account_number,
        "debt_found": debt_status.total_amount > 0,
        "amount": debt_status.total_amount,
        "currency": "CLP",
        "amount_text": amount_text,
        "document_number": None if invoice is None else invoice.document_number,
        "debt_label": None if invoice is None else invoice.label,
        "source": "portal de pago",
    }
    return compose_grounded_response(facts, fallback_text)


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
