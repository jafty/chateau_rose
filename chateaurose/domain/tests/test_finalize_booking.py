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
            }
        }
    )


def test_provider_confirms_original_captures_and_notifies():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()

    booking = BookingRequest(
        id="booking_1",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Paris 10e",
        location_preference="salon",
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

    updated = finalize_booking.execute(
        booking_id="booking_1",
        actor="provider",
        decision="confirm",
        now=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        booking_repository=repo,
        payment_gateway=payments,
        provider_directory=provider_directory,
        notifier=notifier,
        operations_email="ops@example.com",
    )

    assert updated.status == finalize_booking.CONFIRMED
    assert payments.capture_calls == [{"auth_id": "auth_1"}]
    assert notifier.messages == [
        {
            "recipient": "provider_1",
            "subject": "Rendez-vous confirmé",
            "body": "\n".join(
                [
                    "Bonjour Amandine,",
                    "",
                    "Merci, ton rendez-vous est confirmé.",
                    "Récapitulatif :",
                    "- Date : 2026-01-10T17:00:00Z",
                    "- Lieu : Paris 10e",
                    "- Tarif : 85,00 €",
                    "",
                    "Paiement :",
                    "- Frais de réservation débités : 25,50 €",
                    "  dont acompte prestataire : 25,50 €",
                    "  dont frais Château Rose : 0,00 €",
                    "- Reste à régler chez la prestataire : 59,50 €",
                    "  (arrondi à payer le jour J : 59,00 €)",
                    "",
                    "La personne cliente se déplace chez toi.",
                    "",
                    "Belle journée,",
                    "L'équipe Château Rose",
                ]
            ),
        },
        {
            "recipient": "sarah@example.com",
            "subject": "Rendez-vous confirmé",
            "body": "\n".join(
                [
                    "Bonjour Sarah,",
                    "",
                    "Bonne nouvelle, ta réservation est confirmée.",
                    "Récapitulatif :",
                    "- Date : 2026-01-10T17:00:00Z",
                    "- Lieu : Paris 10e",
                    "- Tarif : 85,00 €",
                    "",
                    "Paiement :",
                    "- Frais de réservation débités : 25,50 €",
                    "  dont acompte prestataire : 25,50 €",
                    "  dont frais Château Rose : 0,00 €",
                    "- Reste à régler chez la prestataire : 59,50 €",
                    "  (arrondi à payer le jour J : 59,00 €)",
                    "",
                    "Adresse de la prestataire : 12 rue des Fleurs, 75010 Paris",
                    "Cette information est partagée uniquement pour organiser le rendez-vous.",
                    "",
                    "À très vite,",
                    "L'équipe Château Rose",
                ]
            ),
        },
        {
            "recipient": "ops@example.com",
            "subject": "Acompte débité · rendez-vous confirmé",
            "body": "\n".join(
                [
                    "Un rendez-vous vient d'être confirmé et l'acompte a été débité.",
                    "- ID demande : booking_1",
                    "- Prestataire : Amandine",
                    "- Cliente : Sarah (sarah@example.com)",
                    "- Date : 2026-01-10T17:00:00Z",
                    "- Lieu : Paris 10e",
                    "- Tarif total : 85,00 €",
                    "Paiement :",
                    "- Frais de réservation débités : 25,50 €",
                    "  dont acompte prestataire : 25,50 €",
                    "  dont frais Château Rose : 0,00 €",
                    "- Reste à régler chez la prestataire : 59,50 €",
                    "  (arrondi à payer le jour J : 59,00 €)",
                ]
            ),
            "reply_to": "sarah@example.com",
        },
    ]


def test_provider_rejects_releases_and_notifies():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()

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
        now=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        booking_repository=repo,
        payment_gateway=payments,
        provider_directory=provider_directory,
        notifier=notifier,
    )

    assert updated.status == finalize_booking.CANCELLED
    assert payments.release_calls == [{"auth_id": "auth_2"}]
    assert notifier.messages[-2:] == [
        {
            "recipient": "provider_1",
            "subject": "Demande annulée",
            "body": "\n".join(
                [
                    "Bonjour Amandine,",
                    "",
                    "Tu as bien annulé la demande.",
                    "Récapitulatif :",
                    "- Date : 2026-01-10T17:00:00Z",
                    "- Lieu : Saint-Cyprien",
                    "- Tarif : 85,00 €",
                    "",
                    "Paiement :",
                    "- Empreinte bancaire déjà validée : 25,50 € (pas encore débités)",
                    "  dont acompte prestataire : 25,50 €",
                    "  dont frais Château Rose : 0,00 €",
                    "- Montant qui sera débité à la confirmation : 25,50 €",
                    "  (arrondi affiché : 26,00 €)",
                    "- Reste à régler chez la prestataire après confirmation : 59,50 €",
                    "  (arrondi à payer le jour J : 59,00 €)",
                    "",
                    "À bientôt,",
                    "L'équipe Château Rose",
                ]
            ),
        },
        {
            "recipient": "sarah@example.com",
            "subject": "Demande annulée",
            "body": "\n".join(
                [
                    "Bonjour Sarah,",
                    "",
                    "La demande a été refusée par la prestataire.",
                    "Récapitulatif :",
                    "- Date : 2026-01-10T17:00:00Z",
                    "- Lieu : Saint-Cyprien",
                    "- Tarif : 85,00 €",
                    "",
                    "Paiement :",
                    "- Empreinte bancaire déjà validée : 25,50 € (pas encore débités)",
                    "  dont acompte prestataire : 25,50 €",
                    "  dont frais Château Rose : 0,00 €",
                    "- Montant qui sera débité à la confirmation : 25,50 €",
                    "  (arrondi affiché : 26,00 €)",
                    "- Reste à régler chez la prestataire après confirmation : 59,50 €",
                    "  (arrondi à payer le jour J : 59,00 €)",
                    "",
                    "Si tu veux, tu peux déposer une nouvelle demande.",
                    "À bientôt,",
                    "L'équipe Château Rose",
                ]
            ),
        },
    ]


def test_client_accepts_proposal_captures_and_confirms():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()

    booking = BookingRequest(
        id="booking_3",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        location_preference="domicile",
        desired_date="2026-01-11T18:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        client_address="5 place du Capitole, 31000 Toulouse",
        payment_auth_id="auth_3",
        status="PENDING_CLIENT_VALIDATION",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
        proposed_price_cents=9000,
        proposed_date="2026-01-11T18:00:00Z",
    )
    repo.add(booking)

    updated = finalize_booking.execute(
        booking_id="booking_3",
        actor="client",
        decision="accept",
        now=datetime(2026, 1, 11, 10, 0, tzinfo=timezone.utc),
        booking_repository=repo,
        payment_gateway=payments,
        provider_directory=provider_directory,
        notifier=notifier,
    )

    assert updated.status == finalize_booking.CONFIRMED
    assert payments.capture_calls == [{"auth_id": "auth_3"}]
    assert notifier.messages == [
        {
            "recipient": "provider_1",
            "subject": "Rendez-vous confirmé",
            "body": "\n".join(
                [
                    "Bonjour Amandine,",
                    "",
                    "La personne cliente a accepté la proposition.",
                    "Récapitulatif :",
                    "- Date : 2026-01-11T18:00:00Z",
                    "- Lieu : Saint-Cyprien",
                    "- Tarif : 90,00 €",
                    "",
                    "Paiement :",
                    "- Frais de réservation débités : 27,00 €",
                    "  dont acompte prestataire : 27,00 €",
                    "  dont frais Château Rose : 0,00 €",
                    "- Reste à régler chez la prestataire : 63,00 €",
                    "  (arrondi à payer le jour J : 63,00 €)",
                    "",
                    "Adresse de la personne cliente : 5 place du Capitole, 31000 Toulouse",
                    "Adresse transmise uniquement pour ce rendez-vous, merci de la garder confidentielle.",
                    "",
                    "Belle journée,",
                    "L'équipe Château Rose",
                ]
            ),
        },
        {
            "recipient": "sarah@example.com",
            "subject": "Rendez-vous confirmé",
            "body": "\n".join(
                [
                    "Bonjour Sarah,",
                    "",
                    "Bonne nouvelle, ta réservation est confirmée.",
                    "Récapitulatif :",
                    "- Date : 2026-01-11T18:00:00Z",
                    "- Lieu : Saint-Cyprien",
                    "- Tarif : 90,00 €",
                    "",
                    "Paiement :",
                    "- Frais de réservation débités : 27,00 €",
                    "  dont acompte prestataire : 27,00 €",
                    "  dont frais Château Rose : 0,00 €",
                    "- Reste à régler chez la prestataire : 63,00 €",
                    "  (arrondi à payer le jour J : 63,00 €)",
                    "",
                    "Le profil partenaire se déplace jusqu'à toi.",
                    "",
                    "À très vite,",
                    "L'équipe Château Rose",
                ]
            ),
        },
    ]


def test_client_refuses_proposal_releases_and_cancels():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()

    booking = BookingRequest(
        id="booking_4",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Saint-Cyprien",
        location_preference="domicile",
        desired_date="2026-01-11T18:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        client_address="5 place du Capitole, 31000 Toulouse",
        payment_auth_id="auth_4",
        status="PENDING_CLIENT_VALIDATION",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
        proposed_price_cents=9000,
        proposed_date="2026-01-11T18:00:00Z",
    )
    repo.add(booking)

    updated = finalize_booking.execute(
        booking_id="booking_4",
        actor="client",
        decision="refuse",
        now=datetime(2026, 1, 11, 10, 0, tzinfo=timezone.utc),
        booking_repository=repo,
        payment_gateway=payments,
        provider_directory=provider_directory,
        notifier=notifier,
    )

    assert updated.status == finalize_booking.CANCELLED
    assert payments.release_calls == [{"auth_id": "auth_4"}]
    assert notifier.messages == [
        {
            "recipient": "provider_1",
            "subject": "Demande annulée",
            "body": "\n".join(
                [
                    "Bonjour Amandine,",
                    "",
                    "La personne cliente a refusé la proposition.",
                    "Récapitulatif :",
                    "- Date : 2026-01-11T18:00:00Z",
                    "- Lieu : Saint-Cyprien",
                    "- Tarif : 90,00 €",
                    "",
                    "Paiement :",
                    "- Empreinte bancaire déjà validée : 27,00 € (pas encore débités)",
                    "  dont acompte prestataire : 27,00 €",
                    "  dont frais Château Rose : 0,00 €",
                    "- Montant qui sera débité à la confirmation : 27,00 €",
                    "  (arrondi affiché : 27,00 €)",
                    "- Reste à régler chez la prestataire après confirmation : 63,00 €",
                    "  (arrondi à payer le jour J : 63,00 €)",
                    "",
                    "À bientôt,",
                    "L'équipe Château Rose",
                ]
            ),
        },
        {
            "recipient": "sarah@example.com",
            "subject": "Demande annulée",
            "body": "\n".join(
                [
                    "Bonjour Sarah,",
                    "",
                    "Tu as refusé la proposition : la demande est annulée.",
                    "Récapitulatif :",
                    "- Date : 2026-01-11T18:00:00Z",
                    "- Lieu : Saint-Cyprien",
                    "- Tarif : 90,00 €",
                    "",
                    "Paiement :",
                    "- Empreinte bancaire déjà validée : 27,00 € (pas encore débités)",
                    "  dont acompte prestataire : 27,00 €",
                    "  dont frais Château Rose : 0,00 €",
                    "- Montant qui sera débité à la confirmation : 27,00 €",
                    "  (arrondi affiché : 27,00 €)",
                    "- Reste à régler chez la prestataire après confirmation : 63,00 €",
                    "  (arrondi à payer le jour J : 63,00 €)",
                    "",
                    "Si tu veux, tu peux déposer une nouvelle demande.",
                    "À bientôt,",
                    "L'équipe Château Rose",
                ]
            ),
        },
    ]


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
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()

    booking = BookingRequest(
        id="booking_idem",
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
        payment_auth_id="auth_idem",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    first = finalize_booking.execute(
        booking_id="booking_idem",
        actor="provider",
        decision="confirm",
        now=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        booking_repository=repo,
        payment_gateway=payments,
        provider_directory=provider_directory,
        notifier=notifier,
    )
    second = finalize_booking.execute(
        booking_id="booking_idem",
        actor="provider",
        decision="confirm",
        now=datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc),
        booking_repository=repo,
        payment_gateway=payments,
        provider_directory=provider_directory,
        notifier=notifier,
    )

    assert first.status == finalize_booking.CONFIRMED
    assert second.status == finalize_booking.CONFIRMED
    assert payments.capture_calls == [{"auth_id": "auth_idem"}]
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
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()
    reminders = InMemoryReminderGateway()

    booking = BookingRequest(
        id="booking_reminder_24h",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Paris 10e",
        location_preference="salon",
        desired_date="2026-01-12T12:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_reminder_24h",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    now = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)
    finalize_booking.execute(
        booking_id="booking_reminder_24h",
        actor="provider",
        decision="confirm",
        now=now,
        booking_repository=repo,
        payment_gateway=payments,
        provider_directory=provider_directory,
        notifier=notifier,
        reminder_gateway=reminders,
    )

    assert reminders.reminders == [
        {
            "recipient": "sarah@example.com",
            "send_at": datetime(2026, 1, 11, 12, 0, tzinfo=timezone.utc),
            "subject": "Rappel: rendez-vous confirmé",
            "body": "\n".join(
                [
                    "Bonjour Sarah,",
                    "",
                    "Petit rappel pour ton rendez-vous confirmé.",
                    "Récapitulatif :",
                    "- Date : 2026-01-12T12:00:00Z",
                    "- Lieu : Paris 10e",
                    "- Tarif : 85,00 €",
                    "",
                    "Paiement :",
                    "- Frais de réservation débités : 25,50 €",
                    "  dont acompte prestataire : 25,50 €",
                    "  dont frais Château Rose : 0,00 €",
                    "- Reste à régler chez la prestataire : 59,50 €",
                    "  (arrondi à payer le jour J : 59,00 €)",
                    "",
                    "À très vite,",
                    "L'équipe Château Rose",
                ]
            ),
        }
    ]


def test_confirm_schedules_client_reminder_immediately_if_within_24h():
    repo = InMemoryBookingRepository()
    notifier = InMemoryNotifier()
    payments = InMemoryPaymentGateway()
    provider_directory = _provider_directory()
    reminders = InMemoryReminderGateway()

    booking = BookingRequest(
        id="booking_reminder_soon",
        provider_id="provider_1",
        service_id="service_tresses",
        client_contact={"name": "Sarah", "email": "sarah@example.com"},
        location="Paris 10e",
        location_preference="salon",
        desired_date="2026-01-10T20:00:00Z",
        hair_length="long",
        meche=False,
        current_hair_picture="s3://bucket/hair.jpg",
        inspiration_pictures=[],
        free_text="",
        estimated_price_cents=8500,
        payment_auth_id="auth_reminder_soon",
        status="SUBMITTED",
        created_at=datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc),
    )
    repo.add(booking)

    now = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)
    finalize_booking.execute(
        booking_id="booking_reminder_soon",
        actor="provider",
        decision="confirm",
        now=now,
        booking_repository=repo,
        payment_gateway=payments,
        provider_directory=provider_directory,
        notifier=notifier,
        reminder_gateway=reminders,
    )

    assert reminders.reminders == [
        {
            "recipient": "sarah@example.com",
            "send_at": now,
            "subject": "Rappel: rendez-vous confirmé",
            "body": "\n".join(
                [
                    "Bonjour Sarah,",
                    "",
                    "Petit rappel pour ton rendez-vous confirmé.",
                    "Récapitulatif :",
                    "- Date : 2026-01-10T20:00:00Z",
                    "- Lieu : Paris 10e",
                    "- Tarif : 85,00 €",
                    "",
                    "Paiement :",
                    "- Frais de réservation débités : 25,50 €",
                    "  dont acompte prestataire : 25,50 €",
                    "  dont frais Château Rose : 0,00 €",
                    "- Reste à régler chez la prestataire : 59,50 €",
                    "  (arrondi à payer le jour J : 59,00 €)",
                    "",
                    "À très vite,",
                    "L'équipe Château Rose",
                ]
            ),
        }
    ]
