import json
import logging
import uuid
from datetime import datetime

from django import forms
from django.contrib.auth.decorators import login_required
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from django.urls import reverse

from booking.models import (
    Booking,
    Provider,
    ProviderBeforeAppointmentItem,
    ProviderServiceFeeCoupon,
    Service,
    ServiceCategory,
    Zone,
)
from chateaurose.domain.exceptions import DomainError, ValidationError
from chateaurose.domain.services.marketing_content import GalleryImage, ServiceContent, build_marketing_content
from chateaurose.domain.services.pricing import (
    ceil_price_for_display_cents,
    compute_checkout_amounts_cents,
    compute_service_fee_only_amounts_cents,
    compute_checkout_amounts_from_total_cents,
    estimate_service_price_cents,
    floor_price_for_display_cents,
)
from chateaurose.domain.use_cases import expire_booking as expire_booking_uc
from chateaurose.domain.use_cases import finalize_booking as finalize_booking_uc
from chateaurose.domain.use_cases import create_booking_request, prepare_booking_recap, request_haircut, update_proposal
from chateaurose.infrastructure.booking_repository import DjangoBookingRepository
from chateaurose.infrastructure.stripe_gateway import StripePaymentGateway
from chateaurose.infrastructure.email_notifier import EmailNotifier
from chateaurose.infrastructure.provider_directory import DjangoProviderDirectory
from chateaurose.infrastructure.provider_catalog import (
    DjangoProviderCatalog,
    SALON_LOCATION_LABEL,
)
from interface.forms import GenericBookingRequestForm, ProviderBookingRequestForm, ProviderQuestionForm, ServiceRequestForm
from interface.marketing_cities import CITY_PAGE_COPY, MARKETING_CITY_ENTRIES
from interface.models import (
    ClientReview,
    MarketingService,
    MarketingSubService,
    MarketingServiceZone,
    MarketingZone,
    ProviderBookingDraft,
    QuickCheckoutPage,
    ServiceRequest,
    Interaction,
)
from interface.services import booking_requests
from chateaurose.seo import build_base_url

logger = logging.getLogger(__name__)

repo = DjangoBookingRepository()
notifier = EmailNotifier()
payment_gateway = StripePaymentGateway()
provider_catalog = DjangoProviderCatalog()
provider_directory = DjangoProviderDirectory()


FEATURED_SERVICE_SLUGS = ["tresses", "locks", "tissage", "vanilles"]
SUPPORT_EMAIL = (getattr(settings, "OPERATIONS_EMAIL", "") or "japhet.situmonana@gmail.com").strip()
SUPPORT_PHONE_DISPLAY = "+33 6 49 49 14 49"
SUPPORT_PHONE_TEL = "+33649491449"


def _provider_coupon_is_valid(provider: Provider, code: str | None) -> bool:
    normalized_code = (code or "").strip().upper()
    if not normalized_code:
        return False
    return ProviderServiceFeeCoupon.objects.filter(
        provider=provider,
        is_active=True,
        code=normalized_code,
    ).exists()


def _create_interaction(
    *,
    kind: str,
    source_label: str,
    contact_name: str = "",
    contact_email: str = "",
    contact_phone: str = "",
    subject: str = "",
    message: str = "",
    next_action: str = "",
    metadata: dict | None = None,
    service_request: ServiceRequest | None = None,
) -> None:
    Interaction.objects.create(
        kind=kind,
        source_label=source_label,
        contact_name=contact_name,
        contact_email=contact_email,
        contact_phone=contact_phone,
        subject=subject,
        message=message,
        next_action=next_action,
        metadata=metadata or {},
        service_request=service_request,
    )


def _notify_provider_question(provider: Provider, question_form: ProviderQuestionForm) -> None:
    client_name = question_form.cleaned_data["client_name"]
    client_email = question_form.cleaned_data["client_email"]
    message = question_form.cleaned_data["message"]

    email_subject = f"Question depuis le profil de {provider.name}"
    body_lines = [
        f"Prestataire : {provider.name}",
        f"Client·e : {client_name} ({client_email})",
        "Destinataire : Château Rose",
        "",
        "Question :",
        message,
    ]
    _create_interaction(
        kind=Interaction.KIND_PROVIDER_QUESTION,
        source_label=f"Profil prestataire · {provider.name}",
        contact_name=client_name,
        contact_email=client_email,
        subject=email_subject,
        message=message,
        next_action="Répondre à la question client",
        metadata={"provider_id": provider.id, "provider_name": provider.name},
    )

    notifier.notify(
        SUPPORT_EMAIL,
        email_subject,
        "\n".join(body_lines),
        reply_to=client_email,
    )


def _first_form_error(form: forms.Form) -> str | None:
    non_field_errors = form.non_field_errors()
    if non_field_errors:
        return non_field_errors[0]
    for field_errors in form.errors.values():
        if field_errors:
            return field_errors[0]
    return None


def _friendly_domain_error_message(error: DomainError) -> str:
    raw = str(error)
    if "Selected slot is unavailable" in raw:
        return "Ce créneau n'est plus disponible. Choisis un autre horaire."
    return raw


def _release_payment_auth_safely(payment_auth_id: str | None) -> None:
    auth_id = (payment_auth_id or "").strip()
    if not auth_id:
        return
    try:
        payment_gateway.release_auth(auth_id)
    except Exception:
        logger.exception("Failed to release payment auth %s after booking failure", auth_id)


def _mark_recap_completed_if_needed(recap_token: str | None) -> None:
    token_value = (recap_token or "").strip()
    if not token_value:
        return
    draft = ProviderBookingDraft.objects.filter(token=token_value).first()
    if draft is None or draft.completed_at:
        return
    draft.completed_at = timezone.now()
    draft.save(update_fields=["completed_at", "updated_at"])


def _build_recap_email_body(*, provider: Provider, recap_url: str, payload: dict) -> str:
    lines = [
        f"Salut {payload.get('client_name', '').strip() or 'à toi'} 👋",
        "",
        "Ton récapitulatif est prêt.",
        "Tu peux revenir dessus à tout moment via ce lien :",
        recap_url,
        "",
        "Résumé :",
        f"- Prestataire : {provider.name}",
        f"- Prestation : {payload.get('service_name', '')}",
        f"- Date souhaitée : {payload.get('desired_date', '')}",
        f"- Lieu : {'Chez la prestataire' if payload.get('location_preference') == 'salon' else 'À domicile'}",
    ]
    if payload.get("location_preference") == "domicile":
        lines.append(f"- Adresse : {payload.get('client_address', '')}")
    lines.extend(
        [
            "",
            "Tu peux soit modifier ta demande, soit confirmer depuis ce même lien.",
        ]
    )
    return "\n".join(lines)


def _build_provider_booking_recap_payload(*, provider: Provider, form: ProviderBookingRequestForm) -> dict:
    current_hair_picture_file = form.cleaned_data.get("current_hair_picture_file")
    if current_hair_picture_file:
        current_picture = booking_requests.save_current_hair_picture(current_hair_picture_file)
    else:
        current_picture = (form.cleaned_data.get("current_hair_picture") or "").strip()

    stored_inspiration_pictures = booking_requests.save_inspiration_pictures(form.get_inspiration_files())
    if not stored_inspiration_pictures:
        stored_inspiration_pictures = form.cleaned_data.get("existing_inspiration_pictures") or []

    service = Service.objects.filter(provider=provider, id=form.cleaned_data.get("service_id")).first()
    if service is None:
        raise ValidationError("Service non disponible.")

    return prepare_booking_recap.execute(
        provider_id=provider.id,
        service_id=form.cleaned_data.get("service_id"),
        service_name=service.name,
        client_name=form.cleaned_data.get("client_name"),
        client_email=form.cleaned_data.get("client_email"),
        desired_date_iso=form.cleaned_data.get("desired_date"),
        location_preference=form.cleaned_data.get("location_preference"),
        location=form.cleaned_data.get("location"),
        client_address=form.cleaned_data.get("client_address"),
        hair_length=form.cleaned_data.get("hair_length"),
        general_adjustments=form.cleaned_data.get("general_adjustments", []),
        meche=form.cleaned_data.get("meche", False),
        free_text=form.cleaned_data.get("free_text", ""),
        service_fee_coupon_code=form.cleaned_data.get("service_fee_coupon_code", ""),
        current_hair_picture=current_picture,
        inspiration_pictures=stored_inspiration_pictures,
    )


def _create_provider_booking_recap(
    *,
    request,
    provider: Provider,
    form: ProviderBookingRequestForm,
    source: str = ProviderBookingDraft.SOURCE_CLIENT,
    created_by=None,
):
    recap_payload = _build_provider_booking_recap_payload(provider=provider, form=form)
    draft = ProviderBookingDraft.objects.create(
        provider=provider,
        source=source,
        created_by=created_by,
        client_email=recap_payload["client_email"],
        client_name=recap_payload["client_name"],
        payload=recap_payload,
    )
    recap_url = request.build_absolute_uri(
        reverse("interface:provider_booking_recap", args=[str(draft.token)])
    )
    notifier.notify(
        recap_payload["client_email"],
        "Ton récapitulatif est prêt",
        _build_recap_email_body(provider=provider, recap_url=recap_url, payload=recap_payload),
    )
    return draft


def _update_provider_booking_recap(*, provider: Provider, form: ProviderBookingRequestForm, draft: ProviderBookingDraft):
    recap_payload = _build_provider_booking_recap_payload(provider=provider, form=form)
    draft.client_email = recap_payload["client_email"]
    draft.client_name = recap_payload["client_name"]
    draft.payload = recap_payload
    draft.save(update_fields=["client_email", "client_name", "payload", "updated_at"])
    return draft


def _save_partial_provider_booking_recap_prefill(*, provider: Provider, form: ProviderBookingRequestForm, draft: ProviderBookingDraft):
    payload = dict(draft.payload or {})
    service = Service.objects.filter(provider=provider, id=form.cleaned_data.get("service_id")).first()
    if service is None:
        raise ValidationError("Service non disponible.")

    current_hair_picture_file = form.cleaned_data.get("current_hair_picture_file")
    if current_hair_picture_file:
        current_picture = booking_requests.save_current_hair_picture(current_hair_picture_file)
    else:
        current_picture = (form.cleaned_data.get("current_hair_picture") or payload.get("current_hair_picture") or "").strip()

    stored_inspiration_pictures = booking_requests.save_inspiration_pictures(form.get_inspiration_files())
    if not stored_inspiration_pictures:
        stored_inspiration_pictures = form.cleaned_data.get("existing_inspiration_pictures") or payload.get("inspiration_pictures") or []

    payload.update(
        {
            "provider_id": str(provider.id),
            "service_id": str(form.cleaned_data.get("service_id")),
            "service_name": service.name,
            "client_name": (form.cleaned_data.get("client_name") or payload.get("client_name") or "").strip(),
            "client_email": (form.cleaned_data.get("client_email") or payload.get("client_email") or "").strip(),
            "desired_date": (form.cleaned_data.get("desired_date") or payload.get("desired_date") or "").strip(),
            "location_preference": (form.cleaned_data.get("location_preference") or payload.get("location_preference") or "").strip(),
            "location": (form.cleaned_data.get("location") or payload.get("location") or "").strip(),
            "client_address": (form.cleaned_data.get("client_address") or payload.get("client_address") or "").strip(),
            "hair_length": (form.cleaned_data.get("hair_length") or payload.get("hair_length") or "").strip(),
            "general_adjustments": form.cleaned_data.get("general_adjustments") or [],
            "meche": bool(form.cleaned_data.get("meche")),
            "free_text": (form.cleaned_data.get("free_text") or payload.get("free_text") or "").strip(),
            "service_fee_coupon_code": (
                form.cleaned_data.get("service_fee_coupon_code")
                or payload.get("service_fee_coupon_code")
                or ""
            ).strip().upper(),
            "current_hair_picture": current_picture,
            "inspiration_pictures": stored_inspiration_pictures,
        }
    )

    draft.client_email = payload.get("client_email", "")
    draft.client_name = payload.get("client_name", "")
    draft.payload = payload
    draft.save(update_fields=["client_email", "client_name", "payload", "updated_at"])
    return draft


def _provider_configuration_blocks_salon_booking(provider: Provider, location_preference: str | None) -> bool:
    requested_preference = (location_preference or "").strip()
    is_salon_request = requested_preference == "salon" or provider.location_mode == Provider.LOCATION_MODE_SALON_ONLY
    if not is_salon_request:
        return False
    return not provider.salon_zone or not provider.salon_address


def _complete_quick_checkout(checkout: QuickCheckoutPage, payment_auth_id: str):
    provider = checkout.provider
    client_address_value = (checkout.client_address or "").strip()
    if checkout.location_preference == "domicile" and not client_address_value:
        raise DomainError("Missing client address for domicile quick checkout")

    booking_detail_path = reverse("providers:booking_detail", args=["BOOKING_ID"])
    provider_booking_url_base = booking_detail_path.replace("BOOKING_ID/", "")
    hair_length_value = (checkout.hair_length or "").strip()
    supported_lengths = set((checkout.service.hair_length_adjustments or {}).keys())
    if hair_length_value and supported_lengths and hair_length_value not in supported_lengths:
        hair_length_value = ""

    booking = request_haircut.execute(
        provider_id=str(provider.id),
        service_id=checkout.service_id,
        client_contact={
            "name": checkout.client_name,
            "email": checkout.client_email,
        },
        location=(provider.salon_zone or "Salon") if checkout.location_preference == "salon" else client_address_value,
        location_preference=checkout.location_preference,
        client_address=client_address_value,
        desired_date=checkout.desired_date.isoformat(),
        hair_length=hair_length_value,
        general_adjustments=[],
        meche=False,
        current_hair_picture="quick-checkout",
        require_current_hair_picture=False,
        skip_coverage_validation=True,
        inspiration_pictures=[],
        free_text=checkout.free_text,
        payment_auth_id=payment_auth_id,
        provider_booking_url_base=provider_booking_url_base,
        provider_salon_zone=provider.salon_zone,
        booking_repository=repo,
        provider_catalog=provider_catalog,
        payment_gateway=payment_gateway,
        notifier=notifier,
        reminder_gateway=None,
        clock=type("Clock", (), {"now": timezone.now}),
        send_submission_notifications=False,
        operations_email=SUPPORT_EMAIL,
    )

    booking_row = Booking.objects.filter(booking_id=booking.id).first()
    if booking_row:
        booking_row.estimated_price_cents = checkout.final_price_cents
        booking_row.save(update_fields=["estimated_price_cents", "updated_at"])

    checkout.completed_at = timezone.now()
    checkout.is_active = False
    checkout.save(update_fields=["completed_at", "is_active", "updated_at"])

    notifier.notify(
        provider.id,
        "Nouvelle demande à confirmer",
        "\n".join(
            [
                "Une demande rapide a été sécurisée (frais Château Rose traités).",
                "Le créneau n'est pas encore confirmé : confirme manuellement depuis ton espace.",
                f"Client·e : {checkout.client_name} ({checkout.client_email})",
                f"Prestation : {checkout.service.name}",
                f"Date : {checkout.desired_date.isoformat()}",
                f"ID demande : {booking.id}",
            ]
        ),
    )
    client_confirmation_lines = [
        f"Merci {checkout.client_name} ! Ta demande pour {checkout.service.name} est bien enregistrée.",
        "Tes frais Château Rose sont traités, mais le rendez-vous reste en attente de confirmation.",
        "",
        "Récapitulatif :",
        f"- Prestation : {checkout.service.name}",
        f"- Date demandée : {checkout.desired_date.isoformat()}",
        f"- Frais Château Rose : {booking_requests.format_price(checkout.reservation_fee_cents)}",
        f"- Reste à payer le jour J : {booking_requests.format_price(max(checkout.final_price_cents - checkout.reservation_fee_cents, 0))}",
        f"- ID demande : {booking.id}",
    ]
    notifier.notify(
        checkout.client_email,
        "Demande en attente de confirmation",
        "\n".join(client_confirmation_lines),
    )

    return booking


def home(request):
    providers = Provider.objects.visible_on_website().order_by("homepage_order", "id")
    zones = Zone.objects.all()
    services = list(
        MarketingService.objects.filter(is_visible_on_homepage=True).order_by(
            "homepage_order",
            "name",
            "id",
        )
    )
    services_by_slug = {service.slug: service for service in services}
    featured_services = []
    for slug in FEATURED_SERVICE_SLUGS:
        service = services_by_slug.get(slug)
        if service:
            featured_services.append(service)
    if len(featured_services) < 4:
        for service in services:
            if service not in featured_services and len(featured_services) < 4:
                featured_services.append(service)
    service_request_redirect = _build_service_request_redirect(request)
    if service_request_redirect:
        return service_request_redirect

    request_form, request_success = _build_service_request_form(request, service_meta=None, zone=None)
    if request_form == "redirect":
        return redirect("interface:thank_you_quick_request")
    if request_form is None:
        return redirect(f"{request.path}?anchor=service-request")
    homepage_reviews = _get_homepage_reviews()
    city_links = [
        {
            "name": city["name"],
            "url": reverse("interface:city_page", args=[city["slug"]]),
        }
        for city in MARKETING_CITY_ENTRIES
    ]
    return render(
        request,
        "interface/home.html",
        {
            "providers": providers,
            "zones": zones,
            "services": services,
            "featured_services": featured_services,
            "request_form": request_form,
            "request_success": request_success,
            "homepage_reviews": homepage_reviews,
            "marketing_city_links": city_links,
        },
    )


def city_page(request, city_slug: str):
    zone = _get_zone_or_404(city_slug)
    providers = list(Provider.objects.visible_on_website().filter(zones__slug=zone.slug).distinct())
    services = list(MarketingService.objects.all())

    city_copy = CITY_PAGE_COPY.get(zone.slug, {})
    intro = city_copy.get(
        "intro",
        (
            "Tu recherches une coiffure afro à {city} ? Château Rose te met en relation avec des "
            "coiffeuses et coiffeurs afro qui connaissent les cheveux texturés et adaptent chaque "
            "prestation à ton style : coiffures protectrices, tresses, locks, soins et finitions "
            "personnalisées."
        ).format(city=zone.name),
    )
    long_description = city_copy.get(
        "long_description",
        (
            "Sur cette page dédiée à la coiffure afro à {city}, tu peux comparer les profils, vérifier "
            "les disponibilités et réserver en quelques minutes. L'objectif est simple : te permettre "
            "de trouver rapidement un ou une professionnelle sérieuse, proche de chez toi, avec un "
            "accompagnement clair du début à la fin."
        ).format(city=zone.name),
    )

    return render(
        request,
        "interface/city_page.html",
        {
            "zone": zone,
            "providers": providers,
            "services": services,
            "intro": intro,
            "long_description": long_description,
        },
    )


def zone_search(request):
    if request.method != "GET":
        return HttpResponseBadRequest("Méthode non autorisée")

    term = request.GET.get("q", "").strip()
    zones = Zone.objects.all().order_by("name")
    if term:
        zones = zones.filter(name__icontains=term)

    limit = 20 if term else 76
    zones = zones[:limit]
    payload = {"results": [{"id": zone.id, "name": zone.name, "slug": zone.slug} for zone in zones]}
    return JsonResponse(payload)


def provider_list(request):
    providers = Provider.objects.visible_on_website()
    return render(request, "interface/provider_list.html", {"providers": providers})


def at_home_provider_list(request):
    providers = Provider.objects.visible_on_website().filter(
        location_mode__in=[
            Provider.LOCATION_MODE_CLIENT_HOME_ONLY,
            Provider.LOCATION_MODE_HYBRID,
        ]
    )
    return render(request, "interface/at_home_provider_list.html", {"providers": providers})


def provider_detail(request, provider_id, quick_checkout=None):
    provider = get_object_or_404(Provider, id=provider_id)
    services = list(
        Service.objects.filter(provider=provider)
        .select_related("category")
        .order_by("category__order", "category__name", "name")
    )
    pricing_data, starting_prices = booking_requests.build_pricing_data(services)
    zones = provider.zones.all()
    message = None
    question_message = None
    error = None
    question_error = None
    salon_location_label = SALON_LOCATION_LABEL
    question_form = ProviderQuestionForm()
    stripe_public_key = settings.STRIPE_PUBLIC_KEY
    require_payment_auth = False
    prefilled_payment_auth_id = ""
    payment_message = None
    fixed_price_cents = None
    recap_prefill = {}
    recap_token = ""
    recap_message = None
    can_save_partial_prefill = False

    if quick_checkout is not None:
        fixed_price_cents = quick_checkout.reservation_fee_cents

    if request.method == "GET":
        message = request.session.pop("provider_request_message", None)
        question_message = request.session.pop("provider_question_message", None)
        prefilled_payment_auth_id = (request.GET.get("payment_auth_id") or "").strip()
        if prefilled_payment_auth_id:
            payment_message = (
                "Paiement Château Rose confirmé. Tu peux finaliser l'envoi de ta demande."
            )
        recap_token = (request.GET.get("recap") or "").strip()
        if recap_token:
            recap_draft = (
                ProviderBookingDraft.objects.filter(token=recap_token, provider=provider).first()
            )
            if recap_draft:
                recap_prefill = recap_draft.payload or {}
                recap_message = "Récapitulatif chargé. Tu peux modifier les infos puis finaliser."
                can_save_partial_prefill = (
                    bool(getattr(request.user, "is_authenticated", False))
                    and bool(getattr(request.user, "is_staff", False))
                    and
                    recap_draft.source == ProviderBookingDraft.SOURCE_ADMIN
                    and recap_draft.completed_at is None
                )
            else:
                recap_token = ""

    if request.method == "POST" and request.POST.get("question_form") == "1":
        question_form = ProviderQuestionForm(request.POST)
        if question_form.is_valid():
            _notify_provider_question(provider, question_form)
            request.session["provider_question_message"] = "Question envoyée. Nous revenons vers toi rapidement."
            return redirect("interface:thank_you_question")
        question_error = _first_form_error(question_form)

    if request.method == "POST" and request.POST.get("question_form") != "1":
        prefilled_payment_auth_id = (request.POST.get("payment_auth_id") or "").strip()
        recap_token_from_post = (request.POST.get("recap_token") or "").strip()
        post_action = (request.POST.get("action") or "").strip()
        existing_admin_draft = None
        if recap_token_from_post:
            existing_admin_draft = ProviderBookingDraft.objects.filter(
                token=recap_token_from_post,
                provider=provider,
                source=ProviderBookingDraft.SOURCE_ADMIN,
                completed_at__isnull=True,
            ).first()
        partial_prefill_mode = bool(
            existing_admin_draft
            and post_action == "save_prefill"
            and bool(getattr(request.user, "is_authenticated", False))
            and bool(getattr(request.user, "is_staff", False))
        )
        form = ProviderBookingRequestForm(
            request.POST,
            request.FILES,
            provider=provider,
            require_payment_auth=False,
            require_current_hair_picture=not partial_prefill_mode,
            partial_prefill_mode=partial_prefill_mode,
        )
        if form.is_valid():
            try:
                if existing_admin_draft:
                    if partial_prefill_mode:
                        recap = _save_partial_provider_booking_recap_prefill(
                            provider=provider,
                            form=form,
                            draft=existing_admin_draft,
                        )
                    else:
                        recap = _update_provider_booking_recap(
                            provider=provider,
                            form=form,
                            draft=existing_admin_draft,
                        )
                else:
                    recap = _create_provider_booking_recap(
                        request=request,
                        provider=provider,
                        form=form,
                    )
            except DomainError as exc:
                error = _friendly_domain_error_message(exc)
            else:
                if partial_prefill_mode:
                    return redirect(
                        f"{reverse('interface:provider_detail', args=[provider.id])}?recap={recap.token}#booking-wizard"
                    )
                return redirect("interface:provider_booking_recap", token=str(recap.token))
        else:
            if _provider_configuration_blocks_salon_booking(provider, request.POST.get("location_preference")):
                _release_payment_auth_safely(prefilled_payment_auth_id)
                prefilled_payment_auth_id = ""
            error = _first_form_error(form)
            can_save_partial_prefill = bool(existing_admin_draft)

    service_categories = []
    if provider.categorized_services_enabled:
        categories = list(
            ServiceCategory.objects.filter(provider=provider).order_by("order", "name")
        )
        services_by_category = {category.id: [] for category in categories}
        unassigned_services = []
        for service in services:
            if service.category_id:
                services_by_category.setdefault(service.category_id, []).append(service)
            else:
                unassigned_services.append(service)

        for category in categories:
            categorized_services = services_by_category.get(category.id, [])
            if categorized_services:
                service_categories.append(
                    {"name": category.name, "services": categorized_services}
                )

        if unassigned_services:
            service_categories.append(
                {"name": "Autres services", "services": unassigned_services}
            )

    selected_category_slug = (request.GET.get("category") or "").strip()
    available_category_slugs = {
        slugify(category["name"]): category for category in service_categories
    }
    if selected_category_slug not in available_category_slugs:
        selected_category_slug = next(iter(available_category_slugs), "")

    visible_service_categories = service_categories
    if selected_category_slug:
        visible_service_categories = [
            available_category_slugs[selected_category_slug]
        ]

    provider_photos = list(provider.photos.all())
    before_appointment_items = list(
        ProviderBeforeAppointmentItem.objects.filter(provider=provider)
    )
    hero_photos = [
        photo
        for photo in provider_photos
        if photo.media_kind == photo.MEDIA_IMAGE and photo.resolved_url
    ][:4]
    gallery_photos = [photo for photo in provider_photos if photo.resolved_url]

    context = {
        "provider": provider,
        "services": services,
        "service_categories": service_categories,
        "visible_service_categories": visible_service_categories,
        "selected_category_slug": selected_category_slug,
        "zones": zones,
        "hero_photos": hero_photos,
        "gallery_photos": gallery_photos,
        "before_appointment_items": before_appointment_items,
        "message": message,
        "question_message": question_message,
        "error": error,
        "question_error": question_error,
        "question_form": question_form,
        "pricing_data": json.dumps(pricing_data),
        "default_starting_price": (
            booking_requests.format_marketing_price(min(starting_prices))
            if starting_prices
            else None
        ),
        "salon_location_label": salon_location_label,
        "stripe_public_key": stripe_public_key,
        "payment_auth_id": prefilled_payment_auth_id,
        "payment_message": payment_message,
        "fixed_price_cents": fixed_price_cents,
        "quick_checkout": quick_checkout,
        "is_quick_checkout": quick_checkout is not None,
        "quick_checkout_id": quick_checkout.id if quick_checkout else "",
        "recap_prefill": json.dumps(recap_prefill),
        "recap_token": recap_token,
        "recap_message": recap_message,
        "can_save_partial_prefill": can_save_partial_prefill,
        "support_phone_display": SUPPORT_PHONE_DISPLAY,
        "support_phone_tel": SUPPORT_PHONE_TEL,
    }
    if request.headers.get("HX-Request") == "true":
        return render(request, "interface/partials/provider_services_section.html", context)

    return render(request, "interface/provider_detail.html", context)


def quick_checkout_page(request, checkout_id):
    checkout = get_object_or_404(
        QuickCheckoutPage.objects.select_related("provider", "service"),
        id=checkout_id,
        is_active=True,
        completed_at__isnull=True,
    )
    if checkout.expires_at and checkout.expires_at <= timezone.now():
        raise Http404("Ce lien de paiement rapide a expiré.")

    provider = checkout.provider
    stripe_public_key = settings.STRIPE_PUBLIC_KEY
    requires_reservation_fee = checkout.reservation_fee_cents > 0
    require_payment_auth = bool(stripe_public_key) and requires_reservation_fee
    message = None
    error = None
    payment_message = None
    prefilled_payment_auth_id = ""
    client_address_value = (checkout.client_address or "").strip()
    is_domicile = checkout.location_preference == "domicile"

    if request.method == "GET":
        prefilled_payment_auth_id = (request.GET.get("payment_auth_id") or "").strip()
        if prefilled_payment_auth_id:
            payment_message = (
                "Paiement Château Rose confirmé. Tu peux finaliser l'envoi de ta demande."
            )

    if request.method == "POST":
        payment_auth_id = (request.POST.get("payment_auth_id") or "").strip()
        if not requires_reservation_fee:
            payment_auth_id = f"free_quick_checkout_{checkout.id}"
        client_address_value = (request.POST.get("client_address") or "").strip()
        if not is_domicile:
            client_address_value = ""
        if require_payment_auth and not payment_auth_id:
            error = "Merci d'ajouter ton paiement Château Rose pour sécuriser la demande."
        elif require_payment_auth and not _payment_auth_is_confirmed(payment_auth_id):
            error = "Le paiement Château Rose n'est pas confirmé. Merci de réessayer le paiement."
        elif is_domicile and not client_address_value:
            error = "Merci d'indiquer ton adresse complète pour le rendez-vous à domicile."
        else:
            if checkout.client_address != client_address_value:
                checkout.client_address = client_address_value
                checkout.save(update_fields=["client_address", "updated_at"])
            try:
                booking = _complete_quick_checkout(checkout, payment_auth_id)
                _create_interaction(
                    kind=Interaction.KIND_PROVIDER_APPOINTMENT_REQUEST,
                    source_label=f"Demande rapide checkout · {provider.name}",
                    contact_name=checkout.client_name,
                    contact_email=checkout.client_email,
                    subject=f"Demande RDV rapide {booking.id}",
                    message=checkout.free_text or "",
                    next_action="Confirmer le rendez-vous côté prestataire",
                    metadata={
                        "booking_id": booking.id,
                        "provider_id": provider.id,
                        "provider_name": provider.name,
                        "quick_checkout_id": checkout.id,
                    },
                )
                thank_you_url = reverse("interface:thank_you_provider_booking")
                return redirect(
                    f"{thank_you_url}?provider={provider.name}&provider_id={provider.id}"
                )
            except DomainError as exc:
                _release_payment_auth_safely(payment_auth_id)
                error = _friendly_domain_error_message(exc)

    return render(
        request,
        "interface/quick_checkout_page.html",
        {
            "provider": provider,
            "quick_checkout": checkout,
            "message": message,
            "error": error,
            "payment_message": payment_message,
            "payment_auth_id": prefilled_payment_auth_id,
            "stripe_public_key": stripe_public_key,
            "require_payment_auth": require_payment_auth,
            "requires_reservation_fee": requires_reservation_fee,
            "quick_checkout_id": checkout.id,
            "final_price_cents": checkout.final_price_cents,
            "reservation_fee_cents": checkout.reservation_fee_cents,
            "remaining_price_cents": max(checkout.final_price_cents - checkout.reservation_fee_cents, 0),
            "is_domicile": is_domicile,
            "client_address": client_address_value,
        },
    )


def provider_booking_recap(request, token):
    draft = get_object_or_404(
        ProviderBookingDraft.objects.select_related("provider"),
        token=token,
    )
    payload = draft.payload or {}
    provider = draft.provider
    service = Service.objects.filter(provider=provider, id=payload.get("service_id")).first()
    if service is None:
        raise Http404("Service introuvable pour ce récapitulatif.")

    try:
        total_cents, _, _ = estimate_service_price_cents(
            service={
                "base_price_cents": service.base_price_cents,
                "hair_length_adjustments": service.hair_length_adjustments,
                "general_adjustments": service.general_adjustments,
                "meche_bonus_cents": service.meche_bonus_cents,
                "at_home_bonus_cents": service.at_home_bonus_cents,
            },
            hair_length=payload.get("hair_length") or "",
            general_adjustments=payload.get("general_adjustments") or [],
            meche=bool(payload.get("meche")),
            location_preference=payload.get("location_preference") or "salon",
        )
    except ValidationError as exc:
        raise Http404(str(exc))

    coupon_code = (payload.get("service_fee_coupon_code") or "").strip().upper()
    service_fee_waived = _provider_coupon_is_valid(provider, coupon_code)
    checkout_amounts = compute_service_fee_only_amounts_cents(
        subtotal_cents=total_cents,
        service_fee_percentage=provider.service_fee_percentage if provider.service_fee_percentage is not None else 15,
        waive_service_fee=service_fee_waived,
    )
    desired_date_display = payload.get("desired_date") or "Non renseignée"
    try:
        desired_date_display = timezone.localtime(datetime.fromisoformat(str(payload.get("desired_date")))).strftime("%d/%m/%Y à %H:%M")
    except (TypeError, ValueError):
        pass
    stripe_public_key = settings.STRIPE_PUBLIC_KEY
    require_payment_auth = bool(stripe_public_key) and checkout_amounts["amount_due_now_cents"] > 0
    error = None

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip() or "confirm"
        if action == "edit":
            return redirect(f"{reverse('interface:provider_detail', args=[provider.id])}?recap={draft.token}#booking-wizard")
        if draft.completed_at:
            thank_you_url = reverse("interface:thank_you_provider_booking")
            return redirect(
                f"{thank_you_url}?provider={provider.name}&provider_id={provider.id}"
            )

        payment_auth_id = (request.POST.get("payment_auth_id") or "").strip()
        if require_payment_auth and not payment_auth_id:
            error = "Ajoute ton paiement Château Rose pour confirmer la demande."
        elif require_payment_auth and not _payment_auth_is_confirmed(payment_auth_id):
            error = "Le paiement Château Rose n'est pas confirmé. Merci de réessayer le paiement."
        else:
            booking_detail_path = reverse("providers:booking_detail", args=["BOOKING_ID"])
            provider_booking_url_base = request.build_absolute_uri(
                booking_detail_path.replace("BOOKING_ID/", "")
            )
            try:
                booking = request_haircut.execute(
                    provider_id=str(provider.id),
                    service_id=str(service.id),
                    client_contact={
                        "name": payload.get("client_name") or "",
                        "email": payload.get("client_email") or "",
                    },
                    location=payload.get("location") or "",
                    location_preference=payload.get("location_preference") or "",
                    client_address=payload.get("client_address") or "",
                    desired_date=payload.get("desired_date") or "",
                    hair_length=payload.get("hair_length") or "",
                    general_adjustments=payload.get("general_adjustments") or [],
                    meche=bool(payload.get("meche")),
                    current_hair_picture=payload.get("current_hair_picture") or "",
                    inspiration_pictures=payload.get("inspiration_pictures") or [],
                    free_text=payload.get("free_text") or "",
                    service_fee_coupon_code=coupon_code,
                    waive_service_fee=service_fee_waived,
                    payment_auth_id=payment_auth_id or None,
                    provider_booking_url_base=provider_booking_url_base,
                    provider_salon_zone=provider.salon_zone,
                    booking_repository=repo,
                    provider_catalog=provider_catalog,
                    payment_gateway=payment_gateway,
                    notifier=notifier,
                    reminder_gateway=None,
                    clock=type("Clock", (), {"now": timezone.now}),
                    operations_email=SUPPORT_EMAIL,
                )
            except DomainError as exc:
                _release_payment_auth_safely(payment_auth_id)
                error = _friendly_domain_error_message(exc)
            else:
                _create_interaction(
                    kind=Interaction.KIND_PROVIDER_APPOINTMENT_REQUEST,
                    source_label=f"Demande de réservation · {provider.name}",
                    contact_name=payload.get("client_name") or "",
                    contact_email=payload.get("client_email") or "",
                    subject=f"Demande RDV {booking.id}",
                    message=payload.get("free_text") or "",
                    next_action="Vérifier et confirmer la demande dans le tableau prestataires",
                    metadata={
                        "booking_id": booking.id,
                        "provider_id": provider.id,
                        "provider_name": provider.name,
                        "recap_token": str(draft.token),
                    },
                )
                _mark_recap_completed_if_needed(str(draft.token))
                request.session["provider_request_message"] = f"Demande envoyée. ID: {booking.id}"
                thank_you_url = reverse("interface:thank_you_provider_booking")
                return redirect(
                    f"{thank_you_url}?provider={provider.name}&provider_id={provider.id}"
                )

    displayed_deposit_cents = 0
    displayed_reservation_fee_cents = checkout_amounts["amount_due_now_cents"]
    displayed_remaining_cents = floor_price_for_display_cents(checkout_amounts["provider_price_cents"])

    return render(
        request,
        "interface/provider_booking_recap.html",
        {
            "provider": provider,
            "draft": draft,
            "payload": payload,
            "is_completed": bool(draft.completed_at),
            "edit_url": f"{reverse('interface:provider_detail', args=[provider.id])}?recap={draft.token}",
            "total_price": booking_requests.format_price(checkout_amounts["subtotal_cents"] + checkout_amounts["service_fee_cents"]),
            "subtotal_price": booking_requests.format_price(checkout_amounts["subtotal_cents"]),
            "service_fee_price": booking_requests.format_price(checkout_amounts["service_fee_cents"]),
            "acompte_price": booking_requests.format_price(displayed_deposit_cents),
            "deposit_price": booking_requests.format_price(displayed_reservation_fee_cents),
            "remaining_price": booking_requests.format_price(displayed_remaining_cents),
            "amount_due_now_cents": checkout_amounts["amount_due_now_cents"],
            "service_fee_coupon_code": coupon_code,
            "service_fee_waived": service_fee_waived,
            "reservation_label_details": "frais de service Château Rose uniquement",
            "desired_date_display": desired_date_display,
            "stripe_public_key": stripe_public_key,
            "require_payment_auth": require_payment_auth,
            "payment_intent_url": reverse("interface:provider_payment_intent"),
            "provider_id": provider.id,
            "service_id": service.id,
            "error": error,
        },
    )


def _format_euros_from_cents(amount_cents: int) -> str:
    return booking_requests.format_price(amount_cents)


def _payment_auth_is_confirmed(payment_auth_id: str) -> bool:
    if not payment_auth_id or payment_auth_id.startswith("free_"):
        return True
    if not settings.STRIPE_SECRET_KEY:
        return False
    try:
        intent = payment_gateway.retrieve_payment_intent(payment_auth_id)
    except Exception:
        return False
    return (intent.get("status") or "") in {"requires_capture", "succeeded", "processing"}


def _payment_summary(booking, *, total_cents: int | None = None) -> dict:
    effective_total_cents = (
        total_cents
        if total_cents is not None
        else booking.proposed_price_cents
        if booking.proposed_price_cents is not None
        else booking.estimated_price_cents
    )
    service_fee_cents = getattr(booking, "chateau_rose_fee_cents", 0) or 0
    provider_price_cents = booking.provider_price_estimate_cents

    if provider_price_cents is None:
        should_infer_legacy_fee = service_fee_cents == 0 and bool(getattr(booking, "payment_auth_id", "")) and getattr(booking, "provider", None)
        if should_infer_legacy_fee:
            service_fee_percentage = booking.provider.service_fee_percentage
            if service_fee_percentage is None:
                service_fee_percentage = Provider._meta.get_field("service_fee_percentage").default
            checkout_amounts = compute_checkout_amounts_from_total_cents(
                total_cents=effective_total_cents,
                deposit_percentage=booking.provider.deposit_percentage or 30,
                service_fee_percentage=service_fee_percentage or 0,
            )
            provider_price_cents = checkout_amounts["subtotal_cents"]
            service_fee_cents = checkout_amounts["service_fee_cents"]
        else:
            provider_price_cents = max(effective_total_cents - service_fee_cents, 0)

    amount_due_now_cents = getattr(booking, "amount_due_now_cents", 0) or service_fee_cents
    return {
        "total": _format_euros_from_cents(provider_price_cents + service_fee_cents),
        "reservation_fee": _format_euros_from_cents(amount_due_now_cents),
        "deposit": _format_euros_from_cents(0),
        "service_fee": _format_euros_from_cents(service_fee_cents),
        "remaining": _format_euros_from_cents(provider_price_cents),
    }


def quick_checkout_confirmation(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("provider", "service"),
        booking_id=booking_id,
    )
    effective_date = booking.proposed_date or booking.desired_date
    effective_price = (
        booking_requests.format_price(booking.proposed_price_cents)
        if booking.proposed_price_cents is not None
        else booking_requests.format_price(booking.estimated_price_cents)
    )
    is_salon = booking.location_preference == "salon"

    return render(
        request,
        "interface/quick_checkout_confirmation.html",
        {
            "booking": booking,
            "effective_date": effective_date,
            "effective_price": effective_price,
            "is_salon": is_salon,
            "provider_email": booking.provider.contact_email or "Non communiqué",
            "provider_phone": booking.provider.contact_phone or "Non communiqué",
            "provider_salon_address": booking.provider.salon_address or "Adresse à confirmer",
            "payment_summary": _payment_summary(booking),
        },
    )


def provider_payment_intent(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Méthode non autorisée")

    if not settings.STRIPE_SECRET_KEY:
        return JsonResponse({"error": "Paiement indisponible."}, status=400)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (TypeError, json.JSONDecodeError):
        return HttpResponseBadRequest("Requête invalide")

    provider_id = payload.get("provider_id")
    service_id = payload.get("service_id")
    hair_length = payload.get("hair_length")
    general_adjustments = payload.get("general_adjustments") or []
    meche = payload.get("meche")
    location_preference = payload.get("location_preference")
    desired_date = payload.get("desired_date")
    service_fee_coupon_code = (payload.get("service_fee_coupon_code") or "").strip().upper()
    quick_checkout_id = payload.get("quick_checkout_id")
    validate_only = bool(payload.get("validate_only"))

    quick_checkout = None
    if quick_checkout_id:
        quick_checkout = QuickCheckoutPage.objects.filter(
            id=quick_checkout_id,
            is_active=True,
            completed_at__isnull=True,
        ).first()
        if quick_checkout is None:
            return JsonResponse({"error": "Lien checkout invalide."}, status=400)

        amount_cents = quick_checkout.reservation_fee_cents
    else:
        if not all([provider_id, service_id, desired_date]) or meche is None:
            return JsonResponse({"error": "Informations manquantes."}, status=400)

        blocked_slot_details_getter = getattr(provider_catalog, "get_blocked_slot_details", None)
        if callable(blocked_slot_details_getter):
            blocked_slot_details = blocked_slot_details_getter(provider_id, desired_date)
        else:
            has_blocked_slot = getattr(provider_catalog, "provider_has_blocked_slot", None)
            blocked_slot_details = {"reason": None} if callable(has_blocked_slot) and has_blocked_slot(provider_id, desired_date) else None

        if blocked_slot_details is not None:
            reason = (blocked_slot_details.get("reason") or "").strip() if isinstance(blocked_slot_details, dict) else ""
            if reason:
                return JsonResponse({"error": f"Créneau non disponible : {reason}"}, status=409)
            return JsonResponse({"error": "Ce créneau n'est plus disponible. Choisis un autre horaire."}, status=409)

        try:
            service = provider_catalog.get_service(provider_id, service_id)
        except KeyError:
            return JsonResponse({"error": "Service non disponible."}, status=400)

        provider_for_coupon = Provider.objects.filter(id=provider_id).first()
        service_fee_waived = bool(
            provider_for_coupon and _provider_coupon_is_valid(provider_for_coupon, service_fee_coupon_code)
        )

        try:
            estimated_price_cents, _, _ = estimate_service_price_cents(
                service=service,
                hair_length=hair_length,
                general_adjustments=general_adjustments,
                meche=meche,
                location_preference=location_preference,
            )
        except ValidationError as exc:
            message = str(exc)
            if "hair_length" in message:
                return JsonResponse({"error": "Longueur de cheveux non supportée."}, status=400)
            if "General adjustment" in message:
                return JsonResponse({"error": "Un ou plusieurs suppléments ne sont pas supportés."}, status=400)
            return JsonResponse({"error": "Informations manquantes."}, status=400)

        amount_cents = compute_service_fee_only_amounts_cents(
            subtotal_cents=estimated_price_cents,
            service_fee_percentage=service.get("service_fee_percentage", 15),
            waive_service_fee=service_fee_waived,
        )["amount_due_now_cents"]

    if validate_only:
        return JsonResponse({"ok": True, "amount_cents": amount_cents, "payment_required": amount_cents > 0})

    if amount_cents <= 0:
        return JsonResponse({"payment_required": False, "amount_cents": 0, "payment_status": "WAIVED"})

    intent = payment_gateway.create_payment_intent(
        amount_cents=amount_cents,
        currency="EUR",
        reference=f"estimate-{uuid.uuid4().hex[:10]}",
    )

    return JsonResponse(
        {
            "client_secret": intent["client_secret"],
            "payment_auth_id": intent["id"],
            "amount_cents": amount_cents,
            "payment_required": True,
        }
    )


def provider_payment_return(request):
    provider_id = request.GET.get("provider_id", "").strip()
    intent_id = request.GET.get("payment_intent", "").strip()
    redirect_status = request.GET.get("redirect_status", "").strip()
    status = redirect_status or "unknown"
    status_checked = False

    if intent_id and settings.STRIPE_SECRET_KEY:
        try:
            intent = payment_gateway.retrieve_payment_intent(intent_id)
            status = intent.get("status") or status
            status_checked = True
        except Exception:
            status_checked = False

    success_statuses = {"succeeded", "requires_capture", "processing"}
    failure_statuses = {"requires_payment_method", "canceled"}

    quick_checkout_id = request.GET.get("quick_checkout_id", "").strip()
    completed_booking_id = ""
    if status in success_statuses and intent_id and quick_checkout_id:
        checkout = QuickCheckoutPage.objects.filter(
            id=quick_checkout_id,
            is_active=True,
            completed_at__isnull=True,
        ).select_related("provider", "service").first()
        if checkout is not None:
            try:
                booking = _complete_quick_checkout(checkout, intent_id)
                completed_booking_id = booking.id
            except DomainError:
                _release_payment_auth_safely(intent_id)
                completed_booking_id = ""

    if status in success_statuses:
        headline = "Paiement Château Rose confirmé"
        tone = "success"
        if completed_booking_id:
            message = "Ton paiement Château Rose est validé. La demande est envoyée et reste en attente de confirmation manuelle."
        else:
            message = (
                "Ton paiement Château Rose a bien été enregistré. Tu peux maintenant finaliser ta demande."
            )
    elif status in failure_statuses:
        headline = "Paiement Château Rose refusé"
        tone = "error"
        message = "La banque a refusé la carte. Tu peux réessayer avec un autre moyen."
    else:
        headline = "Paiement Château Rose en attente"
        tone = "warning"
        message = (
            "Nous n'avons pas pu confirmer immédiatement le paiement Château Rose. "
            "Tu peux retourner au formulaire pour réessayer."
        )

    action_label = "Retourner au formulaire"
    action_url = reverse("interface:home")
    if provider_id:
        try:
            Provider.objects.only("id").get(id=provider_id)
        except Provider.DoesNotExist:
            action_url = reverse("interface:home")
        else:
            action_url = reverse("interface:provider_detail", args=[provider_id])
            if completed_booking_id:
                action_url = reverse("interface:client_confirmation", args=[completed_booking_id])
            elif status in success_statuses and intent_id:
                action_url = f"{action_url}?payment_auth_id={intent_id}"

    return render(
        request,
        "interface/provider_payment_return.html",
        {
            "headline": headline,
            "tone": tone,
            "message": message,
            "action_label": action_label,
            "action_url": action_url,
            "status": status,
            "status_checked": status_checked,
            "completed_booking_id": completed_booking_id,
        },
    )


def provider_action(request, booking_id):
    if not request.user.is_authenticated:
        return HttpResponseForbidden("Authentification requise")
    if not request.user.is_staff:
        return HttpResponseForbidden("Accès réservé au staff/prestataires")
    if request.method != "POST":
        return HttpResponseBadRequest("Méthode non autorisée")
    decision = request.POST.get("decision")
    provider_id = request.POST.get("provider_id")
    now = timezone.now()
    try:
        final_booking = finalize_booking_uc.execute(
            booking_id=booking_id,
            actor="provider",
            decision=decision,
            now=now,
            booking_repository=repo,
            payment_gateway=payment_gateway,
            provider_directory=provider_directory,
            notifier=notifier,
            operations_email=SUPPORT_EMAIL,
        )
    except finalize_booking_uc.InvalidState as exc:
        if str(exc) != "Booking has expired":
            raise
        final_booking = expire_booking_uc.execute(
            booking_id=booking_id,
            now=now,
            booking_repository=repo,
            payment_gateway=payment_gateway,
            notifier=notifier,
            operations_email=SUPPORT_EMAIL,
        )
    return redirect("interface:home")


def client_action(request, booking_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Méthode non autorisée")
    decision = request.POST.get("decision")
    now = timezone.now()
    expired = False
    try:
        final_booking = finalize_booking_uc.execute(
            booking_id=booking_id,
            actor="client",
            decision=decision,
            now=now,
            booking_repository=repo,
            payment_gateway=payment_gateway,
            provider_directory=provider_directory,
            notifier=notifier,
            operations_email=SUPPORT_EMAIL,
        )
    except finalize_booking_uc.InvalidState as exc:
        if str(exc) != "Booking has expired":
            raise
        final_booking = expire_booking_uc.execute(
            booking_id=booking_id,
            now=now,
            booking_repository=repo,
            payment_gateway=payment_gateway,
            notifier=notifier,
            operations_email=SUPPORT_EMAIL,
        )
        expired = True

    target_url = reverse("interface:client_confirmation", args=[final_booking.id])
    if expired:
        target_url = f"{target_url}?status=expired"
    return redirect(target_url)


def client_confirmation(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("provider", "service"),
        booking_id=booking_id,
    )
    effective_date = booking.proposed_date or booking.desired_date
    effective_price = (
        booking_requests.format_price(booking.proposed_price_cents)
        if booking.proposed_price_cents is not None
        else booking_requests.format_price(booking.estimated_price_cents)
    )
    is_confirmed = booking.status == finalize_booking_uc.CONFIRMED
    is_cancelled = booking.status == finalize_booking_uc.CANCELLED
    is_awaiting_alternative = booking.status == finalize_booking_uc.AWAITING_ALTERNATIVE_PROVIDER
    is_waiting_provider_assignment = booking.status == getattr(expire_booking_uc, "WAITING_PROVIDER_ASSIGNMENT", "WAITING_PROVIDER_ASSIGNMENT")
    show_expired_notice = request.GET.get("status") == "expired"
    is_salon = booking.location_preference == "salon"
    client_moves = is_salon
    return render(
        request,
        "interface/client_confirmation.html",
        {
            "booking": booking,
            "effective_date": effective_date,
            "effective_price": effective_price,
            "is_confirmed": is_confirmed,
            "is_cancelled": is_cancelled,
            "is_awaiting_alternative": is_awaiting_alternative,
            "is_waiting_provider_assignment": is_waiting_provider_assignment,
            "show_expired_notice": show_expired_notice,
            "client_moves": client_moves,
            "provider_email": (booking.provider.contact_email if booking.provider else "Non communiqué"),
            "provider_phone": (booking.provider.contact_phone if booking.provider else "Non communiqué"),
            "provider_salon_address": (booking.provider.salon_address if booking.provider else "Adresse à confirmer"),
            "payment_summary": _payment_summary(booking),
        },
    )


def client_proposal(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("provider", "service"),
        booking_id=booking_id,
    )
    proposed_date = booking.proposed_date or booking.desired_date
    proposed_price = (
        booking_requests.format_price(booking.proposed_price_cents)
        if booking.proposed_price_cents is not None
        else booking_requests.format_price(booking.estimated_price_cents)
    )
    return render(
        request,
        "interface/client_proposal.html",
        {
            "booking": booking,
            "proposed_date": proposed_date,
            "proposed_price": proposed_price,
            "provider_email": booking.provider.contact_email or "Non communiqué",
            "provider_phone": booking.provider.contact_phone or "Non communiqué",
            "payment_summary": _payment_summary(booking),
        },
    )


def _get_service_or_404(service_slug: str):
    return get_object_or_404(MarketingService, slug=service_slug)


def _get_zone_or_404(zone_slug: str):
    return get_object_or_404(Zone, slug=zone_slug)


def _zone_options(active_zone=None):
    zones = list(Zone.objects.filter(marketing_profile__isnull=False).order_by("name"))
    if active_zone and not any(zone.slug == active_zone.slug for zone in zones):
        zones.append(active_zone)
    return zones


def _notify_service_request(record) -> None:
    desired_date = timezone.localtime(record.desired_date).strftime("%d/%m/%Y %H:%M") if record.desired_date else "Non précisée"
    zone_name = record.zone.name if record.zone else "Non précisé"
    location_preference = record.get_location_preference_display()
    availability_labels = dict(ServiceRequest.AVAILABILITY_CHOICES)
    availabilities = ", ".join(availability_labels.get(item, item) for item in (record.availabilities or [])) or "Non précisées"
    subject = f"Nouvelle demande rapide - {record.marketing_service.name}"
    body_lines = [
        f"Service : {record.marketing_service.name}",
        f"Email : {record.client_email or 'Non communiqué'}",
        f"WhatsApp / téléphone : {record.client_phone or 'Non communiqué'}",
        f"Date souhaitée : {desired_date}",
        f"Lieu préféré : {location_preference}",
        f"Zone : {zone_name}",
        f"Disponibilités : {availabilities}",
        f"Photo jointe : {'Oui' if record.inspiration_picture_urls else 'Non'}",
    ]
    if record.details:
        body_lines.extend(["Détails de la demande :", record.details])
    _create_interaction(
        kind=Interaction.KIND_QUICK_REQUEST,
        source_label="Demande rapide",
        contact_name=record.client_name,
        contact_email=record.client_email,
        contact_phone=record.client_phone,
        subject=subject,
        message=record.details or "",
        next_action="Contacter la cliente / le client rapidement",
        metadata={
            "service": record.marketing_service.name,
            "zone": zone_name,
            "location_preference": location_preference,
            "availabilities": record.availabilities or [],
        },
        service_request=record,
    )
    notifier.notify(
        "japhet.situmonana@gmail.com",
        subject,
        "\n".join(body_lines),
        reply_to=record.client_email or "japhet.situmonana@gmail.com",
    )


def _get_homepage_reviews(limit: int = 6) -> list[ClientReview]:
    featured = list(ClientReview.objects.filter(is_active=True, is_featured=True).order_by("-created_at")[:limit])
    if len(featured) >= limit:
        return featured

    extra = list(
        ClientReview.objects.filter(is_active=True, is_featured=False)
        .order_by("-created_at")[: max(limit - len(featured), 0)]
    )
    return featured + extra


def _build_service_request_redirect(request):
    if request.method != "GET":
        return None

    target_anchor = request.GET.get("anchor", "").strip()
    if target_anchor != "service-request":
        return None

    success = request.session.get("service_request_success", False)
    if not success:
        return None

    return redirect(f"{request.path}#service-request")


def _generic_booking_label(service_meta: MarketingService | None, sub_service: MarketingSubService | None = None) -> str:
    if sub_service:
        return f"{service_meta.name} · {sub_service.name}"
    return service_meta.name if service_meta else "Prestation demandée"


def _build_service_request_form(request, service_meta: MarketingService | None, zone, sub_service: MarketingSubService | None = None):
    is_request_submission = request.method == "POST" and request.POST.get("request_service") == "1"
    use_legacy_quick_request = is_request_submission and "contact" in request.POST
    request_success = request.session.pop("service_request_success", False)

    if use_legacy_quick_request:
        legacy_form = ServiceRequestForm(request.POST)
        if service_meta:
            legacy_form.fields["marketing_service"].initial = service_meta
            legacy_form.fields["marketing_service"].widget = forms.HiddenInput()
            legacy_form.fields["marketing_service"].required = False
        if legacy_form.is_valid():
            record = legacy_form.save(commit=False)
            record.marketing_service = service_meta or legacy_form.cleaned_data.get("marketing_service")
            if zone:
                record.zone = zone
            record.inspiration_picture_urls = []
            record.save()
            _notify_service_request(record)
            request.session["service_request_success"] = True
            return "redirect", False
        return legacy_form, request_success

    form = GenericBookingRequestForm(request.POST if is_request_submission else None)

    if is_request_submission and form.is_valid():
        coupon_code = (form.cleaned_data.get("service_fee_coupon_code") or "").strip().upper()
        generic_fee_cents = int(getattr(settings, "GENERIC_BOOKING_PLATFORM_FEE_CENTS", 0) or 0)
        waive_service_fee = coupon_code in {"VIPZERO", "ROSEZERO", "GRATUIT"}
        try:
            booking = create_booking_request.execute(
                client_contact={
                    "name": form.cleaned_data["client_name"],
                    "email": form.cleaned_data["client_email"],
                    "phone": form.cleaned_data["client_phone"],
                },
                requested_marketing_service_id=str(service_meta.id) if service_meta else None,
                requested_marketing_sub_service_id=str(sub_service.id) if sub_service else None,
                requested_service_label_snapshot=_generic_booking_label(service_meta, sub_service),
                requested_options=form.cleaned_data.get("requested_options") or [],
                chateau_rose_fee_cents=0 if waive_service_fee else generic_fee_cents,
                waive_service_fee=waive_service_fee,
                location=zone.name if zone else "À préciser",
                location_preference=form.cleaned_data.get("location_preference") or "salon",
                desired_date=form.cleaned_data["desired_date"],
                hair_length=form.cleaned_data.get("hair_length") or "",
                current_hair_picture="",
                inspiration_pictures=[],
                free_text="",
                operations_email=SUPPORT_EMAIL,
                booking_repository=repo,
                provider_catalog=provider_catalog,
                payment_gateway=payment_gateway,
                notifier=notifier,
                clock=type("Clock", (), {"now": timezone.now}),
            )
        except DomainError as exc:
            form.add_error(None, _friendly_domain_error_message(exc))
        else:
            _create_interaction(
                kind=Interaction.KIND_QUICK_REQUEST,
                source_label="Demande générique",
                contact_name=form.cleaned_data["client_name"],
                contact_email=form.cleaned_data["client_email"],
                contact_phone=form.cleaned_data["client_phone"],
                subject=f"Demande générique {booking.id}",
                next_action="Assigner une prestataire manuellement",
                metadata={"booking_id": booking.id, "service": _generic_booking_label(service_meta, sub_service)},
            )
            request.session["service_request_success"] = True
            return "redirect", False

    return form, request_success


def _gallery_from_service(service_meta: MarketingService):
    images = []
    for image in service_meta.images.all():
        resolved = image.resolved_url
        if not resolved:
            continue
        images.append(GalleryImage(url=resolved, caption=image.caption))
    return images


def _to_service_content(service_meta: MarketingService) -> ServiceContent:
    return ServiceContent(
        name=service_meta.name,
        intro=service_meta.intro,
        short_intro=service_meta.short_intro,
        long_description=service_meta.long_description,
        long_title=service_meta.long_title,
        highlights=service_meta.highlights,
        main_image=service_meta.resolved_main_image,
        gallery=_gallery_from_service(service_meta),
        meta_description=service_meta.meta_description,
    )


def _apply_zone_marketing(
    service_meta: MarketingService,
    marketing_zone: MarketingZone | None,
    service_zone: MarketingServiceZone | None = None,
):
    if not marketing_zone:
        base_content = _to_service_content(service_meta)
    else:
        intro_parts = [service_meta.intro]
        if marketing_zone.intro:
            intro_parts.append(marketing_zone.intro)

        merged_highlights = list(service_meta.highlights)
        if marketing_zone.highlights:
            for highlight in marketing_zone.highlights:
                if highlight and highlight not in merged_highlights:
                    merged_highlights.append(highlight)

        meta_description = service_meta.meta_description or ""
        if marketing_zone.meta_description:
            if meta_description:
                meta_description = f"{meta_description} {marketing_zone.meta_description}".strip()
            else:
                meta_description = marketing_zone.meta_description

        base_content = ServiceContent(
            name=service_meta.name,
            intro=" ".join([part for part in intro_parts if part]),
            short_intro=service_meta.short_intro,
            long_description=service_meta.long_description,
            long_title=service_meta.long_title,
            highlights=merged_highlights,
            main_image=marketing_zone.resolved_hero_image or service_meta.resolved_main_image,
            gallery=_gallery_from_service(service_meta),
            meta_description=meta_description,
        )

    if not service_zone:
        return base_content

    return ServiceContent(
        name=service_meta.name,
        intro=service_zone.intro or base_content.intro,
        short_intro=service_zone.short_intro or base_content.short_intro,
        long_description=service_zone.long_description or base_content.long_description,
        long_title=service_zone.long_title or base_content.long_title,
        highlights=service_zone.highlights or base_content.highlights,
        main_image=service_zone.resolved_hero_image or base_content.main_image,
        gallery=base_content.gallery,
        meta_description=service_zone.meta_description or base_content.meta_description,
    )


def _build_service_schema(request, service_name: str, zone_name: str | None):
    base_url = build_base_url(request)
    area_name = zone_name or "Toulouse"
    return {
        "@context": "https://schema.org",
        "@type": "Service",
        "serviceType": service_name,
        "areaServed": {"@type": "City", "name": area_name},
        "provider": {"@id": f"{base_url}#business"},
    }


AT_HOME_MARKETING_COPY = (
    "Réserve facilement une prestation à domicile avec une prestataire ou un prestataire "
    "qui se déplace. Même fonctionnement pour tous les services : tu compares les profils, "
    "tu vérifies les tarifs, puis tu réserves selon tes disponibilités."
)


def service_page(request, service_slug: str):
    service_meta = _get_service_or_404(service_slug)
    providers = list(
        Provider.objects.visible_on_website().filter(marketing_services__slug=service_slug).distinct()
    )
    sub_services = list(
        MarketingSubService.objects.filter(service=service_meta, is_visible=True)
        .prefetch_related("providers")
    )
    service_request_redirect = _build_service_request_redirect(request)
    if service_request_redirect:
        return service_request_redirect

    request_form, request_success = _build_service_request_form(
        request, service_meta, zone=None
    )
    if request_form == "redirect":
        return redirect("interface:thank_you_quick_request")
    if request_form is None:
        return redirect(f"{request.path}?anchor=service-request")
    service_content = _to_service_content(service_meta)
    marketing_content = build_marketing_content(service=service_content)
    hero_image = marketing_content.hero_image
    gallery_images = marketing_content.gallery
    intro = marketing_content.intro
    short_intro = marketing_content.short_intro
    long_description = marketing_content.long_description
    long_title = marketing_content.long_title
    city_intro = marketing_content.location_intro
    highlights = marketing_content.highlights
    meta_description = marketing_content.meta_description

    service_schema = _build_service_schema(request, service_meta.name, None)
    return render(
        request,
        "interface/service_page.html",
        {
            "service": service_meta,
            "zone": None,
            "providers": providers,
            "zones": _zone_options(),
            "intro": intro,
            "short_intro": short_intro,
            "long_description": long_description,
            "long_title": long_title,
            "city_intro": city_intro,
            "highlights": highlights,
            "hero_image": hero_image,
            "gallery_images": gallery_images,
            "meta_description": meta_description,
            "service_schema_json": json.dumps(service_schema, ensure_ascii=False),
            "request_form": request_form,
            "request_success": request_success,
            "sub_services": sub_services,
            "is_sub_service_page": False,
            "is_at_home_page": False,
            "page_service_name": service_meta.name,
            "seo_section_heading": f"{service_meta.name} : ce qu'il faut savoir",
            "seo_intro": intro,
            "seo_long_description": long_description,
            "support_phone_display": SUPPORT_PHONE_DISPLAY,
            "support_phone_tel": SUPPORT_PHONE_TEL,
        },
    )


def service_city_page(request, service_slug: str, city_slug: str):
    service_meta = _get_service_or_404(service_slug)
    zone = _get_zone_or_404(city_slug)
    marketing_zone = MarketingZone.objects.filter(zone=zone).first()
    service_zone = MarketingServiceZone.objects.filter(service=service_meta, zone=zone).first()
    marketing_content = build_marketing_content(
        service=_apply_zone_marketing(service_meta, marketing_zone, service_zone),
        location_name=zone.name,
    )
    intro = marketing_content.intro
    short_intro = marketing_content.short_intro
    long_description = marketing_content.long_description
    long_title = marketing_content.long_title
    city_intro = marketing_content.location_intro
    highlights = marketing_content.highlights

    providers = list(
        Provider.objects.visible_on_website().filter(
            marketing_services__slug=service_slug,
            zones__slug=zone.slug,
        ).distinct()
    )
    sub_services = list(
        MarketingSubService.objects.filter(
            service=service_meta,
            is_visible=True,
            providers__zones__slug=zone.slug,
            providers__is_visible_on_website=True,
        )
        .distinct()
        .prefetch_related("providers")
    )
    service_request_redirect = _build_service_request_redirect(request)
    if service_request_redirect:
        return service_request_redirect

    request_form, request_success = _build_service_request_form(
        request, service_meta, zone=zone
    )
    if request_form == "redirect":
        return redirect("interface:thank_you_quick_request")
    if request_form is None:
        return redirect(f"{request.path}?anchor=service-request")

    gallery_images = marketing_content.gallery
    hero_image = marketing_content.hero_image
    meta_description = marketing_content.meta_description

    service_schema = _build_service_schema(request, service_meta.name, zone.name)
    return render(
        request,
        "interface/service_page.html",
        {
            "service": service_meta,
            "zone": zone,
            "district": None,
            "providers": providers,
            "zones": _zone_options(zone),
            "intro": intro,
            "short_intro": short_intro,
            "long_description": long_description,
            "long_title": long_title,
            "city_intro": city_intro,
            "highlights": highlights,
            "hero_image": hero_image,
            "gallery_images": gallery_images,
            "meta_description": meta_description,
            "service_schema_json": json.dumps(service_schema, ensure_ascii=False),
            "request_form": request_form,
            "request_success": request_success,
            "sub_services": sub_services,
            "is_sub_service_page": False,
            "is_at_home_page": False,
            "page_service_name": service_meta.name,
            "seo_section_heading": f"{service_meta.name} : ce qu'il faut savoir",
            "seo_intro": intro,
            "seo_long_description": long_description,
            "support_phone_display": SUPPORT_PHONE_DISPLAY,
            "support_phone_tel": SUPPORT_PHONE_TEL,
        },
    )


def service_city_district_page(request, service_slug: str, city_slug: str, district_slug: str):
    service_meta = _get_service_or_404(service_slug)
    zone = _get_zone_or_404(district_slug)
    marketing_zone = MarketingZone.objects.filter(zone=zone).first()
    service_zone = MarketingServiceZone.objects.filter(service=service_meta, zone=zone).first()
    marketing_content = build_marketing_content(
        service=_apply_zone_marketing(service_meta, marketing_zone, service_zone),
        location_name=zone.name,
    )
    intro = marketing_content.intro
    short_intro = marketing_content.short_intro
    long_description = marketing_content.long_description
    long_title = marketing_content.long_title
    city_intro = marketing_content.location_intro
    highlights = marketing_content.highlights

    providers = list(
        Provider.objects.visible_on_website().filter(
            marketing_services__slug=service_slug,
            zones__slug=zone.slug,
        ).distinct()
    )
    sub_services = list(
        MarketingSubService.objects.filter(
            service=service_meta,
            is_visible=True,
            providers__zones__slug=zone.slug,
            providers__is_visible_on_website=True,
        )
        .distinct()
        .prefetch_related("providers")
    )
    service_request_redirect = _build_service_request_redirect(request)
    if service_request_redirect:
        return service_request_redirect

    request_form, request_success = _build_service_request_form(
        request, service_meta, zone=zone
    )
    if request_form == "redirect":
        return redirect("interface:thank_you_quick_request")
    if request_form is None:
        return redirect(f"{request.path}?anchor=service-request")

    gallery_images = marketing_content.gallery
    hero_image = marketing_content.hero_image or service_meta.resolved_main_image
    meta_description = marketing_content.meta_description

    service_schema = _build_service_schema(request, service_meta.name, zone.name)
    return render(
        request,
        "interface/service_page.html",
        {
            "service": service_meta,
            "zone": zone,
            "district": None,
            "providers": providers,
            "zones": _zone_options(zone),
            "intro": intro,
            "short_intro": short_intro,
            "long_description": long_description,
            "long_title": long_title,
            "city_intro": city_intro,
            "highlights": highlights,
            "hero_image": hero_image,
            "gallery_images": gallery_images,
            "meta_description": meta_description,
            "service_schema_json": json.dumps(service_schema, ensure_ascii=False),
            "request_form": request_form,
            "request_success": request_success,
            "sub_services": sub_services,
            "is_sub_service_page": False,
            "is_at_home_page": False,
            "page_service_name": service_meta.name,
            "seo_section_heading": f"{service_meta.name} : ce qu'il faut savoir",
            "seo_intro": intro,
            "seo_long_description": long_description,
            "support_phone_display": SUPPORT_PHONE_DISPLAY,
            "support_phone_tel": SUPPORT_PHONE_TEL,
        },
    )


def sub_service_page(request, service_slug: str, sub_service_slug: str):
    service_meta = _get_service_or_404(service_slug)
    sub_service = get_object_or_404(
        MarketingSubService,
        service=service_meta,
        slug=sub_service_slug,
        is_visible=True,
    )
    providers = list(
        Provider.objects.visible_on_website()
        .filter(marketing_sub_services=sub_service)
        .distinct()
    )

    service_request_redirect = _build_service_request_redirect(request)
    if service_request_redirect:
        return service_request_redirect

    request_form, request_success = _build_service_request_form(
        request, service_meta, zone=None, sub_service=sub_service
    )
    if request_form == "redirect":
        return redirect("interface:thank_you_quick_request")
    if request_form is None:
        return redirect(f"{request.path}?anchor=service-request")

    service_content = _to_service_content(service_meta)
    marketing_content = build_marketing_content(service=service_content)
    service_schema = _build_service_schema(request, sub_service.name, None)
    return render(
        request,
        "interface/service_page.html",
        {
            "service": service_meta,
            "sub_service": sub_service,
            "zone": None,
            "providers": providers,
            "zones": [],
            "intro": sub_service.intro or marketing_content.intro,
            "short_intro": sub_service.short_intro or marketing_content.short_intro,
            "long_description": marketing_content.long_description,
            "long_title": sub_service.name,
            "city_intro": marketing_content.location_intro,
            "highlights": marketing_content.highlights,
            "hero_image": sub_service.resolved_image or marketing_content.hero_image,
            "gallery_images": marketing_content.gallery,
            "meta_description": marketing_content.meta_description,
            "service_schema_json": json.dumps(service_schema, ensure_ascii=False),
            "request_form": request_form,
            "request_success": request_success,
            "sub_services": list(
                MarketingSubService.objects.filter(service=service_meta, is_visible=True)
            ),
            "is_sub_service_page": True,
            "is_at_home_page": False,
            "page_service_name": sub_service.name,
            "seo_section_heading": f"{sub_service.name} : l'essentiel",
            "seo_intro": sub_service.intro or marketing_content.intro,
            "seo_long_description": "",
            "support_phone_display": SUPPORT_PHONE_DISPLAY,
            "support_phone_tel": SUPPORT_PHONE_TEL,
        },
    )


def service_at_home_page(request, service_slug: str):
    service_meta = _get_service_or_404(service_slug)
    providers = list(
        Provider.objects.visible_on_website()
        .filter(marketing_services__slug=service_slug)
        .filter(
            location_mode__in=[
                Provider.LOCATION_MODE_CLIENT_HOME_ONLY,
                Provider.LOCATION_MODE_HYBRID,
            ]
        )
        .distinct()
    )

    service_content = _to_service_content(service_meta)
    marketing_content = build_marketing_content(service=service_content)
    page_service_name = f"{service_meta.name} à domicile"
    service_schema = _build_service_schema(request, page_service_name, None)
    return render(
        request,
        "interface/service_page.html",
        {
            "service": service_meta,
            "zone": None,
            "providers": providers,
            "zones": [],
            "intro": AT_HOME_MARKETING_COPY,
            "short_intro": AT_HOME_MARKETING_COPY,
            "long_description": "",
            "long_title": page_service_name,
            "city_intro": marketing_content.location_intro,
            "highlights": marketing_content.highlights,
            "hero_image": marketing_content.hero_image,
            "gallery_images": marketing_content.gallery,
            "meta_description": f"Trouve facilement {service_meta.name.lower()} à domicile à Toulouse.",
            "service_schema_json": json.dumps(service_schema, ensure_ascii=False),
            "request_form": None,
            "request_success": False,
            "sub_services": [],
            "is_sub_service_page": False,
            "is_at_home_page": True,
            "page_service_name": page_service_name,
            "seo_section_heading": f"{page_service_name} : comment ça marche",
            "seo_intro": AT_HOME_MARKETING_COPY,
            "seo_long_description": "",
            "support_phone_display": SUPPORT_PHONE_DISPLAY,
            "support_phone_tel": SUPPORT_PHONE_TEL,
        },
    )


def sub_service_at_home_page(request, service_slug: str, sub_service_slug: str):
    service_meta = _get_service_or_404(service_slug)
    sub_service = get_object_or_404(
        MarketingSubService,
        service=service_meta,
        slug=sub_service_slug,
        is_visible=True,
    )
    providers = list(
        Provider.objects.visible_on_website()
        .filter(marketing_sub_services=sub_service)
        .filter(
            location_mode__in=[
                Provider.LOCATION_MODE_CLIENT_HOME_ONLY,
                Provider.LOCATION_MODE_HYBRID,
            ]
        )
        .distinct()
    )

    service_content = _to_service_content(service_meta)
    marketing_content = build_marketing_content(service=service_content)
    page_service_name = f"{sub_service.name} à domicile"
    service_schema = _build_service_schema(request, page_service_name, None)
    return render(
        request,
        "interface/service_page.html",
        {
            "service": service_meta,
            "sub_service": sub_service,
            "zone": None,
            "providers": providers,
            "zones": [],
            "intro": AT_HOME_MARKETING_COPY,
            "short_intro": AT_HOME_MARKETING_COPY,
            "long_description": "",
            "long_title": page_service_name,
            "city_intro": marketing_content.location_intro,
            "highlights": marketing_content.highlights,
            "hero_image": sub_service.resolved_image or marketing_content.hero_image,
            "gallery_images": marketing_content.gallery,
            "meta_description": f"Trouve facilement {sub_service.name.lower()} à domicile à Toulouse.",
            "service_schema_json": json.dumps(service_schema, ensure_ascii=False),
            "request_form": None,
            "request_success": False,
            "sub_services": [],
            "is_sub_service_page": True,
            "is_at_home_page": True,
            "page_service_name": page_service_name,
            "seo_section_heading": f"{page_service_name} : comment ça marche",
            "seo_intro": AT_HOME_MARKETING_COPY,
            "seo_long_description": "",
            "support_phone_display": SUPPORT_PHONE_DISPLAY,
            "support_phone_tel": SUPPORT_PHONE_TEL,
        },
    )



def thank_you_question(request):
    return render(request, "interface/thank_you_question.html")


def thank_you_quick_request(request):
    return render(request, "interface/thank_you_quick_request.html")


def thank_you_provider_booking(request):
    provider_name = request.GET.get("provider", "").strip()
    provider_id = (request.GET.get("provider_id") or "").strip()
    provider_additional_info = ""
    if provider_id.isdigit():
        provider = Provider.objects.filter(id=int(provider_id)).only("additional_info").first()
        provider_additional_info = (getattr(provider, "additional_info", "") or "").strip()
    return render(
        request,
        "interface/thank_you_provider_booking.html",
        {
            "provider_name": provider_name,
            "provider_additional_info": provider_additional_info,
        },
    )


def cancel_booking_admin(request, booking_id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return HttpResponseForbidden("Accès réservé au staff")
    if request.method != "POST":
        return HttpResponseBadRequest("Méthode non autorisée")

    booking = get_object_or_404(Booking, booking_id=booking_id)
    if booking.status in (finalize_booking_uc.CANCELLED, finalize_booking_uc.CONFIRMED):
        return redirect(reverse("providers:booking_detail", args=[booking.booking_id]))

    try:
        finalized = finalize_booking_uc.execute(
            booking_id=booking_id,
            actor="admin",
            decision="cancel",
            now=timezone.now(),
            booking_repository=repo,
            payment_gateway=payment_gateway,
            provider_directory=provider_directory,
            notifier=notifier,
            operations_email=SUPPORT_EMAIL,
        )
    except finalize_booking_uc.InvalidState:
        return HttpResponseBadRequest("Impossible d'annuler cette demande.")

    return redirect(reverse("providers:booking_detail", args=[finalized.id]))

def legal(request):
    return render(request, "interface/legal.html")


def about(request):
    faq_items = [
        {
            "question": "Combien de temps pour obtenir une réponse ?",
            "answer": "La prestataire ou le prestataire qui correspond à ta demande te répond généralement en quelques heures avec un créneau clair.",
        },
        {
            "question": "Travaillez-vous à domicile ou en salon ?",
            "answer": "Les deux : déplacement à domicile possible, ou accueil chez la prestataire ou le prestataire / en salon partenaire selon la prestation.",
        },
        {
            "question": "Comment préparer ma demande ?",
            "answer": "Suis simplement les indications du formulaire, pensées pour aider la prestataire ou le prestataire à bien comprendre ton besoin.",
        },
        {
            "question": "Comment se passe le paiement ?",
            "answer": "Château Rose collecte uniquement ses frais de service en ligne ; la prestation coiffure se règle directement avec la prestataire ou le prestataire le jour du rendez-vous.",
        },
    ]

    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["question"],
                "acceptedAnswer": {"@type": "Answer", "text": item["answer"]},
            }
            for item in faq_items
        ],
    }
    return render(
        request,
        "interface/about.html",
        {
            "faq_items": faq_items,
            "faq_schema_json": json.dumps(faq_schema, ensure_ascii=False),
            "services": list(MarketingService.objects.all()),
        },
    )


def legal_notice(request):
    return render(request, "interface/legal_notice.html")


def terms_of_sale(request):
    return render(request, "interface/terms_of_sale.html")


def terms_of_use(request):
    return render(request, "interface/terms_of_use.html")


def privacy_policy(request):
    return render(request, "interface/privacy_policy.html")


def robots_txt(request):
    base_url = build_base_url(request)
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            f"Sitemap: {base_url}/sitemap.xml",
        ]
    )
    return HttpResponse(content, content_type="text/plain")
