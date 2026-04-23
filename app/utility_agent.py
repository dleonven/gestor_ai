import re
from dataclasses import dataclass
from typing import Optional

from app.capabilities import (
    CAPABILITY_ENEL_DEBT_LOOKUP,
    CAPABILITY_WATER_DEBT_LOOKUP,
    get_available_actions,
)
from app.config import Settings
from app.conversation_state import (
    STATE_COLLECT_ENEL_CLIENT_ID,
    STATE_COLLECT_UTILITY_ACCOUNT_ID,
    clear_conversation_state,
    get_active_conversation_state,
    save_conversation_state,
)
from app.domain_repo import (
    PropertyRecord,
    UtilityAccountRecord,
    get_enel_electricity_account_for_property,
    get_utility_account_for_property,
    list_active_properties_for_user,
    resolve_active_property_for_user,
    save_enel_electricity_client_number,
    save_utility_client_number,
)
from app.grounded_response import compose_grounded_response
from app.sencillito import (
    PROVIDER_ENEL,
    SencillitoDebtStatus,
    SencillitoEnelDebtStatus,
    SencillitoError,
    UTILITY_ELECTRICITY,
    UTILITY_WATER,
    fetch_sencillito_debt_status,
    fetch_sencillito_enel_debt_status,
    get_sencillito_provider_config,
    get_supported_provider_names,
    resolve_supported_provider_name,
)


CLIENT_IDENTIFIER_PATTERN = re.compile(r"\b\d{3,}(?:-\d)?\b")


@dataclass(frozen=True)
class UtilityAgentResult:
    reply: str


def handle_utility_debt_task(
    sender_phone: str,
    message_body: str,
    settings: Settings,
    *,
    property_hint: Optional[str] = None,
    utility_type: str = UTILITY_ELECTRICITY,
    provider_name: Optional[str] = PROVIDER_ENEL,
) -> UtilityAgentResult:
    pending_state = get_active_conversation_state(sender_phone, settings)
    if pending_state and pending_state.state_type in {
        STATE_COLLECT_ENEL_CLIENT_ID,
        STATE_COLLECT_UTILITY_ACCOUNT_ID,
    }:
        return handle_utility_identifier_reply(
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
        return UtilityAgentResult(
            reply=build_property_clarification_reply(properties, utility_type)
        )

    resolved_provider = provider_name
    account = get_account_for_property(
        property_record.property_id,
        settings,
        utility_type=utility_type,
        provider_name=resolved_provider,
    )
    if account and account.provider_name:
        resolved_provider = account.provider_name

    if utility_type == UTILITY_WATER and not resolved_provider:
        save_conversation_state(
            sender_phone,
            STATE_COLLECT_UTILITY_ACCOUNT_ID,
            {
                "property_id": property_record.property_id,
                "property_name": property_record.name,
                "provider": None,
                "utility_type": utility_type,
            },
            settings,
        )
        providers_text = ", ".join(get_supported_provider_names(UTILITY_WATER)[:6])
        return UtilityAgentResult(
            reply=(
                f"Para revisar el agua de {property_record.name}, necesito la empresa y el número de cliente o servicio. "
                f"Por ejemplo: Aguas Andinas 21503894. También puedo revisar {providers_text}."
            )
        )

    if account is None or not is_valid_client_identifier(account.service_account_number):
        save_conversation_state(
            sender_phone,
            STATE_COLLECT_UTILITY_ACCOUNT_ID,
            {
                "property_id": property_record.property_id,
                "property_name": property_record.name,
                "provider": resolved_provider,
                "utility_type": utility_type,
            },
            settings,
        )
        return UtilityAgentResult(
            reply=build_missing_identifier_reply(property_record.name, utility_type, resolved_provider)
        )

    return UtilityAgentResult(
        reply=lookup_and_answer_utility_debt(account, settings)
    )


def handle_utility_identifier_reply(
    sender_phone: str,
    message_body: str,
    payload: dict,
    settings: Settings,
) -> UtilityAgentResult:
    utility_type = str(payload.get("utility_type") or UTILITY_ELECTRICITY)
    provider_name = payload.get("provider")
    provider_text = str(provider_name) if provider_name else None

    if utility_type == UTILITY_WATER and not provider_text:
        provider_text = resolve_supported_provider_name(message_body, UTILITY_WATER)
        if not provider_text:
            property_name = str(payload.get("property_name") or "ese departamento")
            return UtilityAgentResult(
                reply=(
                    f"Necesito la empresa de agua de {property_name} y el número de cliente o servicio. "
                    "Por ejemplo: Aguas Andinas 21503894."
                )
            )

    client_identifier = extract_client_identifier(message_body)
    if not client_identifier:
        property_name = str(payload.get("property_name") or "ese departamento")
        return UtilityAgentResult(
            reply=build_missing_identifier_reply(
                property_name,
                utility_type,
                provider_text,
                include_example=True,
            )
        )

    property_id = str(payload.get("property_id") or "")
    if not property_id:
        clear_conversation_state(sender_phone, settings)
        return UtilityAgentResult(
            reply=(
                "Perdí el contexto del departamento. "
                f"Pregúntame nuevamente por la cuenta de {utility_label(utility_type)}."
            )
        )

    account = save_account_identifier(
        property_id,
        utility_type=utility_type,
        provider_name=provider_text or PROVIDER_ENEL,
        client_identifier=client_identifier,
        settings=settings,
    )
    clear_conversation_state(sender_phone, settings)
    answer = lookup_and_answer_utility_debt(account, settings)
    saved_label = provider_text or PROVIDER_ENEL
    return UtilityAgentResult(
        reply=f"Listo, guardé el número de cliente {saved_label} {client_identifier}.\n\n{answer}"
    )


def lookup_and_answer_utility_debt(
    account: UtilityAccountRecord, settings: Settings
) -> str:
    del settings

    if not account.service_account_number:
        provider_label = account.provider_name or utility_label(account.utility_type)
        return (
            f"No tengo registrado el número de cliente de {provider_label} "
            f"para {account.property_name}."
        )

    if account.utility_type == UTILITY_ELECTRICITY and account.provider_name.upper() == PROVIDER_ENEL:
        debt_status = fetch_sencillito_enel_debt_status(account.service_account_number)
    else:
        debt_status = fetch_sencillito_debt_status(
            account.service_account_number,
            utility_type=account.utility_type,
            provider_name=account.provider_name,
        )
    return compose_utility_debt_answer(account, debt_status)


def compose_utility_debt_answer(
    account: UtilityAccountRecord, debt_status: SencillitoDebtStatus
) -> str:
    invoice = debt_status.invoices[0] if debt_status.invoices else None
    amount_text = format_clp(debt_status.total_amount)
    utility_phrase = utility_noun_phrase(account.utility_type)
    provider_label = account.provider_name

    if debt_status.total_amount > 0:
        fallback_text = (
            f"Para {account.property_name}, la {utility_phrase} {provider_label} "
            f"{account.service_account_number} aparece con deuda actual de {amount_text}."
        )
        if invoice and invoice.document_number:
            fallback_text += f" Documento asociado: {invoice.document_number}."
    else:
        fallback_text = (
            f"Para {account.property_name}, no aparece deuda actual en la "
            f"{utility_phrase} {provider_label} {account.service_account_number}."
        )

    facts = {
        "capability": capability_for(account.utility_type, provider_label),
        "available_actions": get_available_actions(
            capability_for(account.utility_type, provider_label)
        ),
        "property_name": account.property_name,
        "provider": provider_label,
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


def compose_enel_debt_answer(
    account: UtilityAccountRecord, debt_status: SencillitoEnelDebtStatus
) -> str:
    return compose_utility_debt_answer(account, debt_status)


def get_account_for_property(
    property_id: str,
    settings: Settings,
    *,
    utility_type: str,
    provider_name: Optional[str],
) -> Optional[UtilityAccountRecord]:
    if utility_type == UTILITY_ELECTRICITY and (provider_name or "").upper() == PROVIDER_ENEL:
        return get_enel_electricity_account_for_property(property_id, settings)
    return get_utility_account_for_property(
        property_id,
        settings,
        utility_type=utility_type,
        provider_name=provider_name,
    )


def save_account_identifier(
    property_id: str,
    *,
    utility_type: str,
    provider_name: str,
    client_identifier: str,
    settings: Settings,
) -> UtilityAccountRecord:
    if utility_type == UTILITY_ELECTRICITY and provider_name.upper() == PROVIDER_ENEL:
        return save_enel_electricity_client_number(property_id, client_identifier, settings)

    config = get_sencillito_provider_config(utility_type, provider_name)
    return save_utility_client_number(
        property_id,
        provider_name=config.provider_name,
        utility_type=utility_type,
        client_identifier=client_identifier,
        payment_url=config.payment_url,
        settings=settings,
    )


def build_missing_identifier_reply(
    property_name: str,
    utility_type: str,
    provider_name: Optional[str],
    *,
    include_example: bool = False,
) -> str:
    if utility_type == UTILITY_ELECTRICITY:
        return (
            f"No tengo registrado el número de cliente ENEL para {property_name}. "
            "¿Me lo puedes enviar? Aparece en la boleta como “N° de cliente” "
            "o “Número de cliente”."
        )

    provider_label = provider_name or "de agua"
    response = (
        f"No tengo registrado el número de cliente {provider_label} para {property_name}. "
        "¿Me lo puedes enviar?"
    )
    if include_example:
        response += " Ejemplo: 21503894."
    return response


def build_property_clarification_reply(
    properties: list[PropertyRecord], utility_type: str
) -> str:
    utility_text = "cuenta de agua" if utility_type == UTILITY_WATER else "cuenta de luz"
    if len(properties) == 1:
        return f"¿Quieres revisar la {utility_text} de {properties[0].name}?"

    property_names = ", ".join(property_record.name for property_record in properties)
    return (
        f"¿De cuál departamento quieres revisar la {utility_text}? "
        f"Tengo registrados: {property_names}."
    )


def capability_for(utility_type: str, provider_name: str) -> str:
    if utility_type == UTILITY_WATER:
        return CAPABILITY_WATER_DEBT_LOOKUP
    if provider_name.upper() == PROVIDER_ENEL:
        return CAPABILITY_ENEL_DEBT_LOOKUP
    return CAPABILITY_ENEL_DEBT_LOOKUP


def utility_label(utility_type: str) -> str:
    if utility_type == UTILITY_WATER:
        return "agua"
    return "luz"


def utility_noun_phrase(utility_type: str) -> str:
    if utility_type == UTILITY_WATER:
        return "cuenta de agua"
    return "cuenta"


def extract_client_identifier(message_body: str) -> Optional[str]:
    match = CLIENT_IDENTIFIER_PATTERN.search(message_body)
    if match is None:
        return None
    return match.group(0)


def is_valid_client_identifier(value: Optional[str]) -> bool:
    if not value:
        return False
    return CLIENT_IDENTIFIER_PATTERN.fullmatch(value.strip()) is not None


def format_clp(amount: int) -> str:
    return f"${amount:,.0f}".replace(",", ".")

