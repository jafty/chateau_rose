from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import logging

from django import forms
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.urls import reverse_lazy

from booking.models import Booking, Provider, ProviderPhoto, Service
from chateaurose.domain.exceptions import DomainError
from chateaurose.domain.use_cases import (
    expire_booking as expire_booking_uc,
    finalize_booking as finalize_booking_uc,
    update_proposal,
)
from chateaurose.infrastructure.booking_repository import DjangoBookingRepository
from chateaurose.domain.services.pricing import (
    ceil_price_for_display_cents,
    compute_checkout_amounts_from_total_cents,
    floor_price_for_display_cents,
)
from chateaurose.infrastructure.email_notifier import EmailNotifier
from chateaurose.infrastructure.provider_directory import DjangoProviderDirectory
from chateaurose.infrastructure.stripe_gateway import StripePaymentGateway
from providers.forms import (
    ProviderBlockedSlotForm,
    ProviderInfoForm,
    ProviderPartnershipRequestForm,
    ProviderPasswordResetForm,
    ProviderPhotoForm,
    ProviderServiceForm,
)

repo = DjangoBookingRepository()
notifier = EmailNotifier()
payment_gateway = StripePaymentGateway()
provider_directory = DjangoProviderDirectory()
logger = logging.getLogger(__name__)
SUPPORT_EMAIL = (getattr(settings, "OPERATIONS_EMAIL", "") or "japhet.situmonana@gmail.com").strip()


def _expire_visible_open_bookings(*, bookings, now):
    for booking in bookings:
        expire_booking_uc.execute(
            booking_id=booking.booking_id,
            now=now,
            booking_repository=repo,
            payment_gateway=payment_gateway,
            notifier=notifier,
        )


def _format_price_from_cents(amount_cents: int) -> str:
    euros = Decimal(amount_cents) / Decimal("100")
    return f"{euros:.2f}".replace(".", ",") + " €"


def _payment_summary(booking) -> dict:
    effective_total_cents = booking.proposed_price_cents if booking.proposed_price_cents is not None else booking.estimated_price_cents
    deposit_percentage = booking.provider.deposit_percentage if booking.provider.deposit_percentage is not None else 30
    service_fee_percentage = booking.provider.service_fee_percentage if booking.provider.service_fee_percentage is not None else 0
    checkout_amounts = compute_checkout_amounts_from_total_cents(
        total_cents=effective_total_cents,
        deposit_percentage=deposit_percentage,
        service_fee_percentage=service_fee_percentage,
    )
    computed_reservation_fee_cents = checkout_amounts["reservation_fee_cents"]
    reservation_fee_cents = (
        booking.locked_reservation_fee_cents
        if booking.locked_reservation_fee_cents is not None
        else computed_reservation_fee_cents
    )
    service_fee_cents = checkout_amounts["service_fee_cents"]
    deposit_cents = max(reservation_fee_cents - service_fee_cents, 0)
    displayed_deposit_cents = ceil_price_for_display_cents(deposit_cents)
    displayed_reservation_fee_cents = service_fee_cents + displayed_deposit_cents
    displayed_remaining_cents = floor_price_for_display_cents(
        max(effective_total_cents - displayed_reservation_fee_cents, 0)
    )
    return {
        "total": _format_price_from_cents(effective_total_cents),
        "reservation_fee": _format_price_from_cents(displayed_reservation_fee_cents),
        "service_fee": _format_price_from_cents(service_fee_cents),
        "deposit": _format_price_from_cents(displayed_deposit_cents),
        "remaining": _format_price_from_cents(displayed_remaining_cents),
    }


class ProviderPasswordResetView(auth_views.PasswordResetView):
    success_url = reverse_lazy("providers:password_reset_done")
    form_class = ProviderPasswordResetForm

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except Exception:
            logger.exception("Failed to send provider password reset email.")
            return HttpResponseRedirect(self.get_success_url())


def _parse_price_to_cents(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None

    normalized = raw_value.replace(",", ".").strip()
    if not normalized:
        return None
    try:
        euros = Decimal(normalized)
    except (InvalidOperation, TypeError):
        raise DomainError("Le tarif proposé doit être un nombre.")

    cents = int((euros * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if cents < 0:
        raise DomainError("Le tarif proposé doit être positif.")
    return cents


@login_required(login_url="providers:login")
def index(request):
    provider = Provider.objects.filter(user=request.user).first()
    admin_mode = provider is None and request.user.is_staff
    if provider is None and not admin_mode:
        return HttpResponseForbidden("Accès réservé aux prestataires enregistrés.")

    if admin_mode:
        open_bookings = Booking.objects.filter(
            status__in=(expire_booking_uc.SUBMITTED, expire_booking_uc.PENDING_CLIENT_VALIDATION)
        )
    else:
        open_bookings = Booking.objects.filter(
            provider=provider,
            status__in=(expire_booking_uc.SUBMITTED, expire_booking_uc.PENDING_CLIENT_VALIDATION),
        )

    _expire_visible_open_bookings(bookings=open_bookings.iterator(), now=timezone.now())

    if admin_mode:
        bookings = Booking.objects.order_by("-created_at").select_related("service", "provider")
    else:
        bookings = (
            Booking.objects.filter(provider=provider)
            .order_by("-created_at")
            .select_related("service", "provider")
        )

    return render(
        request,
        "providers/index.html",
        {
            "provider": provider,
            "bookings": bookings,
            "admin_mode": admin_mode,
        },
    )


@login_required(login_url="providers:login")
def booking_detail(request, booking_id):
    provider = Provider.objects.filter(user=request.user).first()
    admin_mode = provider is None and request.user.is_staff
    if provider is None and not admin_mode:
        return HttpResponseForbidden("Accès réservé aux prestataires enregistrés.")

    booking_query = Booking.objects.select_related("service", "provider")
    if admin_mode:
        booking = get_object_or_404(booking_query, booking_id=booking_id)
    else:
        booking = get_object_or_404(
            booking_query,
            booking_id=booking_id,
            provider=provider,
        )

    acting_provider = booking.provider if admin_mode else provider

    if booking.status in (expire_booking_uc.SUBMITTED, expire_booking_uc.PENDING_CLIENT_VALIDATION):
        expire_booking_uc.execute(
            booking_id=booking.booking_id,
            now=timezone.now(),
            booking_repository=repo,
            payment_gateway=payment_gateway,
            notifier=notifier,
        )
        booking.refresh_from_db()

    message = None
    error = None

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "propose":
                price_cents = _parse_price_to_cents(
                    request.POST.get("proposed_price_euros")
                )
                raw_date = request.POST.get("proposed_date", "")
                proposed_date = raw_date.strip() or None
                counter_proposal_message = request.POST.get("counter_proposal_message", "").strip() or None
                client_control_url = request.build_absolute_uri(
                    reverse("interface:client_proposal", args=[booking.booking_id])
                )
                update_proposal.execute(
                    booking_id=booking.booking_id,
                    provider_id=acting_provider.id,
                    new_price_cents=price_cents,
                    new_date=proposed_date,
                    now=timezone.now(),
                    booking_repository=repo,
                    notifier=notifier,
                    provider_directory=provider_directory,
                    client_control_url=client_control_url,
                    counter_proposal_message=counter_proposal_message,
                    reply_to_email=acting_provider.contact_email or SUPPORT_EMAIL,
                )
                message = "Proposition envoyée à la personne cliente."
            elif action in ("confirm", "reject"):
                finalize_booking_uc.execute(
                    booking_id=booking.booking_id,
                    actor="provider",
                    decision=action,
                    now=timezone.now(),
                    booking_repository=repo,
                    payment_gateway=payment_gateway,
                    provider_directory=provider_directory,
                    notifier=notifier,
                    operations_email=SUPPORT_EMAIL,
                )
                message = "Décision enregistrée."
            else:
                return HttpResponseBadRequest("Action non reconnue")
        except DomainError as exc:
            error = str(exc)

        booking.refresh_from_db()

    return render(
        request,
        "providers/booking_detail.html",
        {
            "provider": provider,
            "booking": booking,
            "message": message,
            "error": error,
            "payment_summary": _payment_summary(booking),
            "admin_mode": admin_mode,
        },
    )


def signup(request):
    request_sent = request.GET.get("sent") == "1"
    if request.method == "POST":
        form = ProviderPartnershipRequestForm(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            subject = "Nouvelle demande de partenariat"
            body = "\n".join(
                [
                    "Une nouvelle demande de partenariat a été envoyée.",
                    "",
                    f"Nom : {cleaned['name']}",
                    f"Email : {cleaned['email']}",
                    f"Instagram / réseau social : {cleaned.get('social') or 'Non renseigné'}",
                    "",
                    "Message :",
                    cleaned["message"],
                ]
            )
            notifier.notify(
                recipient=SUPPORT_EMAIL,
                subject=subject,
                body=body,
                reply_to=cleaned["email"],
            )
            return redirect(f"{reverse('providers:signup')}?sent=1")
    else:
        form = ProviderPartnershipRequestForm()

    return render(
        request,
        "providers/signup.html",
        {"form": form, "request_sent": request_sent},
    )


def _adjustments_from_post(request, prefix: str) -> dict:
    labels = request.POST.getlist(f"{prefix}_label[]")
    prices = request.POST.getlist(f"{prefix}_price[]")
    adjustments = {}
    for raw_label, raw_price in zip(labels, prices):
        label = (raw_label or "").strip()
        price = (raw_price or "").strip()
        if not label and not price:
            continue
        if not label and price:
            raise DomainError("Ajoute un intitulé pour le supplément saisi.")
        if not label:
            continue
        try:
            cents = ProviderServiceForm._euros_to_cents(raw_price)
        except forms.ValidationError as exc:
            raise DomainError(exc.messages[0])
        adjustments[label] = cents
    return adjustments


@login_required(login_url="providers:login")
def account(request):
    provider = Provider.objects.filter(user=request.user).first()
    if provider is None:
        return HttpResponseForbidden("Accès réservé aux prestataires enregistrés.")

    info_form = ProviderInfoForm(instance=provider)
    blocked_slot_form = ProviderBlockedSlotForm()
    photo_form = ProviderPhotoForm()
    new_service_form = ProviderServiceForm()
    message = None
    error = None

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "save_info":
                info_form = ProviderInfoForm(request.POST, instance=provider)
                if info_form.is_valid():
                    info_form.save()
                    message = "Informations mises à jour."
                else:
                    error = "Merci de corriger les champs informations."
            elif action == "save_service":
                service = get_object_or_404(Service, id=request.POST.get("service_id"), provider=provider)
                service_form = ProviderServiceForm(request.POST, request.FILES, instance=service)
                if service_form.is_valid():
                    service = service_form.save(commit=False)
                    service.hair_length_adjustments = _adjustments_from_post(request, "hair")
                    service.general_adjustments = _adjustments_from_post(request, "general")
                    service.save()
                    message = f"Service « {service.name} » mis à jour."
                else:
                    first_error = next(iter(service_form.errors.values()))[0] if service_form.errors else "Merci de corriger les champs du service."
                    error = f"Service « {service.name} » : {first_error}"
            elif action == "add_service":
                new_service_form = ProviderServiceForm(request.POST, request.FILES)
                if new_service_form.is_valid():
                    service = new_service_form.save(commit=False)
                    service.provider = provider
                    service.hair_length_adjustments = _adjustments_from_post(request, "new_hair")
                    service.general_adjustments = _adjustments_from_post(request, "new_general")
                    service.save()
                    new_service_form = ProviderServiceForm()
                    message = f"Service « {service.name} » ajouté."
                else:
                    error = "Merci de corriger les champs du nouveau service."
            elif action == "add_blocked_slot":
                blocked_slot_form = ProviderBlockedSlotForm(request.POST)
                if blocked_slot_form.is_valid():
                    slot = blocked_slot_form.save(commit=False)
                    slot.provider = provider
                    slot.save()
                    blocked_slot_form = ProviderBlockedSlotForm()
                    message = "Créneau ponctuel indisponible ajouté."
                else:
                    error = "Merci de corriger les dates du créneau indisponible."
            elif action == "delete_blocked_slot":
                slot = get_object_or_404(provider.blocked_slots.filter(is_recurring=False), id=request.POST.get("slot_id"))
                slot.delete()
                message = "Créneau ponctuel supprimé."
            elif action == "add_photo":
                photo_form = ProviderPhotoForm(request.POST, request.FILES)
                if photo_form.is_valid():
                    photo = photo_form.save(commit=False)
                    photo.provider = provider
                    photo.save()
                    photo_form = ProviderPhotoForm()
                    message = "Média ajouté."
                else:
                    error = "Merci de corriger le média à ajouter."
            elif action == "delete_photo":
                photo = get_object_or_404(provider.photos, id=request.POST.get("photo_id"))
                photo.delete()
                message = "Média supprimé."
        except (DomainError, InvalidOperation) as exc:
            error = str(exc)

    services = provider.services.order_by("name")
    service_forms = []
    invalid_service_id = request.POST.get("service_id") if request.method == "POST" else None
    for service in services:
        if request.method == "POST" and request.POST.get("action") == "save_service" and str(service.id) == str(invalid_service_id):
            form = ProviderServiceForm(request.POST, request.FILES, instance=service)
        else:
            form = ProviderServiceForm(instance=service)
        service_forms.append((service, form))

    blocked_slots = provider.blocked_slots.filter(is_recurring=False, is_active=True).order_by("starts_at")
    photos = provider.photos.order_by("order", "id")

    return render(
        request,
        "providers/account.html",
        {
            "provider": provider,
            "message": message,
            "error": error,
            "info_form": info_form,
            "service_forms": service_forms,
            "blocked_slot_form": blocked_slot_form,
            "blocked_slots": blocked_slots,
            "photo_form": photo_form,
            "photos": photos,
            "new_service_form": new_service_form,
        },
    )
