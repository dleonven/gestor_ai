import httpx

from app.grounded_response import compose_grounded_response_with_llm


def build_response(text: str) -> httpx.Response:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    return httpx.Response(
        status_code=200,
        json={"output": [{"content": [{"text": text}]}]},
        request=request,
    )


def test_grounded_response_prompt_forbids_unsupported_actions(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(self, url: str, *, headers: dict, json: dict):  # type: ignore[no-untyped-def]
        captured["json"] = json
        return build_response("respuesta")

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    compose_grounded_response_with_llm(
        {"available_actions": []},
        fallback_text="fallback",
        api_key="test-key",
        model="gpt-5",
    )

    payload = captured["json"]
    system_text = payload["input"][0]["content"][0]["text"]
    assert "No ofrezcas acciones" in system_text
    assert "gestionar pagos" in system_text
    assert "available_actions está vacío" in system_text
    assert "Responde solo la pregunta actual" in system_text
