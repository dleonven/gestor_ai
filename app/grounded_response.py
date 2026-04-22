import json
import os
from typing import Any

import httpx


DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

SYSTEM_PROMPT = """Eres un asistente de WhatsApp para administración de propiedades en Chile.

Escribe una respuesta breve, clara y natural en español chileno.
Usa solamente los hechos entregados en JSON.
Responde solo la pregunta actual del usuario.
No inventes montos, fechas, responsabilidades, documentos ni consejos legales.
No ofrezcas acciones que no estén explícitamente listadas en los hechos como acciones disponibles.
No digas que puedes gestionar pagos, enviar comprobantes, programar recordatorios o regularizar cuentas salvo que los hechos lo indiquen.
Si available_actions está vacío, entrega solo la respuesta informativa y no agregues preguntas de seguimiento.
No listes capacidades generales salvo que los hechos indiquen que el usuario pidió ayuda general o que la intención no está soportada.
Si falta un dato, dilo con cuidado.
"""


def compose_grounded_response(
    facts: dict[str, Any],
    fallback_text: str,
    model: str = DEFAULT_MODEL,
) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return fallback_text

    try:
        return compose_grounded_response_with_llm(
            facts, fallback_text=fallback_text, api_key=api_key, model=model
        )
    except Exception:
        return fallback_text


def compose_grounded_response_with_llm(
    facts: dict[str, Any],
    *,
    fallback_text: str,
    api_key: str,
    model: str,
) -> str:
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Redacta la respuesta usando solo estos hechos:\n"
                            f"{json.dumps(facts, ensure_ascii=False)}"
                        ),
                    }
                ],
            },
        ],
        "max_output_tokens": 500,
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
    return output_text or fallback_text


def _extract_output_text(response_json: dict[str, Any]) -> str:
    texts: list[str] = []
    for item in response_json.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                texts.append(text)
    return "\n".join(texts).strip()
