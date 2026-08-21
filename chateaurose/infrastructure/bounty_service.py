from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from booking.models import Booking, BookingOffer, BookingOpportunity, Provider, Service
from chateaurose.domain.exceptions import DomainError, InvalidState, ValidationError
from chateaurose.domain.services.booking_deadlines import bounded_deadline
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
        booking = (
            Booking.objects.select_for_update()
            .select_related("service", "requested_marketing_sub_service")
            .get(booking_id=booking_id)
        )
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
                "Le service n'est lié exactement à aucun sous-service marketing. La demande a été annulée.",
            )
            notifier.notify(
                booking.client_email,
                "Demande annulée",
                "Aucune autre prestataire compatible n'a pu être recherchée. Ton autorisation de paiement a été libérée.",
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
                "Nous n'avons trouvé aucune autre prestataire proposant cette prestation. Ton autorisation de paiement a été libérée.",
            )
            return opportunity
    providers = {service.provider_id: service.provider for service in services}
    for provider in providers.values():
        url = f"{base_url}{reverse('providers:bounty_offer', args=[opportunity.id])}"
        notifier.notify(
            provider.contact_email,
            f"Une demande de {sub_service.name} est disponible",
            f"{booking.client_name} cherche une prestataire pour {sub_service.name}, le {booking.desired_date}. Si tu souhaites proposer de la prendre en charge : {url}\nUne autre prestataire pourra répondre avant toi.",
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
        f"{provider.name} propose le {proposed_date}, pour {cents / 100:.2f} € à régler le jour J. Profil : {profile_url}\nAccepter ou refuser : {url}\nLes frais Château Rose déjà traités ne changent pas.",
    )
    return offer


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
            if booking.payment_auth_id and booking.amount_due_now_cents > 0:
                payments.capture_auth(booking.payment_auth_id)
                booking.payment_status = Booking.PAYMENT_STATUS_CAPTURED
        else:
            if booking.payment_auth_id:
                payments.release_auth(booking.payment_auth_id)
                booking.payment_status = Booking.PAYMENT_STATUS_RELEASED
        offer.save(update_fields=("status", "decided_at"))
        booking.save()
    notifier.notify(
        offer.provider.contact_email,
        "Proposition acceptée" if decision == "accept" else "Proposition refusée",
        f"La proposition pour la demande {booking.booking_id} a été {'acceptée' if decision == 'accept' else 'refusée'}.",
    )
    return booking, offer
