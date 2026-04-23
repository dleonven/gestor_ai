import json
import os
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.sencillito import (
    PROVIDER_AGUAS_ANDINAS,
    PROVIDER_ENEL,
    UTILITY_ELECTRICITY,
    UTILITY_WATER,
    resolve_supported_provider_name,
)


INTENT_CONTRACT_QA = "CONTRACT_QA"
INTENT_RENT_STATUS = "RENT_STATUS"
INTENT_UTILITY_DEBT = "UTILITY_DEBT"
INTENT_PROPERTY_LIST = "PROPERTY_LIST"
INTENT_UNKNOWN = "UNKNOWN"

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

SYSTEM_PROMPT = """Eres el clasificador de intención de un bot de WhatsApp para administración de propiedades en Chile.

Devuelve solo JSON válido con esta forma:
{
  "intent": "CONTRACT_QA|RENT_STATUS|UTILITY_DEBT|PROPERTY_LIST|UNKNOWN",
  "utility_type": "ELECTRICITY|WATER|null",
  "provider": "ENEL|Aguas Andinas|Essbio|Esval|otro|null",
  "property_hint": "texto breve|null"
}

Reglas:
- Si pregunta por luz, electricidad, cuenta de luz o ENEL, usa intent UTILITY_DEBT, utility_type ELECTRICITY y provider ENEL.
- Si pregunta por agua, cuenta de agua, agua potable o una sanitaria como Aguas Andinas, Essbio o Esval, usa intent UTILITY_DEBT, utility_type WATER. Usa provider si el usuario menciona una empresa; si no, null.
- Si pregunta si pagaron el arriendo o estado del arriendo, usa RENT_STATUS.
- Si pregunta cuántos departamentos, propiedades o inmuebles tiene registrados, usa PROPERTY_LIST.
- Si pregunta por cláusulas, garantía, aviso, reajuste, fechas o monto del contrato, usa CONTRACT_QA.
- property_hint debe ser una palabra o frase mencionada por el usuario para identificar la propiedad, por ejemplo "navidad".
- Si no hay pista de propiedad, usa null.
- No inventes datos.
"""


@dataclass(frozen=True)
class BotIntent:
    intent: str
    utility_type: Optional[str] = None
    provider: Optional[str] = None
    property_hint: Optional[str] = None


def classify_message(message_body: str, model: str = DEFAULT_MODEL) -> BotIntent:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return classify_message_fallback(message_body)

    try:
        return classify_message_with_llm(message_body, api_key=api_key, model=model)
    except Exception:
        return classify_message_fallback(message_body)


def classify_message_with_llm(message_body: str, *, api_key: str, model: str) -> BotIntent:
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": message_body}],
            },
        ],
        "max_output_tokens": 300,
        "reasoning": {"effort": "minimal"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=20.0) as client:
        response = client.post(
            "https://api.openai.com/v1/responses",
            headers=headers,
            json=payload,
        )

    response.raise_for_status()
    output_text = _extract_output_text(response.json())
    data = json.loads(output_text)
    return _parse_intent_payload(data)


def classify_message_fallback(message_body: str) -> BotIntent:
    normalized = normalize_text(message_body)

    if any(
        term in normalized
        for term in (
            "cuenta de luz",
            "deuda de luz",
            "pagar la luz",
            "pagada la luz",
            "electricidad",
            "enel",
        )
    ):
        return BotIntent(
            intent=INTENT_UTILITY_DEBT,
            utility_type=UTILITY_ELECTRICITY,
            provider=PROVIDER_ENEL,
            property_hint=extract_property_hint_fallback(normalized),
        )

    water_provider = resolve_supported_provider_name(message_body, UTILITY_WATER)
    if water_provider or any(
        term in normalized
        for term in (
            "cuenta de agua",
            "deuda de agua",
            "agua potable",
            "pagar el agua",
            "pagada el agua",
            "aguas andinas",
            "essbio",
            "esval",
            "smapa",
            "suralis",
            "essal",
        )
    ):
        return BotIntent(
            intent=INTENT_UTILITY_DEBT,
            utility_type=UTILITY_WATER,
            provider=water_provider,
            property_hint=extract_property_hint_fallback(normalized),
        )

    if (
        "cuantos departamentos" in normalized
        or "cuantas propiedades" in normalized
        or "cuantos inmuebles" in normalized
        or "departamentos registrados" in normalized
        or "propiedades registradas" in normalized
        or "inmuebles registrados" in normalized
    ):
        return BotIntent(intent=INTENT_PROPERTY_LIST)

    if (
        "pagaron el arriendo" in normalized
        or "se pago el arriendo" in normalized
        or "estado del arriendo" in normalized
        or "arriendo pagado" in normalized
    ):
        return BotIntent(intent=INTENT_RENT_STATUS)

    if (
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
    ):
        return BotIntent(intent=INTENT_CONTRACT_QA)

    return BotIntent(intent=INTENT_UNKNOWN)


def extract_property_hint_fallback(normalized_message: str) -> Optional[str]:
    markers = ("departamento de ", "depto de ", "depa de ", "propiedad de ")
    for marker in markers:
        if marker not in normalized_message:
            continue
        after_marker = normalized_message.split(marker, 1)[1].strip()
        if not after_marker:
            return None
        return after_marker.split()[0].strip(".,;:!?") or None
    return None


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def _parse_intent_payload(data: dict[str, Any]) -> BotIntent:
    intent = str(data.get("intent") or INTENT_UNKNOWN)
    if intent not in {
        INTENT_CONTRACT_QA,
        INTENT_RENT_STATUS,
        INTENT_UTILITY_DEBT,
        INTENT_PROPERTY_LIST,
        INTENT_UNKNOWN,
    }:
        intent = INTENT_UNKNOWN

    return BotIntent(
        intent=intent,
        utility_type=_none_if_null(data.get("utility_type")),
        provider=_none_if_null(data.get("provider")),
        property_hint=_none_if_null(data.get("property_hint")),
    )


def _none_if_null(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None
    return text


def _extract_output_text(response_json: dict[str, Any]) -> str:
    texts: list[str] = []
    for item in response_json.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                texts.append(text)
    return "\n".join(texts).strip()
