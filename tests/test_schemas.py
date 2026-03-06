from app.schemas import extract_incoming_messages


def test_extract_incoming_messages_returns_expected_fields() -> None:
    payload = {
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
    }

    result = extract_incoming_messages(payload)

    assert len(result) == 1
    assert result[0].sender_phone == "56912345678"
    assert result[0].message_id == "wamid-1"
    assert result[0].message_body == "hola"

