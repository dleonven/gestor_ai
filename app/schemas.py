from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IncomingMessage:
    sender_phone: str
    message_id: str
    message_body: str


def extract_incoming_messages(payload: dict[str, Any]) -> list[IncomingMessage]:
    messages: list[IncomingMessage] = []

    for entry in payload.get("entry", []):
        if not isinstance(entry, dict):
            continue

        for change in entry.get("changes", []):
            if not isinstance(change, dict):
                continue

            value = change.get("value")
            if not isinstance(value, dict):
                continue

            for message in value.get("messages", []):
                if not isinstance(message, dict):
                    continue

                if message.get("type") != "text":
                    continue

                sender_phone = message.get("from")
                message_id = message.get("id")
                text = message.get("text")
                message_body = text.get("body") if isinstance(text, dict) else None

                if not sender_phone or not message_id or not message_body:
                    continue

                messages.append(
                    IncomingMessage(
                        sender_phone=sender_phone,
                        message_id=message_id,
                        message_body=message_body,
                    )
                )

    return messages

