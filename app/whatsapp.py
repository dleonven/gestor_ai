import logging

import httpx

from app.config import Settings


LOGGER = logging.getLogger("whatsapp_bot.whatsapp")
HELLO_WORLD_REPLY = "hello world"


async def send_text_reply(
    sender_phone: str, settings: Settings, reply_body: str = HELLO_WORLD_REPLY
) -> None:
    url = (
        f"https://graph.facebook.com/"
        f"{settings.graph_api_version}/{settings.phone_number_id}/messages"
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": sender_phone,
        "type": "text",
        "text": {"body": reply_body},
    }
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.is_success:
            LOGGER.info(
                "reply_send_result status=success to=%s reply=%s http_status=%s",
                sender_phone,
                reply_body,
                response.status_code,
            )
            return

        LOGGER.error(
            "reply_send_result status=error to=%s reply=%s http_status=%s response=%s",
            sender_phone,
            reply_body,
            response.status_code,
            response.text,
        )
    except httpx.HTTPError as exc:
        LOGGER.exception(
            "reply_send_result status=error to=%s reply=%s error=%s",
            sender_phone,
            reply_body,
            exc,
        )

