import json
import sys

from app.sencillito import SencillitoError, fetch_sencillito_enel_debt_status


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: ./.venv/bin/python scripts/test_sencillito_enel.py <ACCOUNT_REFERENCE>")
        return 1

    account_reference = sys.argv[1]

    try:
        debt_status = fetch_sencillito_enel_debt_status(account_reference)
    except SencillitoError as exc:
        print(f"Sencillito error: {exc}")
        return 2
    except Exception as exc:
        print(f"Request failed: {exc}")
        return 3

    print(
        json.dumps(
            {
                "account_reference": debt_status.account_reference,
                "client_number": debt_status.client_number,
                "utility_name": debt_status.utility_name,
                "short_utility_name": debt_status.short_utility_name,
                "total_amount": debt_status.total_amount,
                "total_records": debt_status.total_records,
                "session_key": debt_status.session_key,
                "invoices": [
                    {
                        "account_reference": invoice.account_reference,
                        "amount": invoice.amount,
                        "document_number": invoice.document_number,
                        "label": invoice.label,
                        "authentication_code": invoice.authentication_code,
                    }
                    for invoice in debt_status.invoices
                ],
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
