from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import logging

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.urls import reverse_lazy

from booking.models import Booking, Provider
from chateaurose.domain.exceptions import DomainError
from chateaurose.domain.use_cases import finalize_booking as finalize_booking_uc, update_proposal
from chateaurose.infrastructure.booking_repository import DjangoBookingRepository
from chateaurose.infrastructure.email_notifier import EmailNotifier
from chateaurose.infrastructure.provider_directory import DjangoProviderDirectory
from chateaurose.infrastructure.stripe_gateway import StripePaymentGateway
from providers.forms import ProviderPartnershipRequestForm, ProviderPasswordResetForm

repo = DjangoBookingRepository()
notifier = EmailNotifier()
payment_gateway = StripePaymentGateway()
provider_directory = DjangoProviderDirectory()
logger = logging.getLogger(__name__)


def _format_price_from_cents(amount_cents: int) -> str:
    euros = Decimal(amount_cents) / Decimal("100")
    return f"{euros:.2f}".replace(".", ",") + " €"


def _payment_summary(booking) -> dict:
    effective_total_cents = booking.proposed_price_cents if booking.proposed_price_cents is not None else booking.estimated_price_cents
    deposit_percentage = booking.provider.deposit_percentage or 30
    reservation_fee_cents = int((Decimal(effective_total_cents) * Decimal(deposit_percentage) / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    remaining_cents = max(effective_total_cents - reservation_fee_cents, 0)
    return {
        "total": _format_price_from_cents(effective_total_cents),
        "reservation_fee": _format_price_from_cents(reservation_fee_cents),
        "remaining": _format_price_from_cents(remaining_cents),
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
                recipient="japhet.situmonana@gmail.com",
                subject=subject,
                body=body,
            )
            return redirect(f"{reverse('providers:signup')}?sent=1")
    else:
        form = ProviderPartnershipRequestForm()

    return render(
        request,
        "providers/signup.html",
        {"form": form, "request_sent": request_sent},
    )
