import base64
import json
import os
from pathlib import Path
from typing import Any

import httpx


DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
DEFAULT_CONTRACT_PATH = Path(
    os.getenv("CONTRACT_PDF_PATH", "data/contracts/contrato_prueba.pdf")
)

SYSTEM_PROMPT = """Eres un analista de contratos de arriendo en Chile.

Responde solamente usando el contenido del documento entregado.
No inventes clausulas, fechas, montos ni interpretaciones legales no respaldadas.
Si la respuesta no aparece de forma clara en el contrato, di exactamente: "No encontrado en el contrato."

Siempre responde en espanol con este formato:

Respuesta:
<respuesta breve>

Evidencia:
<cita o resumen muy cercano del fragmento relevante>

Confianza:
<alta|media|baja>

Notas:
<aclaraciones breves o "Ninguna">
"""


def encode_pdf_as_data_url(path: Path) -> str:
    pdf_bytes = path.read_bytes()
    base64_string = base64.b64encode(pdf_bytes).decode("utf-8")
    return f"data:application/pdf;base64,{base64_string}"


def build_request_payload(model: str, question: str, contract_path: Path) -> dict[str, Any]:
    return {
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
                        "type": "input_file",
                        "filename": contract_path.name,
                        "file_data": encode_pdf_as_data_url(contract_path),
                    },
                    {
                        "type": "input_text",
                        "text": (
                            "Contesta la siguiente pregunta usando solo el contrato adjunto: "
                            f"{question}"
                        ),
                    },
                ],
            },
        ],
        "max_output_tokens": 2500,
        "reasoning": {"effort": "minimal"},
    }


def extract_output_text(response_json: dict[str, Any]) -> str:
    texts: list[str] = []
    for item in response_json.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                texts.append(text)
    return "\n".join(texts).strip()


def answer_contract_question(
    question: str,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    model: str = DEFAULT_MODEL,
) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")
    if not contract_path.exists():
        raise FileNotFoundError(f"Contract not found: {contract_path}")

    payload = build_request_payload(model=model, question=question, contract_path=contract_path)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            "https://api.openai.com/v1/responses",
            headers=headers,
            json=payload,
        )

    if response.is_error:
        raise RuntimeError(
            f"OpenAI API error {response.status_code}: {response.text}"
        )

    response_json = response.json()
    output_text = extract_output_text(response_json)
    if not output_text:
        return json.dumps(response_json, indent=2, ensure_ascii=False)
    return output_text
