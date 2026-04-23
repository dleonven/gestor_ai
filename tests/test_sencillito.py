import httpx
import pytest

from app.sencillito import (
    CONSULTA_SALDO_PATH,
    PROVIDER_AGUAS_ANDINAS,
    PROVIDER_ENEL,
    SencillitoError,
    fetch_sencillito_debt_status,
    fetch_sencillito_enel_debt_status,
    get_sencillito_provider_config,
    parse_sencillito_debt_status,
    parse_sencillito_enel_debt_status,
    UTILITY_WATER,
)


def sample_payload() -> dict:
    return {
        "clientNumber": "3120910",
        "errorMessage": None,
        "invoices": [
            {
                "accountReference": "312091-0",
                "amount": "16563",
                "authenticationCode": "775626280",
                "convenioId": "516",
                "dateTime": "20260421151254",
                "fields": [
                    {"key": "order", "label": "order", "value": "1"},
                    {"key": "field_01", "label": "DEUDA", "value": "DEUDA ACTUAL"},
                    {"key": "field_03", "label": "DOCUMENTO", "value": "40016971491"},
                    {"key": "amount", "label": "amount", "value": "16563"},
                ],
                "industriaId": "13",
                "order": "1",
                "orderItemId": "0",
                "productTypeName": "Cuentas",
                "utilityName": "ENEL",
                "utilityNumber": "2018",
                "utilityVersion": "1",
            }
        ],
        "sessionKey": "scom-9fda43a8-882b-4603-9c8f-338bbed7ec35",
        "shortUtilityName": "Enel",
        "totalAmount": "16563",
        "totalReccords": "1",
        "utilityNumber": "2018",
    }


def build_response(status_code: int, payload: dict) -> httpx.Response:
    request = httpx.Request(
        "GET",
        f"https://sencillito.com{CONSULTA_SALDO_PATH}",
    )
    return httpx.Response(status_code=status_code, json=payload, request=request)


def test_parse_sencillito_enel_debt_status_normalizes_payload() -> None:
    result = parse_sencillito_enel_debt_status(sample_payload(), "312091-0")

    assert result.client_number == "3120910"
    assert result.account_reference == "312091-0"
    assert result.utility_name == "ENEL"
    assert result.short_utility_name == "Enel"
    assert result.total_amount == 16563
    assert result.total_records == 1
    assert result.session_key == "scom-9fda43a8-882b-4603-9c8f-338bbed7ec35"
    assert len(result.invoices) == 1
    assert result.invoices[0].amount == 16563
    assert result.invoices[0].document_number == "40016971491"
    assert result.invoices[0].label == "DEUDA ACTUAL"
    assert result.invoices[0].authentication_code == "775626280"


def test_fetch_sencillito_enel_debt_status_builds_expected_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_get(
        url: str, *, params: dict, headers: dict, timeout: float
    ) -> httpx.Response:
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return build_response(200, sample_payload())

    monkeypatch.setattr("app.sencillito.httpx.get", fake_get)

    result = fetch_sencillito_enel_debt_status("312091-0")

    assert captured == {
        "url": "https://sencillito.com/o/portal-publico/consulta-saldo/",
        "params": {
            "accountReference": "312091-0",
            "utilityNumber": "2018",
            "utilityVersion": "1",
            "industriaId": "13",
            "productTypeId": "null",
            "userId": "61610",
            "session_key": "null",
        },
        "headers": {
            "Accept": "application/json, text/plain, */*",
            "Referer": get_sencillito_provider_config("ELECTRICITY", PROVIDER_ENEL).payment_url,
            "User-Agent": "Mozilla/5.0",
        },
        "timeout": 15.0,
    }
    assert result.total_amount == 16563


def test_parse_sencillito_enel_debt_status_rejects_error_message() -> None:
    payload = sample_payload()
    payload["errorMessage"] = "Cliente no encontrado"

    with pytest.raises(SencillitoError, match="Cliente no encontrado"):
        parse_sencillito_enel_debt_status(payload, "312091-0")


def test_parse_sencillito_water_no_debt_response_is_not_treated_as_error() -> None:
    payload = {
        "clientNumber": None,
        "errorMessage": "Cliente no registra deuda",
        "invoices": [],
        "sessionKey": "scom-dddb6600-2f80-4146-8409-8f40e8dec1f4",
        "shortUtilityName": None,
        "statuscode": None,
        "tag": None,
        "totalAmount": "0",
        "totalReccords": "0",
        "utilityNumber": None,
    }

    result = parse_sencillito_debt_status(
        payload,
        "2150389-4",
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_ANDINAS,
    )

    assert result.total_amount == 0
    assert result.total_records == 0
    assert result.invoices == []
    assert result.utility_name == PROVIDER_AGUAS_ANDINAS


def test_fetch_sencillito_water_debt_status_builds_expected_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_get(
        url: str, *, params: dict, headers: dict, timeout: float
    ) -> httpx.Response:
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return build_response(
            200,
            {
                "clientNumber": None,
                "errorMessage": "Cliente no registra deuda",
                "invoices": [],
                "sessionKey": "scom-test",
                "shortUtilityName": None,
                "totalAmount": "0",
                "totalReccords": "0",
                "utilityNumber": None,
            },
        )

    monkeypatch.setattr("app.sencillito.httpx.get", fake_get)

    result = fetch_sencillito_debt_status(
        "2150389-4",
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_ANDINAS,
    )

    assert captured == {
        "url": "https://sencillito.com/o/portal-publico/consulta-saldo/",
        "params": {
            "accountReference": "2150389-4",
            "utilityNumber": "1018",
            "utilityVersion": "1",
            "industriaId": "2",
            "productTypeId": "null",
            "userId": "61610",
            "session_key": "null",
        },
        "headers": {
            "Accept": "application/json, text/plain, */*",
            "Referer": get_sencillito_provider_config(
                UTILITY_WATER, PROVIDER_AGUAS_ANDINAS
            ).payment_url,
            "User-Agent": "Mozilla/5.0",
        },
        "timeout": 15.0,
    }
    assert result.total_amount == 0
