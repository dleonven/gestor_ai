from dataclasses import dataclass
from typing import Optional

from app.config import Settings


ROLE_TENANT = "TENANT"
ROLE_LANDLORD = "LANDLORD"


@dataclass(frozen=True)
class UserRecord:
    phone_e164: str
    role: str
    is_active: bool


def get_user_by_phone(phone_e164: str, settings: Settings) -> Optional[UserRecord]:
    import psycopg

    query = """
        select phone_e164, role, is_active
        from public.users
        where phone_e164 = %s
        limit 1
    """
    with psycopg.connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (phone_e164,))
            row = cursor.fetchone()

    if row is None:
        return None

    return UserRecord(phone_e164=row[0], role=row[1], is_active=row[2])
