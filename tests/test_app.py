import os
from collections.abc import Generator
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from app.domain_repo import RentStatusRecord
from app.domain_repo import PropertyRecord
from app.utility_agent import UtilityAgentResult
from app.users_repo import UserRecord


@pytest.fixture(autouse=True)
def env_vars() -> Generator[None, None, None]:
    os.environ["VERIFY_TOKEN"] = "test-verify-token"
    os.environ["WHATSAPP_TOKEN"] = "test-whatsapp-token"
    os.environ["PHONE_NUMBER_ID"] = "123456789"
    os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/postgres"
    os.environ["GRAPH_API_VERSION"] = "v19.0"
    os.environ["PORT"] = "3000"
    os.environ.pop("OPENAI_API_KEY", None)
    yield


def create_client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    with create_client() as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.text == "ok"


def test_webhook_verification_with_valid_token_returns_challenge() -> None:
    with create_client() as client:
        response = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test-verify-token",
                "hub.challenge": "abc123",
            },
        )

    assert response.status_code == 200
    assert response.text == "abc123"


def test_webhook_verification_with_invalid_token_returns_403() -> None:
    with create_client() as client:
        response = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "abc123",
            },
        )

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("user_record", "expected_reply"),
    [
        (
            UserRecord(phone_e164="56912345678", role="TENANT", is_active=True),
            (
                "No pude identificar bien tu solicitud.\n\n"
                "Por ahora puedo ayudarte con:\n"
                "- responder preguntas del contrato\n"
                "- listar departamentos registrados\n"
                "- consultar deuda de luz ENEL"
            ),
        ),
        (
            UserRecord(phone_e164="56912345678", role="LANDLORD", is_active=True),
            (
                "No pude identificar bien tu solicitud.\n\n"
                "Por ahora puedo ayudarte con:\n"
                "- responder preguntas del contrato\n"
                "- revisar estado del arriendo\n"
                "- listar departamentos registrados\n"
                "- consultar deuda de luz ENEL"
            ),
        ),
        (None, "no autorizado"),
        (UserRecord(phone_e164="56912345678", role="TENANT", is_active=False), "no autorizado"),
    ],
)
def test_webhook_text_message_triggers_role_based_reply(
    monkeypatch: pytest.MonkeyPatch,
    user_record: Optional[UserRecord],
    expected_reply: str,
) -> None:
    sent_messages: list[tuple[str, str]] = []

    async def fake_send_text_reply(sender_phone: str, settings, reply_body: str = "hello world") -> None:
        sent_messages.append((sender_phone, reply_body))

    def fake_get_user_by_phone(sender_phone: str, settings) -> Optional[UserRecord]:
        return user_record

    monkeypatch.setattr("app.main.send_text_reply", fake_send_text_reply)
    monkeypatch.setattr("app.main.get_user_by_phone", fake_get_user_by_phone)

    with create_client() as client:
        response = client.post(
            "/webhook",
            json={
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "messages": [
                                        {
                                            "from": "56912345678",
                                            "id": "wamid-1",
                                            "type": "text",
                                            "text": {"body": "hola"},
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ]
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert sent_messages == [("56912345678", expected_reply)]


def test_landlord_rent_status_question_returns_domain_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_messages: list[tuple[str, str]] = []

    async def fake_send_text_reply(sender_phone: str, settings, reply_body: str = "hello world") -> None:
        sent_messages.append((sender_phone, reply_body))

    def fake_get_user_by_phone(sender_phone: str, settings) -> Optional[UserRecord]:
        return UserRecord(phone_e164=sender_phone, role="LANDLORD", is_active=True)

    def fake_get_latest_rent_status_for_landlord(sender_phone: str, settings) -> RentStatusRecord:
        return RentStatusRecord(
            property_name="Depto Centro",
            due_date="2026-03-10",
            charge_status="PAID",
            amount_due=450000.0,
            amount_paid=450000.0,
            currency="CLP",
        )

    monkeypatch.setattr("app.main.send_text_reply", fake_send_text_reply)
    monkeypatch.setattr("app.main.get_user_by_phone", fake_get_user_by_phone)
    monkeypatch.setattr(
        "app.main.get_latest_rent_status_for_landlord",
        fake_get_latest_rent_status_for_landlord,
    )

    with create_client() as client:
        response = client.post(
            "/webhook",
            json={
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "messages": [
                                        {
                                            "from": "56996096419",
                                            "id": "wamid-2",
                                            "type": "text",
                                            "text": {"body": "Pagaron el arriendo?"},
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ]
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert sent_messages == [
        (
            "56996096419",
            "Arriendo de Depto Centro: pagado. Vence el 2026-03-10. Total 450000 CLP, pagado 450000 CLP.",
        )
    ]


def test_contract_question_routes_to_llm_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_messages: list[tuple[str, str]] = []

    async def fake_send_text_reply(sender_phone: str, settings, reply_body: str = "hello world") -> None:
        sent_messages.append((sender_phone, reply_body))

    def fake_get_user_by_phone(sender_phone: str, settings) -> Optional[UserRecord]:
        return UserRecord(phone_e164=sender_phone, role="LANDLORD", is_active=True)

    def fake_answer_contract_question(question: str) -> str:
        return "Respuesta:\nEl monto del arriendo es $450.000.\n\nEvidencia:\nClausula Tercero.\n\nConfianza:\nalta\n\nNotas:\nNinguna"

    monkeypatch.setattr("app.main.send_text_reply", fake_send_text_reply)
    monkeypatch.setattr("app.main.get_user_by_phone", fake_get_user_by_phone)
    monkeypatch.setattr("app.main.answer_contract_question", fake_answer_contract_question)

    with create_client() as client:
        response = client.post(
            "/webhook",
            json={
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "messages": [
                                        {
                                            "from": "56996096419",
                                            "id": "wamid-3",
                                            "type": "text",
                                            "text": {"body": "Cual es el monto del arriendo?"},
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ]
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert sent_messages == [
        (
            "56996096419",
            "Respuesta:\nEl monto del arriendo es $450.000.\n\nEvidencia:\nClausula Tercero.\n\nConfianza:\nalta\n\nNotas:\nNinguna",
        )
    ]


def test_tenant_enel_debt_question_returns_grounded_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_messages: list[tuple[str, str]] = []

    async def fake_send_text_reply(sender_phone: str, settings, reply_body: str = "hello world") -> None:
        sent_messages.append((sender_phone, reply_body))

    def fake_get_user_by_phone(sender_phone: str, settings) -> Optional[UserRecord]:
        return UserRecord(phone_e164=sender_phone, role="TENANT", is_active=True)

    def fake_handle_utility_debt_task(sender_phone: str, message_body: str, settings, property_hint=None):
        assert property_hint == "navidad"
        return UtilityAgentResult(
            reply=(
                "Para Departamento Navidad, la cuenta ENEL 312091-0 aparece "
                "con deuda actual de $16.563. Documento asociado: 40016971491."
            )
        )

    monkeypatch.setattr("app.main.send_text_reply", fake_send_text_reply)
    monkeypatch.setattr("app.main.get_user_by_phone", fake_get_user_by_phone)
    monkeypatch.setattr("app.main.handle_utility_debt_task", fake_handle_utility_debt_task)

    with create_client() as client:
        response = client.post(
            "/webhook",
            json={
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "messages": [
                                        {
                                            "from": "56996096419",
                                            "id": "wamid-4",
                                            "type": "text",
                                            "text": {
                                                "body": (
                                                    "quiero saber si mi departamento de navidad "
                                                    "tiene deuda en la cuenta de luz"
                                                )
                                            },
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ]
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert sent_messages == [
        (
            "56996096419",
            (
                "Para Departamento Navidad, la cuenta ENEL 312091-0 aparece "
                "con deuda actual de $16.563. Documento asociado: 40016971491."
            ),
        )
    ]


def test_property_list_question_returns_registered_properties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_messages: list[tuple[str, str]] = []

    async def fake_send_text_reply(sender_phone: str, settings, reply_body: str = "hello world") -> None:
        sent_messages.append((sender_phone, reply_body))

    def fake_get_user_by_phone(sender_phone: str, settings) -> Optional[UserRecord]:
        return UserRecord(phone_e164=sender_phone, role="LANDLORD", is_active=True)

    def fake_list_active_properties_for_user(sender_phone: str, settings) -> list[PropertyRecord]:
        return [
            PropertyRecord(
                property_id="property-1",
                name="Depto Centro",
                code="PROP-001",
                street_address="Av. Providencia 1234",
                commune="Providencia",
            )
        ]

    monkeypatch.setattr("app.main.send_text_reply", fake_send_text_reply)
    monkeypatch.setattr("app.main.get_user_by_phone", fake_get_user_by_phone)
    monkeypatch.setattr(
        "app.main.list_active_properties_for_user",
        fake_list_active_properties_for_user,
    )

    with create_client() as client:
        response = client.post(
            "/webhook",
            json={
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "messages": [
                                        {
                                            "from": "56996096419",
                                            "id": "wamid-5",
                                            "type": "text",
                                            "text": {
                                                "body": (
                                                    "cuantos departamentos mios "
                                                    "tienes registrados?"
                                                )
                                            },
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ]
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert sent_messages == [
        ("56996096419", "Tengo 1 departamento registrado: Depto Centro.")
    ]


def test_webhook_non_message_event_returns_200() -> None:
    with create_client() as client:
        response = client.post(
            "/webhook",
            json={"entry": [{"changes": [{"value": {"statuses": [{"id": "1"}]}}]}]},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_webhook_partial_payload_returns_200() -> None:
    with create_client() as client:
        response = client.post("/webhook", json={"entry": [{"changes": [None]}]})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
