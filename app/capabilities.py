from dataclasses import dataclass

from app.users_repo import ROLE_LANDLORD, ROLE_TENANT


CAPABILITY_CONTRACT_QA = "contract_qa"
CAPABILITY_ENEL_DEBT_LOOKUP = "enel_debt_lookup"
CAPABILITY_PROPERTY_LIST = "property_list"
CAPABILITY_RENT_STATUS = "rent_status"
CAPABILITY_WATER_DEBT_LOOKUP = "water_debt_lookup"


@dataclass(frozen=True)
class CapabilityAction:
    action: str
    label: str


@dataclass(frozen=True)
class Capability:
    capability_id: str
    label: str
    enabled: bool
    roles: tuple[str, ...]
    examples: tuple[str, ...]
    followup_actions: tuple[CapabilityAction, ...] = ()


CAPABILITIES: dict[str, Capability] = {
    CAPABILITY_CONTRACT_QA: Capability(
        capability_id=CAPABILITY_CONTRACT_QA,
        label="responder preguntas del contrato",
        enabled=True,
        roles=(ROLE_TENANT, ROLE_LANDLORD),
        examples=("cuándo puedo dar aviso?", "qué dice el contrato sobre la garantía?"),
    ),
    CAPABILITY_RENT_STATUS: Capability(
        capability_id=CAPABILITY_RENT_STATUS,
        label="revisar estado del arriendo",
        enabled=True,
        roles=(ROLE_LANDLORD,),
        examples=("pagaron el arriendo?", "está pagado el arriendo?"),
    ),
    CAPABILITY_PROPERTY_LIST: Capability(
        capability_id=CAPABILITY_PROPERTY_LIST,
        label="listar departamentos registrados",
        enabled=True,
        roles=(ROLE_TENANT, ROLE_LANDLORD),
        examples=("qué departamentos tengo registrados?",),
    ),
    CAPABILITY_ENEL_DEBT_LOOKUP: Capability(
        capability_id=CAPABILITY_ENEL_DEBT_LOOKUP,
        label="consultar deuda de luz ENEL",
        enabled=True,
        roles=(ROLE_TENANT, ROLE_LANDLORD),
        examples=("cuánto se debe de luz?", "mi depto tiene cuentas de luz pendientes?"),
    ),
    CAPABILITY_WATER_DEBT_LOOKUP: Capability(
        capability_id=CAPABILITY_WATER_DEBT_LOOKUP,
        label="consultar deuda de agua",
        enabled=True,
        roles=(ROLE_TENANT, ROLE_LANDLORD),
        examples=("cuánto se debe de agua?", "mi depto tiene cuentas de agua pendientes?"),
    ),
}


def get_available_actions(capability: str) -> list[dict[str, str]]:
    registry_item = CAPABILITIES.get(capability)
    if registry_item is None or not registry_item.enabled:
        return []

    return [
        {"action": action.action, "label": action.label}
        for action in registry_item.followup_actions
    ]


def get_supported_capabilities_for_role(role: str) -> list[Capability]:
    return [
        capability
        for capability in CAPABILITIES.values()
        if capability.enabled and role in capability.roles
    ]


def build_supported_actions_reply(prefix: str, role: str) -> str:
    actions = "\n".join(
        f"- {capability.label}" for capability in get_supported_capabilities_for_role(role)
    )
    return f"{prefix}\n\nPor ahora puedo ayudarte con:\n{actions}"
