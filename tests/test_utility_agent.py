from app.conversation_state import STATE_COLLECT_UTILITY_ACCOUNT_ID, ConversationState
from app.domain_repo import PropertyRecord, UtilityAccountRecord
from app.sencillito import (
    PROVIDER_AGUAS_ANDINAS,
    SencillitoDebtStatus,
    SencillitoEnelDebtStatus,
    SencillitoInvoice,
    UTILITY_WATER,
)
from app.utility_agent import handle_utility_debt_task


def test_utility_agent_asks_for_missing_enel_client_identifier(monkeypatch) -> None:
    saved_states: list[tuple[str, str, dict]] = []

    monkeypatch.setattr("app.utility_agent.get_active_conversation_state", lambda phone, settings: None)
    monkeypatch.setattr(
        "app.utility_agent.resolve_active_property_for_user",
        lambda phone, settings, property_hint=None: PropertyRecord(
            property_id="property-1",
            name="Depto Centro",
            code="PROP-001",
            street_address="Av. Providencia 1234",
            commune="Providencia",
        ),
    )
    monkeypatch.setattr(
        "app.utility_agent.get_enel_electricity_account_for_property",
        lambda property_id, settings: UtilityAccountRecord(
            property_id="property-1",
            property_name="Depto Centro",
            provider_name="ENEL",
            utility_type="ELECTRICITY",
            service_account_number=None,
        ),
    )
    monkeypatch.setattr(
        "app.utility_agent.save_conversation_state",
        lambda phone, state_type, payload, settings: saved_states.append(
            (phone, state_type, payload)
        ),
    )

    result = handle_utility_debt_task(
        "56996096419", "quiero saber cuanto se debe de luz", object()
    )

    assert "No tengo registrado el número de cliente ENEL" in result.reply
    assert saved_states == [
        (
            "56996096419",
            STATE_COLLECT_UTILITY_ACCOUNT_ID,
            {
                "property_id": "property-1",
                "property_name": "Depto Centro",
                "provider": "ENEL",
                "utility_type": "ELECTRICITY",
            },
        )
    ]


def test_utility_agent_treats_placeholder_enel_client_identifier_as_missing(monkeypatch) -> None:
    saved_states: list[tuple[str, str, dict]] = []

    monkeypatch.setattr("app.utility_agent.get_active_conversation_state", lambda phone, settings: None)
    monkeypatch.setattr(
        "app.utility_agent.resolve_active_property_for_user",
        lambda phone, settings, property_hint=None: PropertyRecord(
            property_id="property-1",
            name="Depto Centro",
            code="PROP-001",
            street_address="Av. Providencia 1234",
            commune="Providencia",
        ),
    )
    monkeypatch.setattr(
        "app.utility_agent.get_enel_electricity_account_for_property",
        lambda property_id, settings: UtilityAccountRecord(
            property_id="property-1",
            property_name="Depto Centro",
            provider_name="ENEL",
            utility_type="ELECTRICITY",
            service_account_number="E-001",
        ),
    )
    monkeypatch.setattr(
        "app.utility_agent.save_conversation_state",
        lambda phone, state_type, payload, settings: saved_states.append(
            (phone, state_type, payload)
        ),
    )

    result = handle_utility_debt_task(
        "56996096419", "tienes cuentas de luz pendientes?", object()
    )

    assert "No tengo registrado el número de cliente ENEL" in result.reply
    assert saved_states[0][1] == STATE_COLLECT_UTILITY_ACCOUNT_ID


def test_utility_agent_collects_client_identifier_and_answers(monkeypatch) -> None:
    cleared: list[str] = []

    monkeypatch.setattr(
        "app.utility_agent.get_active_conversation_state",
        lambda phone, settings: ConversationState(
            phone_e164=phone,
            state_type=STATE_COLLECT_UTILITY_ACCOUNT_ID,
            payload={
                "property_id": "property-1",
                "property_name": "Depto Centro",
                "provider": "ENEL",
                "utility_type": "ELECTRICITY",
            },
        ),
    )
    monkeypatch.setattr(
        "app.utility_agent.save_enel_electricity_client_number",
        lambda property_id, client_identifier, settings: UtilityAccountRecord(
            property_id=property_id,
            property_name="Depto Centro",
            provider_name="ENEL",
            utility_type="ELECTRICITY",
            service_account_number=client_identifier,
        ),
    )
    monkeypatch.setattr("app.utility_agent.clear_conversation_state", lambda phone, settings: cleared.append(phone))
    monkeypatch.setattr(
        "app.utility_agent.fetch_sencillito_enel_debt_status",
        lambda account_reference: SencillitoEnelDebtStatus(
            client_number="3120910",
            account_reference=account_reference,
            utility_name="ENEL",
            short_utility_name="Enel",
            total_amount=16563,
            total_records=1,
            invoices=[
                SencillitoInvoice(
                    account_reference=account_reference,
                    amount=16563,
                    document_number="40016971491",
                    label="DEUDA ACTUAL",
                    authentication_code="775631818",
                )
            ],
            session_key="scom-test",
            raw_response={},
        ),
    )

    result = handle_utility_debt_task("56996096419", "312091-0", object())

    assert result.reply == (
        "Listo, guardé el número de cliente ENEL 312091-0.\n\n"
        "Para Depto Centro, la cuenta ENEL 312091-0 aparece con deuda actual "
        "de $16.563. Documento asociado: 40016971491."
    )
    assert cleared == ["56996096419"]


def test_utility_agent_asks_for_water_provider_when_missing(monkeypatch) -> None:
    saved_states: list[tuple[str, str, dict]] = []

    monkeypatch.setattr("app.utility_agent.get_active_conversation_state", lambda phone, settings: None)
    monkeypatch.setattr(
        "app.utility_agent.resolve_active_property_for_user",
        lambda phone, settings, property_hint=None: PropertyRecord(
            property_id="property-1",
            name="Depto Centro",
            code="PROP-001",
            street_address="Av. Providencia 1234",
            commune="Providencia",
        ),
    )
    monkeypatch.setattr(
        "app.utility_agent.get_utility_account_for_property",
        lambda property_id, settings, utility_type, provider_name=None: UtilityAccountRecord(
            property_id="property-1",
            property_name="Depto Centro",
            provider_name="",
            utility_type=utility_type,
            service_account_number=None,
        ),
    )
    monkeypatch.setattr(
        "app.utility_agent.save_conversation_state",
        lambda phone, state_type, payload, settings: saved_states.append(
            (phone, state_type, payload)
        ),
    )

    result = handle_utility_debt_task(
        "56996096419",
        "quiero saber cuanto se debe de agua",
        object(),
        utility_type=UTILITY_WATER,
        provider_name=None,
    )

    assert "necesito la empresa y el número de cliente o servicio" in result.reply.lower()
    assert saved_states == [
        (
            "56996096419",
            STATE_COLLECT_UTILITY_ACCOUNT_ID,
            {
                "property_id": "property-1",
                "property_name": "Depto Centro",
                "provider": None,
                "utility_type": "WATER",
            },
        )
    ]


def test_utility_agent_collects_water_provider_and_identifier(monkeypatch) -> None:
    cleared: list[str] = []

    monkeypatch.setattr(
        "app.utility_agent.get_active_conversation_state",
        lambda phone, settings: ConversationState(
            phone_e164=phone,
            state_type=STATE_COLLECT_UTILITY_ACCOUNT_ID,
            payload={
                "property_id": "property-1",
                "property_name": "Depto Centro",
                "provider": None,
                "utility_type": "WATER",
            },
        ),
    )
    monkeypatch.setattr(
        "app.utility_agent.save_account_identifier",
        lambda property_id, utility_type, provider_name, client_identifier, settings: UtilityAccountRecord(
            property_id=property_id,
            property_name="Depto Centro",
            provider_name=provider_name,
            utility_type=utility_type,
            service_account_number=client_identifier,
        ),
    )
    monkeypatch.setattr("app.utility_agent.clear_conversation_state", lambda phone, settings: cleared.append(phone))
    monkeypatch.setattr(
        "app.utility_agent.fetch_sencillito_debt_status",
        lambda account_reference, utility_type, provider_name: SencillitoDebtStatus(
            client_number="21503894",
            account_reference=account_reference,
            utility_name=provider_name,
            short_utility_name=provider_name,
            total_amount=0,
            total_records=0,
            invoices=[],
            session_key="scom-test",
            raw_response={},
        ),
    )

    result = handle_utility_debt_task(
        "56996096419",
        "Aguas Andinas 21503894",
        object(),
    )

    assert result.reply == (
        "Listo, guardé el número de cliente Aguas Andinas 21503894.\n\n"
        "Para Depto Centro, no aparece deuda actual en la cuenta de agua "
        "Aguas Andinas 21503894."
    )
    assert cleared == ["56996096419"]

