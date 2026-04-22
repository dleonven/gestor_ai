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
    property_id: str
    property_name: str
    provider_name: str
    utility_type: str
    service_account_number: Optional[str]


@dataclass(frozen=True)
class PropertyRecord:
    property_id: str
    name: str
    code: Optional[str]
    street_address: Optional[str]
    commune: Optional[str]


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
            p.id::text,
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
        property_id=row[0],
        property_name=row[1],
        provider_name=row[2],
        utility_type=row[3],
        service_account_number=row[4],
    )


def list_active_properties_for_user(
    phone_e164: str, settings: Settings
) -> list[PropertyRecord]:
    import psycopg

    query = """
        select distinct
            p.id::text,
            p.name,
            p.code,
            p.street_address,
            p.commune
        from public.users u
        join public.tenancies t
          on (
            t.tenant_user_id = u.id
            or t.landlord_user_id = u.id
          )
        join public.properties p on p.id = t.property_id
        where u.phone_e164 = %s
          and u.is_active = true
          and t.contract_status = 'ACTIVE'
          and p.is_active = true
        order by p.name
    """

    with psycopg.connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (phone_e164,))
            rows = cursor.fetchall()

    return [
        PropertyRecord(
            property_id=row[0],
            name=row[1],
            code=row[2],
            street_address=row[3],
            commune=row[4],
        )
        for row in rows
    ]


def resolve_active_property_for_user(
    phone_e164: str,
    settings: Settings,
    property_hint: Optional[str] = None,
) -> Optional[PropertyRecord]:
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
            p.id::text,
            p.name,
            p.code,
            p.street_address,
            p.commune
        from public.users u
        join public.tenancies t
          on (
            t.tenant_user_id = u.id
            or t.landlord_user_id = u.id
          )
        join public.properties p on p.id = t.property_id
        where u.phone_e164 = %s
          and u.is_active = true
          and t.contract_status = 'ACTIVE'
          and p.is_active = true
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
    return PropertyRecord(
        property_id=row[0],
        name=row[1],
        code=row[2],
        street_address=row[3],
        commune=row[4],
    )


def get_enel_electricity_account_for_property(
    property_id: str, settings: Settings
) -> Optional[UtilityAccountRecord]:
    import psycopg

    query = """
        select
            p.id::text,
            p.name,
            ua.provider_name,
            ua.utility_type,
            ua.service_account_number
        from public.properties p
        left join public.utility_accounts ua
          on ua.property_id = p.id
          and ua.utility_type = 'ELECTRICITY'
          and ua.provider_name ilike 'ENEL'
          and ua.is_active = true
        where p.id = %s
          and p.is_active = true
        order by ua.updated_at desc nulls last
        limit 1
    """

    with psycopg.connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (property_id,))
            row = cursor.fetchone()

    if row is None:
        return None

    return UtilityAccountRecord(
        property_id=row[0],
        property_name=row[1],
        provider_name=row[2] or "ENEL",
        utility_type=row[3] or "ELECTRICITY",
        service_account_number=row[4],
    )


def save_enel_electricity_client_number(
    property_id: str, client_identifier: str, settings: Settings
) -> UtilityAccountRecord:
    import psycopg

    query = """
        insert into public.utility_accounts (
            property_id,
            provider_name,
            utility_type,
            service_account_number,
            payment_url,
            is_active
        )
        values (
            %s,
            'ENEL',
            'ELECTRICITY',
            %s,
            'https://sencillito.com/pagos-de-la-factura?convenioId=516&industriaId=13',
            true
        )
        on conflict do nothing
    """
    update_query = """
        update public.utility_accounts
        set service_account_number = %s,
            payment_url = 'https://sencillito.com/pagos-de-la-factura?convenioId=516&industriaId=13',
            is_active = true
        where id = (
            select id
            from public.utility_accounts
            where property_id = %s
              and utility_type = 'ELECTRICITY'
              and provider_name ilike 'ENEL'
            order by updated_at desc
            limit 1
        )
    """

    with psycopg.connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (property_id, client_identifier))
            cursor.execute(update_query, (client_identifier, property_id))
        connection.commit()

    account = get_enel_electricity_account_for_property(property_id, settings)
    if account is None:
        raise RuntimeError("Could not save ENEL client identifier")
    return account
