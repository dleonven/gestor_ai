from app.bot_intent import (
    INTENT_CONTRACT_QA,
    INTENT_PROPERTY_LIST,
    INTENT_RENT_STATUS,
    INTENT_UTILITY_DEBT,
    classify_message_fallback,
)
from app.sencillito import (
    PROVIDER_AGUAS_ANDINAS,
    PROVIDER_ENEL,
    UTILITY_ELECTRICITY,
    UTILITY_WATER,
)


def test_classify_message_fallback_extracts_enel_debt_intent() -> None:
    result = classify_message_fallback(
        "quiero saber si mi departamento de navidad tiene deuda en la cuenta de luz"
    )

    assert result.intent == INTENT_UTILITY_DEBT
    assert result.utility_type == UTILITY_ELECTRICITY
    assert result.provider == PROVIDER_ENEL
    assert result.property_hint == "navidad"


def test_classify_message_fallback_extracts_rent_status_intent() -> None:
    result = classify_message_fallback("Pagaron el arriendo?")

    assert result.intent == INTENT_RENT_STATUS


def test_classify_message_fallback_extracts_water_debt_intent() -> None:
    result = classify_message_fallback(
        "quiero saber si mi departamento de navidad tiene deuda de agua con Aguas Andinas"
    )

    assert result.intent == INTENT_UTILITY_DEBT
    assert result.utility_type == UTILITY_WATER
    assert result.provider == PROVIDER_AGUAS_ANDINAS
    assert result.property_hint == "navidad"


def test_classify_message_fallback_extracts_contract_intent() -> None:
    result = classify_message_fallback("Cuando puedo dar aviso segun el contrato?")

    assert result.intent == INTENT_CONTRACT_QA


def test_classify_message_fallback_extracts_property_list_intent() -> None:
    result = classify_message_fallback("cuantos departamentos mios tienes registrados?")

    assert result.intent == INTENT_PROPERTY_LIST
