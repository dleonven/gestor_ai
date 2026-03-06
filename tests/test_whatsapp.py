import asyncio

import httpx

from app.config import Settings
from app.whatsapp import send_text_reply


def test_send_text_reply_builds_expected_graph_api_request(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_post(self, url: str, headers: dict, json: dict):  # type: ignore[no-untyped-def]
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return httpx.Response(status_code=200, json={"messages": [{"id": "wamid.1"}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    settings = Settings(
        verify_token="verify",
        whatsapp_token="wa-token",
        phone_number_id="999888777",
        database_url="postgresql://postgres:postgres@localhost:5432/postgres",
        graph_api_version="v19.0",
        port=3000,
    )

    asyncio.run(send_text_reply("56912345678", settings))

    assert captured["url"] == "https://graph.facebook.com/v19.0/999888777/messages"
    assert captured["headers"] == {
        "Authorization": "Bearer wa-token",
        "Content-Type": "application/json",
    }
    assert captured["json"] == {
        "messaging_product": "whatsapp",
        "to": "56912345678",
        "type": "text",
        "text": {"body": "hello world"},
    }
