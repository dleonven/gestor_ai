from app.capabilities import (
    CAPABILITY_ENEL_DEBT_LOOKUP,
    build_supported_actions_reply,
    get_available_actions,
    get_supported_capabilities_for_role,
)
from app.users_repo import ROLE_LANDLORD, ROLE_TENANT


def test_enel_debt_lookup_has_no_followup_actions_yet() -> None:
    assert get_available_actions(CAPABILITY_ENEL_DEBT_LOOKUP) == []


def test_supported_actions_reply_lists_current_capabilities() -> None:
    assert build_supported_actions_reply(
        "No pude identificar bien tu solicitud.", ROLE_LANDLORD
    ) == (
        "No pude identificar bien tu solicitud.\n\n"
        "Por ahora puedo ayudarte con:\n"
        "- responder preguntas del contrato\n"
        "- revisar estado del arriendo\n"
        "- listar departamentos registrados\n"
        "- consultar deuda de luz ENEL\n"
        "- consultar deuda de agua"
    )


def test_supported_capabilities_are_role_aware() -> None:
    tenant_labels = [
        capability.label for capability in get_supported_capabilities_for_role(ROLE_TENANT)
    ]
    landlord_labels = [
        capability.label for capability in get_supported_capabilities_for_role(ROLE_LANDLORD)
    ]

    assert "revisar estado del arriendo" not in tenant_labels
    assert "revisar estado del arriendo" in landlord_labels
