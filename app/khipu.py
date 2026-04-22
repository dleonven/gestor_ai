from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

import httpx

from app.config import Settings


@dataclass(frozen=True)
class EnelDebt:
    currency: str
    due_date: Optional[date]
    total_amount: Optional[int]


@dataclass(frozen=True)
class EnelLastPayment:
    paid_at: Optional[date]
    amount: Optional[int]


@dataclass(frozen=True)
class EnelDebtStatus:
    client_identifier: str
    address: Optional[str]
    debt: Optional[EnelDebt]
    last_payment: Optional[EnelLastPayment]
    raw_response: dict[str, Any]


class KhipuError(RuntimeError):
    pass


def fetch_enel_debt_status(
    client_identifier: str,
    settings: Settings,
    *,
    timeout_seconds: float = 15.0,
) -> EnelDebtStatus:
    if not settings.khipu_bearer_token:
        raise KhipuError("KHIPU_BEARER_TOKEN is not configured")

    response = httpx.post(
        f"{settings.khipu_base_url}/v1/cl/services/enel.cl/debt-status-by-client-identifier",
        headers={
            "Authorization": f"Bearer {settings.khipu_bearer_token}",
            "Content-Type": "application/json",
        },
        json={"RequestData": {"ClientIdentifier": client_identifier}},
        timeout=timeout_seconds,
    )
    response.raise_for_status()

    payload = response.json()
    debt_status_payload = _extract_debt_status_payload(payload)
    debt_payload = debt_status_payload.get("Debt")
    last_payment_payload = debt_status_payload.get("LastPayment")

    return EnelDebtStatus(
        client_identifier=str(
            debt_status_payload.get("ClientIdentifier", client_identifier)
        ),
        address=_as_optional_str(debt_status_payload.get("Address")),
        debt=_parse_debt(debt_payload),
        last_payment=_parse_last_payment(last_payment_payload),
        raw_response=payload,
    )


def _extract_debt_status_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise KhipuError("Unexpected Khipu response type")

    if isinstance(payload.get("DebtStatus"), dict):
        return payload["DebtStatus"]

    response_data = payload.get("ResponseData")
    if isinstance(response_data, dict) and isinstance(response_data.get("DebtStatus"), dict):
        return response_data["DebtStatus"]

    raise KhipuError("Khipu response did not include DebtStatus")


def _parse_debt(payload: Any) -> Optional[EnelDebt]:
    if not isinstance(payload, dict):
        return None

    return EnelDebt(
        currency=_as_optional_str(payload.get("Currency")) or "CLP",
        due_date=_parse_date(payload.get("DueDate")),
        total_amount=_parse_int(payload.get("TotalAmount")),
    )


def _parse_last_payment(payload: Any) -> Optional[EnelLastPayment]:
    if not isinstance(payload, dict):
        return None

    return EnelLastPayment(
        paid_at=_parse_date(payload.get("Date")),
        amount=_parse_int(payload.get("Amount")),
    )


def _as_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(str(value))


def _parse_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)
