from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from booking.models import Booking, Provider
from chateaurose.domain.exceptions import DomainError
from chateaurose.domain.use_cases import finalize_booking as finalize_booking_uc, update_proposal
from chateaurose.infrastructure.booking_repository import DjangoBookingRepository
from chateaurose.infrastructure.stripe_gateway import StripePaymentGateway
from chateaurose.infrastructure.twilio_notifier import TwilioNotifier
from providers.forms import ProviderSignupForm

repo = DjangoBookingRepository()
notifier = TwilioNotifier()
payment_gateway = StripePaymentGateway()


def _parse_price_to_cents(raw_value: str) -> int:
    if raw_value is None:
        raise DomainError("Le tarif proposé doit être renseigné.")

    normalized = raw_value.replace(",", ".")
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
    try:
        provider = Provider.objects.get(user=request.user)
    except Provider.DoesNotExist:
        return HttpResponseForbidden("Accès réservé aux prestataires enregistrés.")

    bookings = (
        Booking.objects.filter(provider=provider)
        .order_by("-created_at")
        .select_related("service")
    )

    return render(
        request,
        "providers/index.html",
        {
            "provider": provider,
            "bookings": bookings,
        },
    )


@login_required(login_url="providers:login")
def booking_detail(request, booking_id):
    try:
        provider = Provider.objects.get(user=request.user)
    except Provider.DoesNotExist:
        return HttpResponseForbidden("Accès réservé aux prestataires enregistrés.")

    booking = get_object_or_404(
        Booking.objects.select_related("service", "provider"),
        booking_id=booking_id,
        provider=provider,
    )

    message = None
    error = None

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "propose":
                price_cents = _parse_price_to_cents(
                    request.POST.get("proposed_price_euros")
                )
                proposed_date = request.POST.get("proposed_date")
                update_proposal.execute(
                    booking_id=booking.booking_id,
                    provider_id=provider.id,
                    new_price_cents=price_cents,
                    new_date=proposed_date,
                    now=timezone.now(),
                    booking_repository=repo,
                    notifier=notifier,
                )
                message = "Proposition envoyée au client."
            elif action in ("confirm", "reject"):
                finalize_booking_uc.execute(
                    booking_id=booking.booking_id,
                    actor="provider",
                    decision=action,
                    now=timezone.now(),
                    booking_repository=repo,
                    payment_gateway=payment_gateway,
                    notifier=notifier,
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
        },
    )


def signup(request):
    if request.method == "POST":
        form = ProviderSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            Provider.objects.create(
                name=form.cleaned_data["name"],
                contact_email=form.cleaned_data.get("contact_email")
                or form.cleaned_data.get("email"),
                contact_phone=form.cleaned_data.get("contact_phone", ""),
                location_mode=form.cleaned_data.get("location_mode", Provider.LOCATION_MODE_HYBRID),
                user=user,
            )
            login(request, user)
            return redirect("providers:providers_index")
    else:
        form = ProviderSignupForm()

    return render(request, "providers/signup.html", {"form": form})
