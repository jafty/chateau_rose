from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from booking.models import Booking, BookingOffer, BookingOpportunity, Provider, Service
from chateaurose.domain.exceptions import InvalidState, ValidationError
from chateaurose.domain.use_cases import bounty as bounty_uc
from chateaurose.infrastructure.email_notifier import EmailNotifier
from chateaurose.infrastructure.stripe_gateway import StripePaymentGateway

notifier = EmailNotifier()
payments = StripePaymentGateway()


def _parse_date(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("La date proposée est invalide.") from exc
    return timezone.make_aware(result) if timezone.is_naive(result) else result


def _sub_service_for(booking: Booking):
    if booking.booking_kind == Booking.KIND_GENERIC:
        return booking.requested_marketing_sub_service
    if not booking.service_id:
        return None
    links = list(booking.service.marketing_sub_services.all()[:2])
    return links[0] if len(links) == 1 else None


def eligible_services(opportunity, provider=None):
    qs = (
        Service.objects.filter(
            marketing_sub_services=opportunity.requested_sub_service,
            provider__is_visible_on_website=True,
            provider__user__isnull=False,
        )
        .exclude(provider__contact_email="")
        .select_related("provider")
    )
    if opportunity.excluded_provider_id:
        qs = qs.exclude(provider_id=opportunity.excluded_provider_id)
    if provider:
        qs = qs.filter(provider=provider)
    return qs


def open_for_booking(booking_id: str, *, reason: str, now=None, base_url=""):
    now = now or timezone.now()
    base_url = (
        base_url or getattr(settings, "SITE_URL", "") or "https://www.chateau-rose.fr"
    ).rstrip("/")
    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(booking_id=booking_id)
        sub_service = _sub_service_for(booking)
        if not sub_service:
            booking.status = Booking.STATUS_CANCELLED
            booking.updated_at = booking.state_entered_at = now
            booking.save(update_fields=("status", "updated_at", "state_entered_at"))
            if booking.payment_auth_id:
                payments.release_auth(booking.payment_auth_id)
                booking.payment_status = Booking.PAYMENT_STATUS_RELEASED
                booking.save(update_fields=("payment_status",))
            notifier.notify(
                getattr(settings, "OPERATIONS_EMAIL", ""),
                f"Bounty impossible · {booking.booking_id}",
                "Bonjour,\n\n"
                "La recherche de prestataire n'a pas pu être lancée : le service "
                "n'est lié exactement à aucun sous-service marketing.\n\n"
                f"Demande : {booking.booking_id}\n"
                "Statut : annulée\n\n"
                "Merci de vérifier le paramétrage du catalogue.\n\n"
                "L'équipe Château Rose",
            )
            notifier.notify(
                booking.client_email,
                "Demande annulée",
                f"Bonjour {booking.client_name},\n\n"
                "Nous sommes désolés, aucune autre prestataire compatible n'a pu être recherchée. "
                "Ta demande a donc été annulée.\n\n"
                "Ton autorisation de paiement a bien été libérée.\n\n"
                "À bientôt,\nL'équipe Château Rose",
            )
            return None
        if not booking.process_expires_at:
            from datetime import timedelta

            booking.process_expires_at = booking.created_at + timedelta(days=6)
        data = bounty_uc.open_bounty(
            booking=booking, reason=reason, now=now, sub_service_id=str(sub_service.id)
        )
        opportunity = BookingOpportunity.objects.create(
            booking=booking,
            reason=reason,
            requested_sub_service=sub_service,
            excluded_provider_id=(
                booking.provider_id
                if reason != BookingOpportunity.REASON_GENERIC
                else None
            ),
            opened_at=now,
            response_deadline_at=data["deadline"],
        )
        booking.save(
            update_fields=(
                "status",
                "updated_at",
                "state_entered_at",
                "process_expires_at",
            )
        )
        services = list(eligible_services(opportunity))
        if not services:
            opportunity.status, opportunity.closed_at = (
                BookingOpportunity.STATUS_CANCELLED,
                now,
            )
            opportunity.save(update_fields=("status", "closed_at"))
            booking.status = Booking.STATUS_CANCELLED
            booking.save(update_fields=("status",))
            if booking.payment_auth_id:
                payments.release_auth(booking.payment_auth_id)
                booking.payment_status = Booking.PAYMENT_STATUS_RELEASED
                booking.save(update_fields=("payment_status",))
            notifier.notify(
                booking.client_email,
                "Demande annulée",
                f"Bonjour {booking.client_name},\n\n"
                "Nous sommes désolés, nous n'avons trouvé aucune autre prestataire proposant cette prestation. "
                "Ta demande a donc été annulée.\n\n"
                "Ton autorisation de paiement a bien été libérée.\n\n"
                "À bientôt,\nL'équipe Château Rose",
            )
            return opportunity
    providers = {service.provider_id: service.provider for service in services}
    for provider in providers.values():
        url = f"{base_url}{reverse('providers:bounty_offer', args=[opportunity.id])}"
        notifier.notify(
            provider.contact_email,
            f"Une demande de {sub_service.name} est disponible",
            f"Bonjour {provider.name},\n\n"
            "Une nouvelle opportunité de rendez-vous est disponible.\n\n"
            f"Prestation : {sub_service.name}\n"
            f"Date souhaitée : {booking.desired_date}\n"
            f"Zone : {booking.location or 'Non précisée'}\n\n"
            "Consulter la demande et faire une proposition :\n"
            f"{url}\n\n"
            "La première proposition éligible sera transmise à la cliente.\n\n"
            "À bientôt,\nL'équipe Château Rose",
        )
    return opportunity


def submit_offer(
    *,
    opportunity_id,
    provider: Provider,
    service_id,
    proposed_date,
    proposed_price_euros,
    message="",
    now=None,
):
    now = now or timezone.now()
    try:
        cents = int(
            (Decimal(str(proposed_price_euros).replace(",", ".")) * 100).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("Le tarif proposé est invalide.") from exc
    with transaction.atomic():
        opportunity = (
            BookingOpportunity.objects.select_for_update()
            .select_related("booking", "requested_sub_service")
            .get(pk=opportunity_id)
        )
        booking = Booking.objects.select_for_update().get(pk=opportunity.booking_id)
        service = eligible_services(opportunity, provider).filter(pk=service_id).first()
        terms = bounty_uc.OfferTerms(
            str(provider.id), str(service_id), proposed_date, cents, message
        )
        client_deadline = bounty_uc.submit_first_offer(
            booking=booking,
            opportunity=opportunity,
            terms=terms,
            now=now,
            provider_is_eligible=service is not None,
            desired_at=_parse_date(proposed_date),
        )
        offer = BookingOffer.objects.create(
            opportunity=opportunity,
            provider=provider,
            service=service,
            proposed_date=proposed_date,
            proposed_price_cents=cents,
            message=message,
            submitted_at=now,
            client_deadline_at=client_deadline,
        )
        opportunity.save(update_fields=("status", "closed_at"))
        booking.save(update_fields=("status", "updated_at", "state_entered_at"))
    token = signing.dumps({"offer": offer.id}, salt="bounty-client")
    base_url = (
        getattr(settings, "SITE_URL", "") or "https://www.chateau-rose.fr"
    ).rstrip("/")
    url = base_url + reverse("interface:bounty_client_offer", args=[token])
    profile_url = base_url + reverse("interface:provider_detail", args=[provider.id])
    notifier.notify(
        booking.client_email,
        f"{provider.name} propose de prendre ton rendez-vous",
        f"Bonjour {booking.client_name},\n\n"
        f"Bonne nouvelle : {provider.name} propose de prendre ton rendez-vous.\n\n"
        f"Date proposée : {proposed_date}\n"
        f"Tarif à régler le jour J : {cents / 100:.2f} €\n"
        f"Profil de la prestataire : {profile_url}\n\n"
        "Pour accepter ou refuser la proposition :\n"
        f"{url}\n\n"
        "Les frais Château Rose déjà traités restent inchangés.\n\n"
        "À bientôt,\nL'équipe Château Rose",
    )
    return offer


def _capture_confirmation_payment(booking):
    """Capture the locked platform fee, changing state only after Stripe succeeds."""
    if booking.payment_auth_id and booking.amount_due_now_cents > 0:
        payments.capture_auth(booking.payment_auth_id)
        booking.payment_status = Booking.PAYMENT_STATUS_CAPTURED


def accept_unchanged(*, opportunity_id, provider: Provider, service_id, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        opportunity = (
            BookingOpportunity.objects.select_for_update()
            .select_related("requested_sub_service")
            .get(pk=opportunity_id)
        )
        booking = Booking.objects.select_for_update().get(pk=opportunity.booking_id)
        service = eligible_services(opportunity, provider).filter(pk=service_id).first()
        desired_at = _parse_date(booking.desired_date).astimezone(datetime_timezone.utc)
        payout_cents = booking.provider_price_estimate_cents
        if payout_cents is None:
            payout_cents = max(
                0, booking.estimated_price_cents - booking.chateau_rose_fee_cents
            )
        # Canonicalize the legacy fallback once; the total and fee remain unchanged.
        booking.provider_price_estimate_cents = payout_cents
        booking.estimated_price_cents = payout_cents + booking.chateau_rose_fee_cents
        bounty_uc.accept_unchanged_request(
            booking=booking,
            opportunity=opportunity,
            provider_id=provider.id,
            service_id=service_id,
            now=now,
            provider_is_eligible=service is not None,
            service_matches_request=bool(
                service
                and service.marketing_sub_services.filter(
                    pk=opportunity.requested_sub_service_id
                ).exists()
            ),
            desired_at=desired_at,
        )
        _capture_confirmation_payment(booking)
        offer = BookingOffer.objects.create(
            opportunity=opportunity,
            provider=provider,
            service=service,
            proposed_date=booking.desired_date,
            proposed_price_cents=payout_cents,
            status=BookingOffer.STATUS_DIRECTLY_ACCEPTED,
            submitted_at=now,
            client_deadline_at=now,
            decided_at=now,
        )
        opportunity.save(update_fields=("status", "closed_at"))
        booking.save()

    base_url = (
        getattr(settings, "SITE_URL", "") or "https://www.chateau-rose.fr"
    ).rstrip("/")
    manage_url = base_url + reverse(
        "interface:client_confirmation", args=[booking.booking_id]
    )
    details = (
        f"Prestation : {service.name}\nDate : {booking.desired_date}\n"
        f"Lieu : {booking.location or 'Non précisé'}\n"
        f"Tarif prestataire : {payout_cents / 100:.2f} €"
    )
    notifier.notify(
        booking.client_email,
        "Ta demande est confirmée",
        f"Bonjour {booking.client_name},\n\nTa demande est confirmée avec {provider.name}.\n\n"
        f"{details}\n\nGérer ma réservation :\n{manage_url}\n\nÀ bientôt,\nL'équipe Château Rose",
    )
    notifier.notify(
        provider.contact_email,
        "Rendez-vous confirmé",
        f"Bonjour {provider.name},\n\nTu as confirmé la demande {booking.booking_id}.\n\n"
        f"{details}\n\nRetrouve-la dans ton espace prestataire.\n\nÀ bientôt,\nL'équipe Château Rose",
    )
    return booking, offer


def decide(*, token, decision, now=None):
    now = now or timezone.now()
    try:
        payload = signing.loads(token, salt="bounty-client", max_age=6 * 24 * 3600)
    except signing.BadSignature as exc:
        raise InvalidState("Lien de proposition invalide ou expiré.") from exc
    with transaction.atomic():
        offer = (
            BookingOffer.objects.select_for_update()
            .select_related("opportunity__booking")
            .get(pk=payload["offer"])
        )
        booking = Booking.objects.select_for_update().get(
            pk=offer.opportunity.booking_id
        )
        bounty_uc.decide_offer(booking=booking, offer=offer, decision=decision, now=now)
        if decision == "accept":
            _capture_confirmation_payment(booking)
        else:
            if booking.payment_auth_id:
                payments.release_auth(booking.payment_auth_id)
                booking.payment_status = Booking.PAYMENT_STATUS_RELEASED
        offer.save(update_fields=("status", "decided_at"))
        booking.save()
    notifier.notify(
        offer.provider.contact_email,
        "Proposition acceptée" if decision == "accept" else "Proposition refusée",
        f"Bonjour {offer.provider.name},\n\n"
        f"Ta proposition pour la demande {booking.booking_id} a été "
        f"{'acceptée' if decision == 'accept' else 'refusée'}.\n\n"
        + (
            "Tu peux retrouver les informations du rendez-vous dans ton espace prestataire."
            if decision == "accept"
            else "Merci d'avoir pris le temps de répondre à cette demande."
        )
        + "\n\nÀ bientôt,\nL'équipe Château Rose",
    )
    return booking, offer
