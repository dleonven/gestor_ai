from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import Settings


STATE_COLLECT_ENEL_CLIENT_ID = "COLLECT_ENEL_CLIENT_ID"


@dataclass(frozen=True)
class ConversationState:
    phone_e164: str
    state_type: str
    payload: dict[str, Any]


def get_active_conversation_state(
    phone_e164: str, settings: Settings
) -> Optional[ConversationState]:
    import psycopg
    from psycopg.rows import dict_row

    query = """
        select phone_e164, state_type, payload
        from public.conversation_states
        where phone_e164 = %s
          and expires_at > now()
        order by updated_at desc
        limit 1
    """

    with psycopg.connect(settings.database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (phone_e164,))
            row = cursor.fetchone()

    if row is None:
        return None

    return ConversationState(
        phone_e164=row["phone_e164"],
        state_type=row["state_type"],
        payload=dict(row["payload"] or {}),
    )


def save_conversation_state(
    phone_e164: str,
    state_type: str,
    payload: dict[str, Any],
    settings: Settings,
) -> None:
    import psycopg
    from psycopg.types.json import Jsonb

    query = """
        insert into public.conversation_states (
            phone_e164,
            state_type,
            payload,
            expires_at
        )
        values (%s, %s, %s, now() + interval '30 minutes')
        on conflict (phone_e164)
        do update set
            state_type = excluded.state_type,
            payload = excluded.payload,
            expires_at = excluded.expires_at,
            updated_at = now()
    """

    with psycopg.connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (phone_e164, state_type, Jsonb(payload)))
        connection.commit()


def clear_conversation_state(phone_e164: str, settings: Settings) -> None:
    import psycopg

    query = "delete from public.conversation_states where phone_e164 = %s"
    with psycopg.connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (phone_e164,))
        connection.commit()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
