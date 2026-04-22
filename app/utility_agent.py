import re
from dataclasses import dataclass
from typing import Optional

from app.capabilities import CAPABILITY_ENEL_DEBT_LOOKUP, get_available_actions
from app.config import Settings
from app.conversation_state import (
    STATE_COLLECT_ENEL_CLIENT_ID,
    clear_conversation_state,
    get_active_conversation_state,
    save_conversation_state,
)
from app.domain_repo import (
    PropertyRecord,
    UtilityAccountRecord,
    get_enel_electricity_account_for_property,
    list_active_properties_for_user,
    resolve_active_property_for_user,
    save_enel_electricity_client_number,
)
from app.grounded_response import compose_grounded_response
from app.sencillito import SencillitoEnelDebtStatus, fetch_sencillito_enel_debt_status


CLIENT_IDENTIFIER_PATTERN = re.compile(r"\b\d{3,}-?\d\b")


@dataclass(frozen=True)
class UtilityAgentResult:
    reply: str


def handle_utility_debt_task(
    sender_phone: str,
    message_body: str,
    settings: Settings,
    *,
    property_hint: Optional[str] = None,
) -> UtilityAgentResult:
    pending_state = get_active_conversation_state(sender_phone, settings)
    if pending_state and pending_state.state_type == STATE_COLLECT_ENEL_CLIENT_ID:
        return handle_enel_client_identifier_reply(
            sender_phone, message_body, pending_state.payload, settings
        )

    property_record = resolve_active_property_for_user(
        sender_phone, settings, property_hint=property_hint
    )
    if property_record is None:
        properties = list_active_properties_for_user(sender_phone, settings)
        if not properties:
            return UtilityAgentResult(
                reply="No encontré departamentos activos asociados a tu usuario."
            )
        if len(properties) == 1 and property_hint:
            return UtilityAgentResult(
                reply=(
                    "No encontré un departamento que coincida con ese nombre. "
                    f"Tengo registrado: {properties[0].name}."
                )
            )
        return UtilityAgentResult(reply=build_property_clarification_reply(properties))

    account = get_enel_electricity_account_for_property(
        property_record.property_id, settings
    )
    if account is None or not is_valid_client_identifier(account.service_account_number):
        save_conversation_state(
            sender_phone,
            STATE_COLLECT_ENEL_CLIENT_ID,
            {
                "property_id": property_record.property_id,
                "property_name": property_record.name,
                "provider": "ENEL",
                "utility_type": "ELECTRICITY",
            },
            settings,
        )
        return UtilityAgentResult(
            reply=(
                f"No tengo registrado el número de cliente ENEL para {property_record.name}. "
                "¿Me lo puedes enviar? Aparece en la boleta como “N° de cliente” "
                "o “Número de cliente”."
            )
        )

    return UtilityAgentResult(reply=lookup_and_answer_enel_debt(account, settings))


def handle_enel_client_identifier_reply(
    sender_phone: str,
    message_body: str,
    payload: dict,
    settings: Settings,
) -> UtilityAgentResult:
    client_identifier = extract_client_identifier(message_body)
    if not client_identifier:
        property_name = str(payload.get("property_name") or "ese departamento")
        return UtilityAgentResult(
            reply=(
                f"Necesito el número de cliente ENEL de {property_name}. "
                "Por ejemplo: 312091-0."
            )
        )

    property_id = str(payload.get("property_id") or "")
    if not property_id:
        clear_conversation_state(sender_phone, settings)
        return UtilityAgentResult(
            reply="Perdí el contexto del departamento. Pregúntame nuevamente por la cuenta de luz."
        )

    account = save_enel_electricity_client_number(
        property_id, client_identifier, settings
    )
    clear_conversation_state(sender_phone, settings)
    answer = lookup_and_answer_enel_debt(account, settings)
    return UtilityAgentResult(
        reply=f"Listo, guardé el número de cliente ENEL {client_identifier}.\n\n{answer}"
    )


def lookup_and_answer_enel_debt(
    account: UtilityAccountRecord, settings: Settings
) -> str:
    if not account.service_account_number:
        return (
            f"No tengo registrado el número de cliente ENEL para {account.property_name}."
        )

    debt_status = fetch_sencillito_enel_debt_status(account.service_account_number)
    return compose_enel_debt_answer(account, debt_status)


def compose_enel_debt_answer(
    account: UtilityAccountRecord, debt_status: SencillitoEnelDebtStatus
) -> str:
    invoice = debt_status.invoices[0] if debt_status.invoices else None
    amount_text = format_clp(debt_status.total_amount)
    if debt_status.total_amount > 0:
        fallback_text = (
            f"Para {account.property_name}, la cuenta ENEL "
            f"{account.service_account_number} aparece con deuda actual de "
            f"{amount_text}."
        )
        if invoice and invoice.document_number:
            fallback_text += f" Documento asociado: {invoice.document_number}."
    else:
        fallback_text = (
            f"Para {account.property_name}, no aparece deuda actual en la "
            f"cuenta ENEL {account.service_account_number}."
        )

    facts = {
        "capability": CAPABILITY_ENEL_DEBT_LOOKUP,
        "available_actions": get_available_actions(CAPABILITY_ENEL_DEBT_LOOKUP),
        "property_name": account.property_name,
        "provider": account.provider_name,
        "utility_type": account.utility_type,
        "client_identifier": account.service_account_number,
        "debt_found": debt_status.total_amount > 0,
        "amount": debt_status.total_amount,
        "currency": "CLP",
        "amount_text": amount_text,
        "document_number": None if invoice is None else invoice.document_number,
        "debt_label": None if invoice is None else invoice.label,
        "source": "portal de pago",
    }
    return compose_grounded_response(facts, fallback_text)


def build_property_clarification_reply(properties: list[PropertyRecord]) -> str:
    if len(properties) == 1:
        return f"¿Quieres revisar la cuenta de luz de {properties[0].name}?"

    property_names = ", ".join(property_record.name for property_record in properties)
    return (
        "¿De cuál departamento quieres revisar la cuenta de luz? "
        f"Tengo registrados: {property_names}."
    )


def extract_client_identifier(message_body: str) -> Optional[str]:
    match = CLIENT_IDENTIFIER_PATTERN.search(message_body)
    if match is None:
        return None
    value = match.group(0)
    if "-" in value:
        return value
    return value


def is_valid_client_identifier(value: Optional[str]) -> bool:
    if not value:
        return False
    return CLIENT_IDENTIFIER_PATTERN.fullmatch(value.strip()) is not None


def format_clp(amount: int) -> str:
    return f"${amount:,.0f}".replace(",", ".")
