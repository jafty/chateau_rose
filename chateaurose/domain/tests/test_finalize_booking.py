from datetime import datetime, timedelta, timezone

import pytest

from chateaurose.domain.entities.booking import BookingRequest
from chateaurose.domain.tests.stubs.booking_repository import InMemoryBookingRepository
from chateaurose.domain.tests.stubs.notifier import InMemoryNotifier
from chateaurose.domain.tests.stubs.payment_gateway import InMemoryPaymentGateway
from chateaurose.domain.tests.stubs.provider_directory import InMemoryProviderDirectory
from chateaurose.domain.tests.stubs.reminder import InMemoryReminderGateway
from chateaurose.domain.use_cases import finalize_booking


def _provider_directory():
    return InMemoryProviderDirectory(
        {
            "provider_1": {
                "name": "Amandine",
                "email": "amandine@example.com",
                "phone": "+33601020304",
                "salon_zone": "Paris 10e",
                "salon_address": "12 rue des Fleurs, 75010 Paris",
                "preferred_contact_method": "EMAIL",
                "post_confirmation_contact_instructions": "Réponds avec ton numéro de réservation.",
            }
        }
    )


def test_provider_confirms_original_captures_and_notifies():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()
    booking = BookingRequest(
        id="booking_1", provider_id="provider_1", service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com", "phone": "+33699999999"}, location="Paris 10e",
        location_preference="salon", desired_date="2026-01-10T17:00:00Z", hair_length="long",
        meche=False, current_hair_picture="s3://bucket/hair.jpg", inspiration_pictures=[], free_text="",
        estimated_price_cents=8500, provider_price_estimate_cents=7000, chateau_rose_fee_cents=1500,
        amount_due_now_cents=1500, payment_status="AUTHORIZED", payment_auth_id="auth_1",
        status="SUBMITTED", created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)
    updated = finalize_booking.execute(
        booking_id="booking_1", actor="provider", decision="confirm",
        now=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc), booking_repository=repo,
        payment_gateway=payments, provider_directory=provider_directory, notifier=notifier,
        operations_email="ops@example.com",
    )
    assert updated.status == finalize_booking.CONFIRMED
    assert updated.payment_status == "CAPTURED"
    assert payments.capture_calls == [{"auth_id": "auth_1"}]
    assert len(notifier.messages) == 3
    assert all("acompte prestataire" not in message["body"] for message in notifier.messages)
    assert any("Frais Château Rose débités" in message["body"] for message in notifier.messages)
    assert "sarah@example.com" in notifier.messages[0]["body"]
    assert "+33699999999" in notifier.messages[0]["body"]
    assert "amandine@example.com" in notifier.messages[1]["body"]
    assert notifier.messages[1]["reply_to"] == "amandine@example.com"


def test_provider_rejects_submitted_booking_moves_to_alternative_search_and_notifies_operations():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()
    now = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)

    booking = BookingRequest(
        id="booking_2",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        location_preference="domicile",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        client_address="5 place du Capitole, 31000 Toulouse",
        payment_auth_id="auth_2",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    updated = finalize_booking.execute(
        booking_id="booking_2",
        actor="provider",
        decision="reject",
        now=now,
        booking_repository=repo,
        payment_gateway=payments,
        provider_directory=provider_directory,
        notifier=notifier,
        operations_email="ops@example.com",
    )

    assert updated.status == finalize_booking.AWAITING_ALTERNATIVE_PROVIDER
    assert updated.alternative_requested_at == now
    assert payments.release_calls == []
    assert payments.capture_calls == []
    assert [(message["recipient"], message["subject"]) for message in notifier.messages] == [
        ("provider_1", "Demande transférée à Château Rose"),
        ("sarah@example.com", "Château Rose cherche une autre coiffeuse"),
        ("ops@example.com", "Alternative à trouver · booking_2"),
    ]
    assert "Ta demande reste ouverte" in notifier.messages[1]["body"]
    assert "Action requise" in notifier.messages[2]["body"]
    assert notifier.messages[2]["reply_to"] == "sarah@example.com"


def test_provider_rejects_pending_client_validation_booking_moves_to_alternative_search():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()
    now = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)

    booking = BookingRequest(
        id="booking_reject_pending",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        location_preference="domicile",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        client_address="5 place du Capitole, 31000 Toulouse",
        payment_auth_id="auth_pending",
        status="PENDING_CLIENT_VALIDATION",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
        proposed_date="2026-01-11T17:00:00Z",
        proposed_price_cents=9000,
    )
    repo.add(booking)

    updated = finalize_booking.execute(
        booking_id="booking_reject_pending",
        actor="provider",
        decision="reject",
        now=now,
        booking_repository=repo,
        payment_gateway=payments,
        provider_directory=provider_directory,
        notifier=notifier,
    )

    assert updated.status == finalize_booking.AWAITING_ALTERNATIVE_PROVIDER
    assert updated.alternative_requested_at == now
    assert payments.release_calls == []
    assert notifier.messages[1]["subject"] == "Château Rose cherche une autre coiffeuse"


def test_client_accepts_proposal_captures_and_confirms():
    repo = InMemoryBookingRepository(); notifier = InMemoryNotifier(); payments = InMemoryPaymentGateway(); provider_directory = _provider_directory()
    created_at = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    proposal_sent_at = created_at + timedelta(hours=70)
    booking = BookingRequest(
        id="booking_3", provider_id="provider_1", service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"}, location="Saint-Cyprien",
        location_preference="domicile", desired_date="2026-01-11T18:00:00Z", hair_length="long", meche=False,
        current_hair_picture="s3://bucket/hair.jpg", inspiration_pictures=[], free_text="",
        estimated_price_cents=10500, provider_price_estimate_cents=9000, chateau_rose_fee_cents=1500,
        amount_due_now_cents=1500, payment_status="AUTHORIZED", client_address="5 place du Capitole, 31000 Toulouse",
        payment_auth_id="auth_3", status="PENDING_CLIENT_VALIDATION", created_at=created_at, updated_at=proposal_sent_at,
        proposed_price_cents=9000, proposed_date="2026-01-11T18:00:00Z",
    )
    repo.add(booking)
    updated = finalize_booking.execute(
        booking_id="booking_3", actor="client", decision="accept", now=created_at + timedelta(hours=73),
        booking_repository=repo, payment_gateway=payments, provider_directory=provider_directory, notifier=notifier,
    )
    assert updated.status == finalize_booking.CONFIRMED
    assert payments.capture_calls == [{"auth_id": "auth_3"}]
    assert any("Frais Château Rose débités" in message["body"] for message in notifier.messages)


def test_client_refuses_proposal_moves_to_alternative_search():
    repo = InMemoryBookingRepository(); notifier = InMemoryNotifier(); payments = InMemoryPaymentGateway(); provider_directory = _provider_directory()
    booking = BookingRequest(
        id="booking_4", provider_id="provider_1", service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"}, location="Saint-Cyprien",
        location_preference="domicile", desired_date="2026-01-11T18:00:00Z", hair_length="long", meche=False,
        current_hair_picture="s3://bucket/hair.jpg", inspiration_pictures=[], free_text="",
        estimated_price_cents=10500, provider_price_estimate_cents=9000, chateau_rose_fee_cents=1500,
        amount_due_now_cents=1500, payment_status="AUTHORIZED", client_address="5 place du Capitole, 31000 Toulouse",
        payment_auth_id="auth_4", status="PENDING_CLIENT_VALIDATION", created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
        proposed_price_cents=9000, proposed_date="2026-01-11T18:00:00Z",
    )
    repo.add(booking)
    updated = finalize_booking.execute(
        booking_id="booking_4", actor="client", decision="refuse", now=datetime(2026, 1, 11, 10, 0, tzinfo=timezone.utc),
        booking_repository=repo, payment_gateway=payments, provider_directory=provider_directory, notifier=notifier,
    )
    assert updated.status == finalize_booking.AWAITING_ALTERNATIVE_PROVIDER
    assert updated.payment_status == "AUTHORIZED"
    assert payments.release_calls == []
    assert all("acompte prestataire" not in message["body"] for message in notifier.messages)


def test_finalize_booking_rejects_invalid_actor():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()

    booking = BookingRequest(
        id="booking_invalid_actor",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        location_preference="domicile",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        client_address="5 place du Capitole, 31000 Toulouse",
        payment_auth_id="auth_invalid_actor",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    with pytest.raises(finalize_booking.InvalidState):
        finalize_booking.execute(
            booking_id="booking_invalid_actor",
            actor="hacker",
            decision="confirm",
            now=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
            booking_repository=repo,
            payment_gateway=payments,
            provider_directory=provider_directory,
            notifier=notifier,
        )

    assert booking.status == "SUBMITTED"
    assert payments.capture_calls == []
    assert payments.release_calls == []


def test_finalize_booking_idempotent_no_double_capture_or_release():
    repo = InMemoryBookingRepository(); notifier = InMemoryNotifier(); payments = InMemoryPaymentGateway(); provider_directory = _provider_directory()
    confirmed = BookingRequest(
        id="confirmed", provider_id="provider_1", service_id="service_tresses", client_contact={"name":"Sarah","email":"sarah@example.com"},
        location="Paris", desired_date="2026-01-10T17:00:00Z", hair_length="long", meche=False, current_hair_picture="", inspiration_pictures=[], free_text="",
        estimated_price_cents=8500, payment_auth_id="auth_confirmed", status=finalize_booking.CONFIRMED, created_at=datetime(2026,1,10,9,0,tzinfo=timezone.utc),
        amount_due_now_cents=1500, payment_status="CAPTURED",
    )
    repo.add(confirmed)
    result = finalize_booking.execute(booking_id="confirmed", actor="provider", decision="confirm", now=datetime(2026,1,10,10,0,tzinfo=timezone.utc), booking_repository=repo, payment_gateway=payments, provider_directory=provider_directory, notifier=notifier)
    assert result.status == finalize_booking.CONFIRMED
    assert payments.capture_calls == []
    assert payments.release_calls == []


def test_finalize_booking_rejects_if_expired():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()

    created_at = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    booking = BookingRequest(
        id="booking_expired",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        location_preference="domicile",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        client_address="5 place du Capitole, 31000 Toulouse",
        payment_auth_id="auth_expired",
        status="SUBMITTED",
        created_at=created_at,
    )
    repo.add(booking)

    with pytest.raises(finalize_booking.InvalidState):
        finalize_booking.execute(
            booking_id="booking_expired",
            actor="provider",
            decision="confirm",
            now=created_at + timedelta(hours=73),
            booking_repository=repo,
            payment_gateway=payments,
            provider_directory=provider_directory,
            notifier=notifier,
        )

    assert payments.capture_calls == []
    assert payments.release_calls == []


def test_admin_can_cancel_uncaptured_booking_even_if_expired():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()

    created_at = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    booking = BookingRequest(
        id="booking_admin_expired",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        location_preference="domicile",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        client_address="5 place du Capitole, 31000 Toulouse",
        payment_auth_id="auth_admin_expired",
        status="SUBMITTED",
        created_at=created_at,
    )
    repo.add(booking)

    updated = finalize_booking.execute(
        booking_id="booking_admin_expired",
        actor="admin",
        decision="cancel",
        now=created_at + timedelta(hours=73),
        booking_repository=repo,
        payment_gateway=payments,
        provider_directory=provider_directory,
        notifier=notifier,
    )

    assert updated.status == finalize_booking.CANCELLED
    assert payments.capture_calls == []
    assert payments.release_calls == [{"auth_id": "auth_admin_expired"}]
    assert len(notifier.messages) == 2


def test_confirm_schedules_client_reminder_24h_before():
    repo = InMemoryBookingRepository(); notifier = InMemoryNotifier(); payments = InMemoryPaymentGateway(); provider_directory = _provider_directory(); reminders = InMemoryReminderGateway()
    booking = BookingRequest(
        id="booking_reminder", provider_id="provider_1", service_id="service_tresses", client_contact={"name":"Sarah","email":"sarah@example.com"},
        location="Paris 10e", location_preference="salon", desired_date="2026-01-12T12:00:00Z", hair_length="long", meche=False,
        current_hair_picture="s3://bucket/hair.jpg", inspiration_pictures=[], free_text="", estimated_price_cents=10000,
        provider_price_estimate_cents=8500, chateau_rose_fee_cents=1500, amount_due_now_cents=1500, payment_status="AUTHORIZED",
        payment_auth_id="auth_reminder", status="SUBMITTED", created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)
    finalize_booking.execute(booking_id="booking_reminder", actor="provider", decision="confirm", now=datetime(2026,1,10,10,0,tzinfo=timezone.utc), booking_repository=repo, payment_gateway=payments, provider_directory=provider_directory, notifier=notifier, reminder_gateway=reminders)
    assert reminders.reminders[0]["send_at"] == datetime(2026, 1, 11, 12, 0, tzinfo=timezone.utc)
    assert "Frais Château Rose débités" in reminders.reminders[0]["body"]


def test_confirm_schedules_client_reminder_immediately_if_within_24h():
    repo = InMemoryBookingRepository(); notifier = InMemoryNotifier(); payments = InMemoryPaymentGateway(); provider_directory = _provider_directory(); reminders = InMemoryReminderGateway()
    now = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)
    booking = BookingRequest(
        id="booking_reminder_soon", provider_id="provider_1", service_id="service_tresses", client_contact={"name":"Sarah","email":"sarah@example.com"},
        location="Paris 10e", location_preference="salon", desired_date="2026-01-10T20:00:00Z", hair_length="long", meche=False,
        current_hair_picture="s3://bucket/hair.jpg", inspiration_pictures=[], free_text="", estimated_price_cents=10000,
        provider_price_estimate_cents=8500, chateau_rose_fee_cents=1500, amount_due_now_cents=1500, payment_status="AUTHORIZED",
        payment_auth_id="auth_reminder_soon", status="SUBMITTED", created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)
    finalize_booking.execute(booking_id="booking_reminder_soon", actor="provider", decision="confirm", now=now, booking_repository=repo, payment_gateway=payments, provider_directory=provider_directory, notifier=notifier, reminder_gateway=reminders)
    assert reminders.reminders[0]["send_at"] == now
    assert "Frais Château Rose débités" in reminders.reminders[0]["body"]


def test_admin_can_cancel_awaiting_alternative_booking_and_notify_operations():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()

    created_at = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    booking = BookingRequest(
        id="booking_admin_alt_cancel",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        location_preference="domicile",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        client_address="5 place du Capitole, 31000 Toulouse",
        payment_auth_id="auth_admin_alt_cancel",
        status=finalize_booking.AWAITING_ALTERNATIVE_PROVIDER,
        created_at=created_at,
        alternative_requested_at=created_at + timedelta(hours=1),
    )
    repo.add(booking)

    updated = finalize_booking.execute(
        booking_id="booking_admin_alt_cancel",
        actor="admin",
        decision="cancel",
        now=created_at + timedelta(hours=2),
        booking_repository=repo,
        payment_gateway=payments,
        provider_directory=provider_directory,
        notifier=notifier,
        operations_email="ops@example.com",
    )

    assert updated.status == finalize_booking.CANCELLED
    assert payments.release_calls == [{"auth_id": "auth_admin_alt_cancel"}]
    assert notifier.messages[-1]["recipient"] == "ops@example.com"
    assert notifier.messages[-1]["subject"] == "Demande annulée par Château Rose · booking_admin_alt_cancel"


def test_client_refusal_notifies_operations_when_email_is_configured():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()

    created_at = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    booking = BookingRequest(
        id="booking_client_refusal_ops",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        location_preference="domicile",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        client_address="5 place du Capitole, 31000 Toulouse",
        payment_auth_id="auth_client_refusal_ops",
        status="PENDING_CLIENT_VALIDATION",
        created_at=created_at,
        proposed_date="2026-01-11T17:00:00Z",
        proposed_price_cents=9000,
    )
    repo.add(booking)

    updated = finalize_booking.execute(
        booking_id="booking_client_refusal_ops",
        actor="client",
        decision="refuse",
        now=created_at + timedelta(hours=2),
        booking_repository=repo,
        payment_gateway=payments,
        provider_directory=provider_directory,
        notifier=notifier,
        operations_email="ops@example.com",
    )

    assert updated.status == finalize_booking.AWAITING_ALTERNATIVE_PROVIDER
    assert payments.release_calls == []
    assert notifier.messages[-1]["recipient"] == "ops@example.com"
    assert notifier.messages[-1]["subject"] == "Alternative à trouver après refus client · booking_client_refusal_ops"


def test_admin_can_cancel_waiting_provider_assignment_booking():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()
    created_at = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    booking = BookingRequest(
        id="booking_waiting_assignment_cancel",
        booking_kind="GENERIC",
        provider_id=None,
        service_id=None,
        requested_marketing_service_id="mkt-1",
        requested_marketing_sub_service_id="sub-1",
        requested_service_label_snapshot="Tresses plaquées",
        requested_options=["avec motifs"],
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="À préciser",
        location_preference="salon",
        desired_date="2026-01-10T17:00:00Z",
        hair_length="standard",
        general_adjustments=["avec motifs"],
        meche=False,
        current_hair_picture="",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=9000,
        provider_price_estimate_cents=8000,
        chateau_rose_fee_cents=1000,
        amount_due_now_cents=1000,
        payment_status="AUTHORIZED",
        payment_auth_id="auth_waiting_assignment_cancel",
        status=finalize_booking.WAITING_PROVIDER_ASSIGNMENT,
        created_at=created_at,
    )
    repo.add(booking)

    updated = finalize_booking.execute(
        booking_id="booking_waiting_assignment_cancel",
        actor="admin",
        decision="cancel",
        now=created_at + timedelta(hours=2),
        booking_repository=repo,
        payment_gateway=payments,
        provider_directory=provider_directory,
        notifier=notifier,
        operations_email="ops@example.com",
    )

    assert updated.status == finalize_booking.CANCELLED
    assert payments.release_calls == [{"auth_id": "auth_waiting_assignment_cancel"}]
