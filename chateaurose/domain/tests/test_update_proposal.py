from datetime import datetime, timezone

import pytest

from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.exceptions import InvalidState, PermissionError, ValidationError
from chateaurose.domain.tests.stubs.booking_repository import InMemoryBookingRepository
from chateaurose.domain.tests.stubs.notifier import InMemoryNotifier
from chateaurose.domain.tests.stubs.provider_directory import InMemoryProviderDirectory
from chateaurose.domain.use_cases import update_proposal


def test_provider_proposes_update_moves_to_pending_client_validation_and_notifies_client():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    provider_directory = InMemoryProviderDirectory(
        {
            "provider_1": {
                "name": "Amandine",
                "email": "amandine@example.com",
                "phone": "+33601020304",
            }
        }
    )

    provider_id = "provider_1"
    client = {"name": "Sarah", "email": "sarah@example.com"}
    booking = BookingRequest(
        id="booking_1",
        provider_id=provider_id,
        service_id="service_tresses",
        client_contact=client,
        location="Saint-Cyprien",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_1",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    updated = update_proposal.execute(
        booking_id="booking_1",
        provider_id=provider_id,
        new_price_cents=9000,
        new_date="2026-01-11T18:00:00Z",
        booking_repository=repo,
        notifier=notifier,
        provider_directory=provider_directory,
        client_control_url="https://example.com/booking/booking_1/",
    )

    assert updated.status == update_proposal.PENDING_CLIENT_VALIDATION
    assert updated.proposed_price_cents == 9000
    assert updated.proposed_date == "2026-01-11T18:00:00Z"

    assert len(notifier.messages) == 1
    message = notifier.messages[0]
    assert message["recipient"] == client["email"]
    assert message["subject"] == "Proposition de rendez-vous"
    assert message["reply_to"] == "amandine@example.com"
    assert "- Tarif proposé : 90,00 €" in message["body"]
    assert "Frais Château Rose déjà traités" in message["body"]
    assert "Prestation coiffure à régler directement" in message["body"]
    assert "acompte prestataire" not in message["body"]


def test_update_proposal_rejects_wrong_provider():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    provider_directory = InMemoryProviderDirectory(
        {
            "provider_1": {
                "name": "Amandine",
                "email": "amandine@example.com",
                "phone": "+33601020304",
            }
        }
    )

    booking = BookingRequest(
        id="booking_2",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_2",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    with pytest.raises(PermissionError):
        update_proposal.execute(
            booking_id="booking_2",
            provider_id="intruder",
            new_price_cents=9000,
            new_date="2026-01-11T18:00:00Z",
            booking_repository=repo,
            notifier=notifier,
            provider_directory=provider_directory,
            client_control_url="https://example.com/booking/booking_2/",
        )

    assert booking.status == "SUBMITTED"
    assert notifier.messages == []


def test_update_proposal_rejects_terminal_state():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    provider_directory = InMemoryProviderDirectory(
        {
            "provider_1": {
                "name": "Amandine",
                "email": "amandine@example.com",
                "phone": "+33601020304",
            }
        }
    )

    booking = BookingRequest(
        id="booking_3",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_3",
        status="CONFIRMED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    with pytest.raises(InvalidState):
        update_proposal.execute(
            booking_id="booking_3",
            provider_id="provider_1",
            new_price_cents=9000,
            new_date="2026-01-11T18:00:00Z",
            booking_repository=repo,
            notifier=notifier,
            provider_directory=provider_directory,
            client_control_url="https://example.com/booking/booking_3/",
        )

    assert notifier.messages == []


def test_provider_can_send_multiple_proposals_before_terminal():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    provider_directory = InMemoryProviderDirectory(
        {
            "provider_1": {
                "name": "Amandine",
                "email": "amandine@example.com",
                "phone": "+33601020304",
            }
        }
    )

    provider_id = "provider_1"
    client = {"name": "Sarah", "email": "sarah@example.com"}
    booking = BookingRequest(
        id="booking_multi",
        provider_id=provider_id,
        service_id="service_tresses",
        client_contact=client,
        location="Saint-Cyprien",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_multi",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    first = update_proposal.execute(
        booking_id="booking_multi",
        provider_id=provider_id,
        new_price_cents=9000,
        new_date="2026-01-11T18:00:00Z",
        booking_repository=repo,
        notifier=notifier,
        provider_directory=provider_directory,
        client_control_url="https://example.com/booking/booking_multi/",
    )
    second = update_proposal.execute(
        booking_id="booking_multi",
        provider_id=provider_id,
        new_price_cents=9500,
        new_date="2026-01-12T19:00:00Z",
        booking_repository=repo,
        notifier=notifier,
        provider_directory=provider_directory,
        client_control_url="https://example.com/booking/booking_multi/",
    )

    assert second.status == update_proposal.PENDING_CLIENT_VALIDATION
    assert second.proposed_price_cents == 9500
    assert second.proposed_date == "2026-01-12T19:00:00Z"
    # two notifications, one per proposal
    assert len(notifier.messages) == 2


def test_provider_can_update_only_price_without_changing_date():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    provider_directory = InMemoryProviderDirectory(
        {
            "provider_1": {
                "name": "Amandine",
                "email": "amandine@example.com",
                "phone": "+33601020304",
            }
        }
    )

    booking = BookingRequest(
        id="booking_price_only",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_price_only",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
        proposed_date="2026-01-11T18:00:00Z",
    )
    repo.add(booking)

    updated = update_proposal.execute(
        booking_id="booking_price_only",
        provider_id="provider_1",
        new_price_cents=9200,
        new_date=None,
        booking_repository=repo,
        notifier=notifier,
        provider_directory=provider_directory,
        client_control_url="https://example.com/booking/booking_price_only/",
    )

    assert updated.proposed_price_cents == 9200
    assert updated.proposed_date == "2026-01-11T18:00:00Z"


def test_provider_can_update_only_date_without_changing_price():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    provider_directory = InMemoryProviderDirectory(
        {
            "provider_1": {
                "name": "Amandine",
                "email": "amandine@example.com",
                "phone": "+33601020304",
            }
        }
    )

    booking = BookingRequest(
        id="booking_date_only",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_date_only",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
        proposed_price_cents=9000,
    )
    repo.add(booking)

    updated = update_proposal.execute(
        booking_id="booking_date_only",
        provider_id="provider_1",
        new_price_cents=None,
        new_date="2026-01-13T12:30:00Z",
        booking_repository=repo,
        notifier=notifier,
        provider_directory=provider_directory,
        client_control_url="https://example.com/booking/booking_date_only/",
    )

    assert updated.proposed_price_cents == 9000
    assert updated.proposed_date == "2026-01-13T12:30:00Z"


def test_update_proposal_requires_price_or_date():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    provider_directory = InMemoryProviderDirectory(
        {
            "provider_1": {
                "name": "Amandine",
                "email": "amandine@example.com",
                "phone": "+33601020304",
            }
        }
    )

    booking = BookingRequest(
        id="booking_empty",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_empty",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    with pytest.raises(ValidationError):
        update_proposal.execute(
            booking_id="booking_empty",
            provider_id="provider_1",
            new_price_cents=None,
            new_date=None,
            booking_repository=repo,
            notifier=notifier,
            provider_directory=provider_directory,
            client_control_url="https://example.com/booking/booking_empty/",
        )


def test_update_proposal_includes_optional_free_text_message_in_email():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    provider_directory = InMemoryProviderDirectory(
        {
            "provider_1": {
                "name": "Amandine",
                "email": "amandine@example.com",
                "phone": "+33601020304",
            }
        }
    )

    booking = BookingRequest(
        id="booking_with_message",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_with_message",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    update_proposal.execute(
        booking_id="booking_with_message",
        provider_id="provider_1",
        new_price_cents=9200,
        new_date="2026-01-13T12:30:00Z",
        counter_proposal_message="Je peux aussi avancer de 30 minutes si besoin.",
        booking_repository=repo,
        notifier=notifier,
        provider_directory=provider_directory,
        client_control_url="https://example.com/booking/booking_with_message/",
    )

    assert "Message de la prestataire / du prestataire :" in notifier.messages[0]["body"]
    assert "Je peux aussi avancer de 30 minutes si besoin." in notifier.messages[0]["body"]


def test_update_proposal_payment_lines_include_service_fee_in_captured_amount():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    provider_directory = InMemoryProviderDirectory(
        {
            "provider_1": {
                "name": "Amandine",
                "email": "amandine@example.com",
                "phone": "+33601020304",
                "deposit_percentage": 30,
                "service_fee_percentage": 15,
            }
        }
    )

    booking = BookingRequest(
        id="booking_fee_1",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_fee_1",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    update_proposal.execute(
        booking_id="booking_fee_1",
        provider_id="provider_1",
        new_price_cents=9000,
        new_date="2026-01-11T18:00:00Z",
        booking_repository=repo,
        notifier=notifier,
        provider_directory=provider_directory,
        client_control_url="https://example.com/booking/booking_fee_1/",
    )

    body = notifier.messages[0]["body"]
    assert "Frais Château Rose déjà traités" in body
    assert "Prestation coiffure à régler directement à la prestataire : 90,00 €" in body
    assert "acompte prestataire" not in body
