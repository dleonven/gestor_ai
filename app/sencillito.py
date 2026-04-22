from dataclasses import dataclass
from typing import Any, Optional

import httpx


SENCILLITO_BASE_URL = "https://sencillito.com"
ENEL_CONSULTA_SALDO_PATH = "/o/portal-publico/consulta-saldo/"
ENEL_REFERER = "https://sencillito.com/pagos-de-la-factura?convenioId=516&industriaId=13"


@dataclass(frozen=True)
class SencillitoInvoice:
    account_reference: str
    amount: int
    document_number: Optional[str]
    label: Optional[str]
    authentication_code: Optional[str]


@dataclass(frozen=True)
class SencillitoEnelDebtStatus:
    client_number: str
    account_reference: str
    utility_name: str
    short_utility_name: Optional[str]
    total_amount: int
    total_records: int
    invoices: list[SencillitoInvoice]
    session_key: Optional[str]
    raw_response: dict[str, Any]


class SencillitoError(RuntimeError):
    pass


def fetch_sencillito_enel_debt_status(
    account_reference: str,
    *,
    timeout_seconds: float = 15.0,
    base_url: str = SENCILLITO_BASE_URL,
) -> SencillitoEnelDebtStatus:
    response = httpx.get(
        f"{base_url}{ENEL_CONSULTA_SALDO_PATH}",
        params={
            "accountReference": account_reference,
            "utilityNumber": "2018",
            "utilityVersion": "1",
            "industriaId": "13",
            "productTypeId": "null",
            "userId": "61610",
            "session_key": "null",
        },
        headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": ENEL_REFERER,
            "User-Agent": "Mozilla/5.0",
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()

    payload = response.json()
    return parse_sencillito_enel_debt_status(payload, account_reference)


def parse_sencillito_enel_debt_status(
    payload: dict[str, Any], account_reference: str
) -> SencillitoEnelDebtStatus:
    if not isinstance(payload, dict):
        raise SencillitoError("Unexpected Sencillito response type")

    error_message = payload.get("errorMessage")
    if error_message:
        raise SencillitoError(str(error_message))

    invoices_payload = payload.get("invoices")
    if not isinstance(invoices_payload, list):
        raise SencillitoError("Sencillito response did not include invoices")

    invoices = [_parse_invoice(invoice) for invoice in invoices_payload]
    total_amount = _parse_int(payload.get("totalAmount"))

    if total_amount is None:
        total_amount = sum(invoice.amount for invoice in invoices)

    return SencillitoEnelDebtStatus(
        client_number=_as_str(payload.get("clientNumber")),
        account_reference=account_reference,
        utility_name=_as_str(payload.get("utilityNumber"))
        if not invoices
        else invoices_payload[0].get("utilityName", "ENEL"),
        short_utility_name=_as_optional_str(payload.get("shortUtilityName")),
        total_amount=total_amount,
        total_records=_parse_int(payload.get("totalReccords")) or len(invoices),
        invoices=invoices,
        session_key=_as_optional_str(payload.get("sessionKey")),
        raw_response=payload,
    )


def _parse_invoice(payload: Any) -> SencillitoInvoice:
    if not isinstance(payload, dict):
        raise SencillitoError("Unexpected invoice response type")

    fields = payload.get("fields")
    field_map: dict[str, str] = {}
    if isinstance(fields, list):
        field_map = {
            str(field.get("key")): str(field.get("value"))
            for field in fields
            if isinstance(field, dict) and field.get("key") is not None
        }

    amount = _parse_int(payload.get("amount")) or _parse_int(field_map.get("amount"))
    if amount is None:
        raise SencillitoError("Sencillito invoice did not include amount")

    return SencillitoInvoice(
        account_reference=_as_str(payload.get("accountReference")),
        amount=amount,
        document_number=_as_optional_str(field_map.get("field_03")),
        label=_as_optional_str(field_map.get("field_01")),
        authentication_code=_as_optional_str(payload.get("authenticationCode")),
    )


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _as_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _parse_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)
