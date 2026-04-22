from dataclasses import dataclass
from typing import Optional

from app.config import Settings


@dataclass(frozen=True)
class RentStatusRecord:
    property_name: str
    due_date: str
    charge_status: str
    amount_due: float
    amount_paid: float
    currency: str


@dataclass(frozen=True)
class UtilityAccountRecord:
    property_name: str
    provider_name: str
    utility_type: str
    service_account_number: str


def get_latest_rent_status_for_landlord(
    landlord_phone: str, settings: Settings
) -> Optional[RentStatusRecord]:
    import psycopg

    query = """
        select
            p.name,
            rc.due_date::text,
            rc.charge_status,
            rc.amount_due::float8,
            rc.amount_paid::float8,
            t.rent_currency
        from public.users u
        join public.tenancies t on t.landlord_user_id = u.id
        join public.properties p on p.id = t.property_id
        join public.rent_charges rc on rc.tenancy_id = t.id
        where u.phone_e164 = %s
          and u.role = 'LANDLORD'
          and u.is_active = true
          and t.contract_status = 'ACTIVE'
        order by rc.due_date desc
        limit 1
    """

    with psycopg.connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (landlord_phone,))
            row = cursor.fetchone()

    if row is None:
        return None

    return RentStatusRecord(
        property_name=row[0],
        due_date=row[1],
        charge_status=row[2],
        amount_due=row[3],
        amount_paid=row[4],
        currency=row[5],
    )


def get_enel_electricity_account_for_user(
    phone_e164: str, settings: Settings, property_hint: Optional[str] = None
) -> Optional[UtilityAccountRecord]:
    import psycopg

    property_filter = ""
    params: list[str] = [phone_e164]
    if property_hint:
        property_filter = """
          and (
            p.name ilike %s
            or coalesce(p.code, '') ilike %s
            or coalesce(p.street_address, '') ilike %s
            or coalesce(p.commune, '') ilike %s
          )
        """
        pattern = f"%{property_hint}%"
        params.extend([pattern, pattern, pattern, pattern])

    query = f"""
        select distinct
            p.name,
            ua.provider_name,
            ua.utility_type,
            ua.service_account_number
        from public.users u
        join public.tenancies t
          on (
            t.tenant_user_id = u.id
            or t.landlord_user_id = u.id
          )
        join public.properties p on p.id = t.property_id
        join public.utility_accounts ua on ua.property_id = p.id
        where u.phone_e164 = %s
          and u.is_active = true
          and t.contract_status = 'ACTIVE'
          and ua.is_active = true
          and ua.utility_type = 'ELECTRICITY'
          and ua.provider_name ilike 'ENEL'
          and ua.service_account_number is not null
          {property_filter}
        order by p.name
        limit 2
    """

    with psycopg.connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

    if len(rows) != 1:
        return None

    row = rows[0]
    return UtilityAccountRecord(
        property_name=row[0],
        provider_name=row[1],
        utility_type=row[2],
        service_account_number=row[3],
    )
