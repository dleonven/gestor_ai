from datetime import date

import httpx
import pytest

from app.config import Settings
from app.khipu import KhipuError, fetch_enel_debt_status


def build_settings() -> Settings:
    return Settings(
        verify_token="verify",
        whatsapp_token="wa-token",
        phone_number_id="999888777",
        database_url="postgresql://postgres:postgres@localhost:5432/postgres",
        khipu_bearer_token="khipu-jwt",
        khipu_base_url="https://api.khipu.com",
        graph_api_version="v19.0",
        port=3000,
    )


def build_response(status_code: int, payload: dict) -> httpx.Response:
    request = httpx.Request(
        "POST",
        "https://api.khipu.com/v1/cl/services/enel.cl/debt-status-by-client-identifier",
    )
    return httpx.Response(status_code=status_code, json=payload, request=request)


def test_fetch_enel_debt_status_builds_expected_request(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url: str, *, headers: dict, json: dict, timeout: float) -> httpx.Response:
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return build_response(
            200,
            {
                "ResponseData": {
                    "DebtStatus": {
                        "ClientIdentifier": "1234567-8",
                        "Address": "Av. Siempre Viva 123",
                        "Debt": {
                            "Currency": "CLP",
                            "DueDate": "2026-04-15",
                            "TotalAmount": 24560,
                        },
                        "LastPayment": {
                            "Date": "2026-03-10",
                            "Amount": 21890,
                        },
                    }
                }
            },
        )

    monkeypatch.setattr("app.khipu.httpx.post", fake_post)

    result = fetch_enel_debt_status("1234567-8", build_settings())

    assert captured == {
        "url": "https://api.khipu.com/v1/cl/services/enel.cl/debt-status-by-client-identifier",
        "headers": {
            "Authorization": "Bearer khipu-jwt",
            "Content-Type": "application/json",
        },
        "json": {"RequestData": {"ClientIdentifier": "1234567-8"}},
        "timeout": 15.0,
    }
    assert result.client_identifier == "1234567-8"
    assert result.address == "Av. Siempre Viva 123"
    assert result.debt is not None
    assert result.debt.currency == "CLP"
    assert result.debt.due_date == date(2026, 4, 15)
    assert result.debt.total_amount == 24560
    assert result.last_payment is not None
    assert result.last_payment.paid_at == date(2026, 3, 10)
    assert result.last_payment.amount == 21890


def test_fetch_enel_debt_status_requires_bearer_token() -> None:
    settings = Settings(
        verify_token="verify",
        whatsapp_token="wa-token",
        phone_number_id="999888777",
        database_url="postgresql://postgres:postgres@localhost:5432/postgres",
        khipu_bearer_token=None,
        graph_api_version="v19.0",
        port=3000,
    )

    with pytest.raises(KhipuError, match="KHIPU_BEARER_TOKEN is not configured"):
        fetch_enel_debt_status("1234567-8", settings)


def test_fetch_enel_debt_status_rejects_missing_debt_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, *, headers: dict, json: dict, timeout: float) -> httpx.Response:
        return build_response(200, {"ResponseData": {}})

    monkeypatch.setattr("app.khipu.httpx.post", fake_post)

    with pytest.raises(KhipuError, match="DebtStatus"):
        fetch_enel_debt_status("1234567-8", build_settings())
