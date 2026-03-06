import os
from collections.abc import Generator
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from app.users_repo import UserRecord


@pytest.fixture(autouse=True)
def env_vars() -> Generator[None, None, None]:
    os.environ["VERIFY_TOKEN"] = "test-verify-token"
    os.environ["WHATSAPP_TOKEN"] = "test-whatsapp-token"
    os.environ["PHONE_NUMBER_ID"] = "123456789"
    os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/postgres"
    os.environ["GRAPH_API_VERSION"] = "v19.0"
    os.environ["PORT"] = "3000"
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
        (UserRecord(phone_e164="56912345678", role="TENANT", is_active=True), "hello arrendatario"),
        (UserRecord(phone_e164="56912345678", role="LANDLORD", is_active=True), "hello arrendador"),
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
