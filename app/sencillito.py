import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional

import httpx


SENCILLITO_BASE_URL = "https://sencillito.com"
CONSULTA_SALDO_PATH = "/o/portal-publico/consulta-saldo/"
DEFAULT_PRODUCT_TYPE_ID = "null"
DEFAULT_USER_ID = "61610"
DEFAULT_SESSION_KEY = "null"
DEFAULT_UTILITY_VERSION = "1"
NO_DEBT_ERROR_MESSAGES = {
    "cliente no registra deuda",
    "no registra deuda",
    "sin deuda",
    "no hay deudas",
}

UTILITY_ELECTRICITY = "ELECTRICITY"
UTILITY_WATER = "WATER"

PROVIDER_ENEL = "ENEL"
PROVIDER_AGUAS_ANDINAS = "Aguas Andinas"
PROVIDER_AGUAS_ANTOFAGASTA = "Aguas Antofagasta"
PROVIDER_AGUAS_ARAUCANIA = "Aguas Araucania"
PROVIDER_AGUAS_CORDILLERA = "Aguas Cordillera"
PROVIDER_AGUAS_DEL_ALTIPLANO = "Aguas del Altiplano"
PROVIDER_AGUAS_DEL_VALLE = "Aguas del Valle"
PROVIDER_AGUAS_DECIMA = "Aguas Décima"
PROVIDER_AGUAS_LAMPA = "Aguas Lampa"
PROVIDER_AGUAS_MAGALLANES = "Aguas Magallanes"
PROVIDER_AGUAS_MANQUEHUE = "Aguas Manquehue"
PROVIDER_AGUAS_METROPOLITANA = "Aguas Metropolitana"
PROVIDER_AGUAS_PIRQUE = "Aguas Pirque"
PROVIDER_AGUAS_SAN_PEDRO = "Aguas San Pedro"
PROVIDER_AGUAS_SANTIAGO_PONIENTE = "Aguas Santiago Poniente"
PROVIDER_BIODIVERSA = "Biodiversa"
PROVIDER_ESSBIO = "Essbio"
PROVIDER_ESVAL = "Esval"
PROVIDER_NUEVA_ATACAMA = "Nueva Atacama"
PROVIDER_NUEVO_SUR = "Nuevo Sur"
PROVIDER_SEPRA = "Sepra"
PROVIDER_SMAPA = "Smapa"
PROVIDER_SURALIS = "Suralis (Essal)"


@dataclass(frozen=True)
class SencillitoProviderConfig:
    utility_type: str
    provider_name: str
    utility_number: str
    industria_id: str
    convenio_id: str
    utility_version: str = DEFAULT_UTILITY_VERSION
    product_type_id: str = DEFAULT_PRODUCT_TYPE_ID
    user_id: str = DEFAULT_USER_ID
    session_key: str = DEFAULT_SESSION_KEY
    input_hint: Optional[str] = None

    @property
    def payment_url(self) -> str:
        return (
            f"{SENCILLITO_BASE_URL}/pagos-de-la-factura"
            f"?convenioId={self.convenio_id}&industriaId={self.industria_id}"
        )


@dataclass(frozen=True)
class SencillitoInvoice:
    account_reference: str
    amount: int
    document_number: Optional[str]
    label: Optional[str]
    authentication_code: Optional[str]


@dataclass(frozen=True)
class SencillitoDebtStatus:
    client_number: str
    account_reference: str
    utility_name: str
    short_utility_name: Optional[str]
    total_amount: int
    total_records: int
    invoices: list[SencillitoInvoice]
    session_key: Optional[str]
    raw_response: dict[str, Any]


SencillitoEnelDebtStatus = SencillitoDebtStatus


class SencillitoError(RuntimeError):
    pass


def normalize_provider_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    collapsed = re.sub(r"[^a-z0-9]+", "_", ascii_only.lower()).strip("_")
    return collapsed


SENCILLITO_PROVIDER_CONFIGS: tuple[SencillitoProviderConfig, ...] = (
    SencillitoProviderConfig(
        utility_type=UTILITY_ELECTRICITY,
        provider_name=PROVIDER_ENEL,
        utility_number="2018",
        industria_id="13",
        convenio_id="516",
        input_hint="N° de cliente",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_ANDINAS,
        utility_number="1018",
        industria_id="2",
        convenio_id="501",
        input_hint="Número de cliente",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_ANTOFAGASTA,
        utility_number="1232",
        industria_id="2",
        convenio_id="509",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_ARAUCANIA,
        utility_number="1064",
        industria_id="2",
        convenio_id="502",
        input_hint="Número de servicio",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_CORDILLERA,
        utility_number="1128",
        industria_id="2",
        convenio_id="503",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_DEL_ALTIPLANO,
        utility_number="1164",
        industria_id="2",
        convenio_id="505",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_DEL_VALLE,
        utility_number="1222",
        industria_id="2",
        convenio_id="508",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_DECIMA,
        utility_number="1424",
        industria_id="2",
        convenio_id="3901",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_LAMPA,
        utility_number="1364",
        industria_id="2",
        convenio_id="2406",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_MAGALLANES,
        utility_number="1264",
        industria_id="2",
        convenio_id="510",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_MANQUEHUE,
        utility_number="1188",
        industria_id="2",
        convenio_id="506",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_METROPOLITANA,
        utility_number="1354",
        industria_id="2",
        convenio_id="2405",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_PIRQUE,
        utility_number="1214",
        industria_id="2",
        convenio_id="5601",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_SAN_PEDRO,
        utility_number="1191",
        industria_id="2",
        convenio_id="507",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_AGUAS_SANTIAGO_PONIENTE,
        utility_number="1321",
        industria_id="2",
        convenio_id="512",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_BIODIVERSA,
        utility_number="1339",
        industria_id="2",
        convenio_id="3303",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_ESSBIO,
        utility_number="1289",
        industria_id="2",
        convenio_id="3301",
        input_hint="ID servicio",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_ESVAL,
        utility_number="1155",
        industria_id="2",
        convenio_id="504",
        input_hint="Número cliente",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_NUEVA_ATACAMA,
        utility_number="1404",
        industria_id="2",
        convenio_id="513",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_NUEVO_SUR,
        utility_number="1319",
        industria_id="2",
        convenio_id="3302",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_SEPRA,
        utility_number="1504",
        industria_id="2",
        convenio_id="515",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_SMAPA,
        utility_number="1041",
        industria_id="2",
        convenio_id="97",
    ),
    SencillitoProviderConfig(
        utility_type=UTILITY_WATER,
        provider_name=PROVIDER_SURALIS,
        utility_number="1091",
        industria_id="2",
        convenio_id="98",
    ),
)

_CONFIGS_BY_KEY = {
    (config.utility_type, normalize_provider_name(config.provider_name)): config
    for config in SENCILLITO_PROVIDER_CONFIGS
}

PROVIDER_ALIASES: dict[str, str] = {
    normalize_provider_name("Suralis"): PROVIDER_SURALIS,
    normalize_provider_name("Essal"): PROVIDER_SURALIS,
    normalize_provider_name("Aguas Metropolitana (Chacabuco/Santiago)"): PROVIDER_AGUAS_METROPOLITANA,
    normalize_provider_name("Sacyr Aguas Metropolitana"): PROVIDER_AGUAS_METROPOLITANA,
}


def fetch_sencillito_debt_status(
    account_reference: str,
    *,
    utility_type: str,
    provider_name: str,
    timeout_seconds: float = 15.0,
    base_url: str = SENCILLITO_BASE_URL,
) -> SencillitoDebtStatus:
    config = get_sencillito_provider_config(utility_type, provider_name)
    response = httpx.get(
        f"{base_url}{CONSULTA_SALDO_PATH}",
        params={
            "accountReference": account_reference,
            "utilityNumber": config.utility_number,
            "utilityVersion": config.utility_version,
            "industriaId": config.industria_id,
            "productTypeId": config.product_type_id,
            "userId": config.user_id,
            "session_key": config.session_key,
        },
        headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": config.payment_url,
            "User-Agent": "Mozilla/5.0",
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()

    payload = response.json()
    return parse_sencillito_debt_status(
        payload,
        account_reference,
        utility_type=utility_type,
        provider_name=config.provider_name,
    )


def fetch_sencillito_enel_debt_status(
    account_reference: str,
    *,
    timeout_seconds: float = 15.0,
    base_url: str = SENCILLITO_BASE_URL,
) -> SencillitoEnelDebtStatus:
    return fetch_sencillito_debt_status(
        account_reference,
        utility_type=UTILITY_ELECTRICITY,
        provider_name=PROVIDER_ENEL,
        timeout_seconds=timeout_seconds,
        base_url=base_url,
    )


def parse_sencillito_debt_status(
    payload: dict[str, Any],
    account_reference: str,
    *,
    utility_type: str,
    provider_name: str,
) -> SencillitoDebtStatus:
    if not isinstance(payload, dict):
        raise SencillitoError("Unexpected Sencillito response type")

    invoices_payload = payload.get("invoices")
    if invoices_payload is None:
        invoices_payload = []
    if not isinstance(invoices_payload, list):
        raise SencillitoError("Sencillito response did not include invoices")

    total_amount = _parse_int(payload.get("totalAmount"))
    if total_amount is None:
        total_amount = 0

    error_message = _as_optional_str(payload.get("errorMessage"))
    if error_message and not _is_no_debt_message(error_message, total_amount, invoices_payload):
        raise SencillitoError(str(error_message))

    invoices = [_parse_invoice(invoice) for invoice in invoices_payload]
    if total_amount == 0 and invoices:
        total_amount = sum(invoice.amount for invoice in invoices)

    utility_name = provider_name
    if invoices_payload:
        utility_name = _as_optional_str(invoices_payload[0].get("utilityName")) or provider_name
    elif payload.get("shortUtilityName"):
        utility_name = _as_optional_str(payload.get("shortUtilityName")) or provider_name

    return SencillitoDebtStatus(
        client_number=_as_str(payload.get("clientNumber")),
        account_reference=account_reference,
        utility_name=utility_name,
        short_utility_name=_as_optional_str(payload.get("shortUtilityName")),
        total_amount=total_amount,
        total_records=_parse_int(payload.get("totalReccords"))
        or _parse_int(payload.get("totalRecords"))
        or len(invoices),
        invoices=invoices,
        session_key=_as_optional_str(payload.get("sessionKey")),
        raw_response=payload,
    )


def parse_sencillito_enel_debt_status(
    payload: dict[str, Any], account_reference: str
) -> SencillitoEnelDebtStatus:
    return parse_sencillito_debt_status(
        payload,
        account_reference,
        utility_type=UTILITY_ELECTRICITY,
        provider_name=PROVIDER_ENEL,
    )


def get_sencillito_provider_config(
    utility_type: str, provider_name: str
) -> SencillitoProviderConfig:
    normalized_provider = normalize_provider_name(provider_name)
    canonical_provider = PROVIDER_ALIASES.get(normalized_provider, provider_name)
    config = _CONFIGS_BY_KEY.get(
        (utility_type.upper(), normalize_provider_name(canonical_provider))
    )
    if config is None:
        raise SencillitoError(
            f"Sencillito provider not configured for {utility_type}:{provider_name}"
        )
    return config


def resolve_supported_provider_name(
    text: str, utility_type: str
) -> Optional[str]:
    normalized_text = normalize_provider_name(text)
    for config in SENCILLITO_PROVIDER_CONFIGS:
        if config.utility_type != utility_type.upper():
            continue
        provider_name = config.provider_name
        candidates = {
            normalize_provider_name(provider_name),
            *[
                alias
                for alias, canonical in PROVIDER_ALIASES.items()
                if canonical == provider_name
            ],
        }
        for candidate in candidates:
            if candidate and candidate in normalized_text:
                return provider_name
    return None


def get_supported_provider_names(utility_type: str) -> list[str]:
    return [
        config.provider_name
        for config in SENCILLITO_PROVIDER_CONFIGS
        if config.utility_type == utility_type.upper()
    ]


def _is_no_debt_message(
    error_message: str, total_amount: int, invoices_payload: list[Any]
) -> bool:
    normalized_message = normalize_provider_name(error_message).replace("_", " ")
    return (
        total_amount == 0
        and not invoices_payload
        and any(candidate in normalized_message for candidate in NO_DEBT_ERROR_MESSAGES)
    )


def _parse_invoice(payload: Any) -> SencillitoInvoice:
    if not isinstance(payload, dict):
        raise SencillitoError("Unexpected invoice response type")

    fields = payload.get("fields")
    field_map: dict[str, str] = {}
    if isinstance(fields, list):
        field_map = {
            str(field.get("key")): str(field.get("value"))
            for field in fields
            if isinstance(field, dict) and field.get("key") is not None
        }

    amount = _parse_int(payload.get("amount")) or _parse_int(field_map.get("amount"))
    if amount is None:
        raise SencillitoError("Sencillito invoice did not include amount")

    return SencillitoInvoice(
        account_reference=_as_str(payload.get("accountReference")),
        amount=amount,
        document_number=_as_optional_str(field_map.get("field_03")),
        label=_as_optional_str(field_map.get("field_01")),
        authentication_code=_as_optional_str(payload.get("authenticationCode")),
    )


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _as_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _parse_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)
