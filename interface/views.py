import json
import uuid

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
from django.views.decorators.http import require_POST
from django.urls import reverse

from booking.models import Booking, Provider, Service, ServiceCategory, Zone
from chateaurose.domain.exceptions import DomainError, ValidationError
from chateaurose.domain.services.marketing_content import GalleryImage, ServiceContent, build_marketing_content
from chateaurose.domain.services.pricing import estimate_service_price_cents
from chateaurose.domain.use_cases import finalize_booking as finalize_booking_uc
from chateaurose.domain.use_cases import request_haircut, update_proposal
from chateaurose.infrastructure.booking_repository import DjangoBookingRepository
from chateaurose.infrastructure.stripe_gateway import StripePaymentGateway
from chateaurose.infrastructure.email_notifier import EmailNotifier
from chateaurose.infrastructure.provider_directory import DjangoProviderDirectory
from chateaurose.infrastructure.provider_catalog import (
    DjangoProviderCatalog,
    SALON_LOCATION_LABEL,
)
from interface.forms import ProviderBookingRequestForm, ServiceRequestForm
from interface.marketing_cities import CITY_PAGE_COPY, MARKETING_CITY_ENTRIES
from interface.models import (
    ClientReview,
    MarketingService,
    MarketingServiceZone,
    MarketingZone,
    QuickCheckoutPage,
)
from interface.services import booking_requests
from chateaurose.seo import build_base_url

repo = DjangoBookingRepository()
notifier = EmailNotifier()
payment_gateway = StripePaymentGateway()
provider_catalog = DjangoProviderCatalog()
provider_directory = DjangoProviderDirectory()

FEATURED_SERVICE_SLUGS = ["tresses", "locks", "tissage", "vanilles"]


def _first_form_error(form: forms.Form) -> str | None:
    non_field_errors = form.non_field_errors()
    if non_field_errors:
        return non_field_errors[0]
    for field_errors in form.errors.values():
        if field_errors:
            return field_errors[0]
    return None


def home(request):
    providers = Provider.objects.all()
    zones = Zone.objects.all()
    services = list(MarketingService.objects.all())
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
    request_form, request_success = _build_service_request_form(request, service_meta=None, zone=None)
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
    providers = list(Provider.objects.filter(zones__slug=zone.slug).distinct())
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
    providers = Provider.objects.all()
    return render(request, "interface/provider_list.html", {"providers": providers})


def at_home_provider_list(request):
    providers = Provider.objects.filter(
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
    error = None
    salon_location_label = SALON_LOCATION_LABEL
    stripe_public_key = settings.STRIPE_PUBLIC_KEY
    require_payment_auth = bool(stripe_public_key)
    prefilled_payment_auth_id = ""
    payment_message = None
    fixed_price_cents = None

    if quick_checkout is not None:
        fixed_price_cents = quick_checkout.fixed_price_cents

    if request.method == "GET":
        prefilled_payment_auth_id = (request.GET.get("payment_auth_id") or "").strip()
        if prefilled_payment_auth_id:
            payment_message = (
                "Empreinte bancaire confirmée. Tu peux finaliser l'envoi de ta demande."
            )

    if request.method == "POST":
        form = ProviderBookingRequestForm(
            request.POST,
            request.FILES,
            provider=provider,
            require_payment_auth=require_payment_auth,
            require_current_hair_picture=True,
        )
        if form.is_valid():
            current_hair_picture_file = form.cleaned_data.get("current_hair_picture_file")
            if current_hair_picture_file:
                current_picture = booking_requests.save_current_hair_picture(current_hair_picture_file)
            else:
                current_picture = (form.cleaned_data.get("current_hair_picture") or "").strip()
            inspiration_paths = booking_requests.save_inspiration_pictures(
                form.get_inspiration_files()
            )
            booking_detail_path = reverse("providers:booking_detail", args=["BOOKING_ID"])
            provider_booking_url_base = request.build_absolute_uri(
                booking_detail_path.replace("BOOKING_ID/", "")
            )
            try:
                booking = request_haircut.execute(
                    provider_id=str(provider.id),
                    service_id=form.cleaned_data.get("service_id"),
                    client_contact={
                        "name": form.cleaned_data.get("client_name"),
                        "email": form.cleaned_data.get("client_email"),
                    },
                    location=form.cleaned_data.get("location"),
                    location_preference=form.cleaned_data.get("location_preference"),
                    client_address=form.cleaned_data.get("client_address"),
                    desired_date=form.cleaned_data.get("desired_date"),
                    hair_length=form.cleaned_data.get("hair_length"),
                    general_adjustment=form.cleaned_data.get("general_adjustment"),
                    meche=form.cleaned_data.get("meche", False),
                    current_hair_picture=current_picture,
                    inspiration_pictures=inspiration_paths,
                    free_text=form.cleaned_data.get("free_text", ""),
                    payment_auth_id=form.cleaned_data.get("payment_auth_id"),
                    provider_booking_url_base=provider_booking_url_base,
                    provider_salon_zone=provider.salon_zone,
                    booking_repository=repo,
                    provider_catalog=provider_catalog,
                    payment_gateway=payment_gateway,
                    notifier=notifier,
                    reminder_gateway=None,
                    clock=type("Clock", (), {"now": timezone.now}),
                )
                message = f"Demande envoyée. ID: {booking.id}"
            except DomainError as exc:
                error = str(exc)
        else:
            error = _first_form_error(form)

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

    return render(
        request,
        "interface/provider_detail.html",
        {
            "provider": provider,
            "services": services,
            "service_categories": service_categories,
            "zones": zones,
            "message": message,
            "error": error,
            "pricing_data": json.dumps(pricing_data),
            "default_starting_price": (
                booking_requests.format_price(min(starting_prices)) if starting_prices else None
            ),
            "salon_location_label": salon_location_label,
            "stripe_public_key": stripe_public_key,
            "payment_auth_id": prefilled_payment_auth_id,
            "payment_message": payment_message,
            "fixed_price_cents": fixed_price_cents,
            "quick_checkout": quick_checkout,
            "is_quick_checkout": quick_checkout is not None,
            "quick_checkout_id": quick_checkout.id if quick_checkout else "",
        },
    )


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
    require_payment_auth = bool(stripe_public_key)
    message = None
    error = None
    payment_message = None
    prefilled_payment_auth_id = ""

    if request.method == "GET":
        prefilled_payment_auth_id = (request.GET.get("payment_auth_id") or "").strip()
        if prefilled_payment_auth_id:
            payment_message = (
                "Empreinte bancaire confirmée. Tu peux finaliser l'envoi de ta demande."
            )

    if request.method == "POST":
        payment_auth_id = (request.POST.get("payment_auth_id") or "").strip()
        if require_payment_auth and not payment_auth_id:
            error = "Merci d'ajouter une empreinte bancaire pour sécuriser la demande."
        else:
            booking_detail_path = reverse("providers:booking_detail", args=["BOOKING_ID"])
            provider_booking_url_base = request.build_absolute_uri(
                booking_detail_path.replace("BOOKING_ID/", "")
            )
            try:
                booking = request_haircut.execute(
                    provider_id=str(provider.id),
                    service_id=checkout.service_id,
                    client_contact={
                        "name": checkout.client_name,
                        "email": checkout.client_email,
                    },
                    location=checkout.location,
                    location_preference=checkout.location_preference,
                    client_address=checkout.client_address,
                    desired_date=checkout.desired_date.isoformat(),
                    hair_length=checkout.hair_length,
                    general_adjustment=checkout.general_adjustment,
                    meche=checkout.meche,
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
                )

                booking_row = Booking.objects.filter(booking_id=booking.id).first()
                if booking_row:
                    booking_row.estimated_price_cents = checkout.fixed_price_cents
                    booking_row.save(update_fields=["estimated_price_cents", "updated_at"])
                checkout.completed_at = timezone.now()
                checkout.is_active = False
                checkout.save(update_fields=["completed_at", "is_active", "updated_at"])

                message = f"Demande envoyée. ID: {booking.id}"
            except DomainError as exc:
                error = str(exc)

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
            "quick_checkout_id": checkout.id,
            "fixed_price_cents": checkout.fixed_price_cents,
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
    general_adjustment = payload.get("general_adjustment")
    meche = payload.get("meche")
    location_preference = payload.get("location_preference")
    quick_checkout_id = payload.get("quick_checkout_id")

    quick_checkout = None
    if quick_checkout_id:
        quick_checkout = QuickCheckoutPage.objects.filter(
            id=quick_checkout_id,
            is_active=True,
            completed_at__isnull=True,
        ).first()
        if quick_checkout is None:
            return JsonResponse({"error": "Lien checkout invalide."}, status=400)

        amount_cents = quick_checkout.fixed_price_cents
    else:
        if not all([provider_id, service_id]) or meche is None:
            return JsonResponse({"error": "Informations manquantes."}, status=400)

        try:
            service = provider_catalog.get_service(provider_id, service_id)
        except KeyError:
            return JsonResponse({"error": "Service non disponible."}, status=400)

        try:
            estimated_price_cents, _, _ = estimate_service_price_cents(
                service=service,
                hair_length=hair_length,
                general_adjustment=general_adjustment,
                meche=meche,
                location_preference=location_preference,
            )
        except ValidationError as exc:
            message = str(exc)
            if "hair_length" in message:
                return JsonResponse({"error": "Longueur de cheveux non supportée."}, status=400)
            if "General adjustment" in message:
                return JsonResponse({"error": "Supplément non supporté."}, status=400)
            return JsonResponse({"error": "Informations manquantes."}, status=400)

        deposit_percentage = service.get("deposit_percentage")
        if deposit_percentage is not None:
            amount_cents = round(estimated_price_cents * deposit_percentage / 100)
        else:
            amount_cents = service.get("deposit_cents")
        if amount_cents is None:
            return JsonResponse({"error": "Acompte non défini."}, status=400)

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

    if status in success_statuses:
        headline = "Empreinte bancaire confirmée"
        tone = "success"
        message = (
            "Ton empreinte bancaire a bien été enregistrée. Tu peux maintenant finaliser ta demande."
        )
    elif status in failure_statuses:
        headline = "Empreinte bancaire refusée"
        tone = "error"
        message = "La banque a refusé la carte. Tu peux réessayer avec un autre moyen."
    else:
        headline = "Empreinte bancaire en attente"
        tone = "warning"
        message = (
            "Nous n'avons pas pu confirmer immédiatement l'empreinte bancaire. "
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
            if status in success_statuses and intent_id:
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
    final_booking = finalize_booking_uc.execute(
        booking_id=booking_id,
        actor="provider",
        decision=decision,
        now=timezone.now(),
        booking_repository=repo,
        payment_gateway=payment_gateway,
        provider_directory=provider_directory,
        notifier=notifier,
    )
    return redirect("interface:home")


def client_action(request, booking_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Méthode non autorisée")
    decision = request.POST.get("decision")
    final_booking = finalize_booking_uc.execute(
        booking_id=booking_id,
        actor="client",
        decision=decision,
        now=timezone.now(),
        booking_repository=repo,
        payment_gateway=payment_gateway,
        provider_directory=provider_directory,
        notifier=notifier,
    )
    return redirect("interface:client_confirmation", booking_id=final_booking.id)


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
            "client_moves": client_moves,
            "provider_email": booking.provider.contact_email or "Non communiqué",
            "provider_phone": booking.provider.contact_phone or "Non communiqué",
            "provider_salon_address": booking.provider.salon_address or "Adresse à confirmer",
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
    desired_date = timezone.localtime(record.desired_date).strftime("%d/%m/%Y %H:%M")
    zone_name = record.zone.name if record.zone else "Non précisé"
    location_preference = record.get_location_preference_display()
    subject = f"Nouvelle demande rapide - {record.marketing_service.name}"
    body_lines = [
        f"Service : {record.marketing_service.name}",
        f"Client·e : {record.client_name} ({record.client_email})",
        f"Date souhaitée : {desired_date}",
        f"Lieu préféré : {location_preference}",
        f"Zone : {zone_name}",
        f"Adresse : {record.client_address or 'Non communiquée'}",
        f"Longueur cheveux : {record.hair_length or 'Non précisée'}",
        f"Mèches déjà fournies : {'Oui' if record.meche_provided else 'Non'}",
        f"Photos : {", ".join(record.inspiration_picture_urls) if record.inspiration_picture_urls else 'Non communiquées'}",
        "Détails :",
        record.details or "Aucun détail supplémentaire.",
    ]
    notifier.notify("japhet.situmonana@gmail.com", subject, "\n".join(body_lines))


def _get_homepage_reviews(limit: int = 6) -> list[ClientReview]:
    featured = list(ClientReview.objects.filter(is_active=True, is_featured=True).order_by("-created_at")[:limit])
    if len(featured) >= limit:
        return featured

    extra = list(
        ClientReview.objects.filter(is_active=True, is_featured=False)
        .order_by("-created_at")[: max(limit - len(featured), 0)]
    )
    return featured + extra


def _build_service_request_form(request, service_meta: MarketingService | None, zone):
    form = ServiceRequestForm(request.POST or None, request.FILES or None)
    request_success = request.session.pop("service_request_success", False)

    if service_meta:
        form.fields["marketing_service"].initial = service_meta
        form.fields["marketing_service"].widget = forms.HiddenInput()
        form.fields["marketing_service"].required = False
    if zone:
        form.fields["zone"].initial = zone
        form.fields["zone"].widget = forms.HiddenInput()
        form.fields["zone"].required = False

    if request.method == "POST" and request.POST.get("request_service") == "1":
        if form.is_valid():
            record = form.save(commit=False)
            record.marketing_service = service_meta or form.cleaned_data.get("marketing_service")
            if zone:
                record.zone = zone
            inspiration_paths = booking_requests.save_inspiration_pictures(form.cleaned_data.get("inspiration_pictures") or [])
            record.inspiration_picture_urls = inspiration_paths
            record.save()
            _notify_service_request(record)
            request_success = True
            request.session["service_request_success"] = True
            form = ServiceRequestForm()
            if service_meta:
                form.fields["marketing_service"].initial = service_meta
                form.fields["marketing_service"].widget = forms.HiddenInput()
                form.fields["marketing_service"].required = False
            if zone:
                form.fields["zone"].initial = zone
                form.fields["zone"].widget = forms.HiddenInput()
                form.fields["zone"].required = False

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


def service_page(request, service_slug: str):
    service_meta = _get_service_or_404(service_slug)
    providers = list(
        Provider.objects.filter(marketing_services__slug=service_slug).distinct()
    )
    request_form, request_success = _build_service_request_form(
        request, service_meta, zone=None
    )
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
        Provider.objects.filter(
            marketing_services__slug=service_slug,
            zones__slug=zone.slug,
        ).distinct()
    )
    request_form, request_success = _build_service_request_form(
        request, service_meta, zone=zone
    )

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
        Provider.objects.filter(
            marketing_services__slug=service_slug,
            zones__slug=zone.slug,
        ).distinct()
    )
    request_form, request_success = _build_service_request_form(
        request, service_meta, zone=zone
    )

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
        },
    )


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
            "answer": "Une empreinte bancaire est prise : l'acompte n'est validé qu'après accord commun avec la prestataire ou le prestataire, puis le reste se règle directement avec elle ou lui (cash, Lydia...).",
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
