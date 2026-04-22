import json
import sys

from app.config import Settings
from app.khipu import KhipuError, fetch_enel_debt_status


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: ./.venv/bin/python scripts/test_khipu_enel.py <CLIENT_IDENTIFIER>")
        return 1

    settings = Settings.from_env()
    client_identifier = sys.argv[1]

    try:
        debt_status = fetch_enel_debt_status(client_identifier, settings)
    except KhipuError as exc:
        print(f"Khipu error: {exc}")
        return 2
    except Exception as exc:
        print(f"Request failed: {exc}")
        return 3

    print(
        json.dumps(
            {
                "client_identifier": debt_status.client_identifier,
                "address": debt_status.address,
                "debt": None
                if debt_status.debt is None
                else {
                    "currency": debt_status.debt.currency,
                    "due_date": None
                    if debt_status.debt.due_date is None
                    else debt_status.debt.due_date.isoformat(),
                    "total_amount": debt_status.debt.total_amount,
                },
                "last_payment": None
                if debt_status.last_payment is None
                else {
                    "paid_at": None
                    if debt_status.last_payment.paid_at is None
                    else debt_status.last_payment.paid_at.isoformat(),
                    "amount": debt_status.last_payment.amount,
                },
                "raw_response": debt_status.raw_response,
            },
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
