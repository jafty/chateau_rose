import json
import os
from datetime import datetime

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from booking.models import Provider, Service, Zone
from chateaurose.domain.exceptions import DomainError
from chateaurose.domain.services.marketing_content import GalleryImage, ServiceContent, build_marketing_content
from chateaurose.domain.use_cases import finalize_booking as finalize_booking_uc
from chateaurose.domain.use_cases import request_haircut, update_proposal
from chateaurose.infrastructure.booking_repository import DjangoBookingRepository
from chateaurose.infrastructure.notifier_stub import NotifierStub
from chateaurose.infrastructure.payment_stub import PaymentGatewayStub
from chateaurose.infrastructure.provider_catalog import (
    DjangoProviderCatalog,
    SALON_LOCATION_LABEL,
)
from interface.forms import ServiceRequestForm
from interface.models import MarketingService, MarketingZone

repo = DjangoBookingRepository()
notifier = NotifierStub()
payment_gateway = PaymentGatewayStub()
provider_catalog = DjangoProviderCatalog()

FEATURED_SERVICE_SLUGS = ["tresses", "locks", "tissage", "vanilles"]


def _format_price(cents: int) -> str:
    euros = cents / 100
    if cents % 100 == 0:
        return f"{euros:.0f} €"
    return f"{euros:.2f} €"


def _save_upload(file_obj, prefix: str):
    if not file_obj:
        return None
    filename = file_obj.name
    return default_storage.save(os.path.join(prefix, filename), file_obj)


def _parse_desired_date(raw_value: str | None) -> str | None:
    if not raw_value:
        return None

    for date_format in ("%Y-%m-%dT%H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw_value, date_format)
            aware_date = timezone.make_aware(parsed)
            return aware_date.isoformat()
        except (ValueError, TypeError):
            continue

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


def provider_detail(request, provider_id):
    provider = get_object_or_404(Provider, id=provider_id)
    services = list(Service.objects.filter(provider=provider))
    pricing_data = {}
    starting_prices = []
    for service in services:
        service.price_display = _format_price(service.base_price_cents)
        adjustments = service.hair_length_adjustments or {}
        min_adj = min(adjustments.values()) if adjustments else 0
        starting_price = service.base_price_cents + min_adj
        starting_prices.append(starting_price)
        pricing_data[str(service.id)] = {
            "base": service.base_price_cents,
            "lengths": adjustments,
            "meche_bonus": service.meche_bonus_cents,
            "starting_from": starting_price,
        }
    zones = provider.zones.all()
    message = None
    error = None
    salon_location_label = SALON_LOCATION_LABEL

    if request.method == "POST":
        data = request.POST
        meche_bool = data.get("meche") == "on"
        location_choice = data.get("location")
        location_preference = data.get("location_preference")
        uploaded_current = request.FILES.get("current_hair_picture_file")
        desired_date = _parse_desired_date(data.get("desired_date"))

        location = location_choice or ""
        if provider.location_mode == Provider.LOCATION_MODE_SALON_ONLY:
            location = SALON_LOCATION_LABEL
            location_preference = "salon"
        elif provider.location_mode == Provider.LOCATION_MODE_HYBRID:
            if location_preference == "salon":
                location = SALON_LOCATION_LABEL
            elif location_preference == "domicile" or location_choice:
                location = location_choice or ""
                location_preference = location_preference or "domicile"
            else:
                error = "Merci de choisir si tu préfères venir au salon ou demander un déplacement."
        else:
            location_preference = location_preference or "domicile"

        if not location:
            error = "Merci de choisir un lieu."

        if not desired_date:
            error = "Merci d'utiliser une date au format JJ/MM/AAAA HH:MM."

        current_picture = _save_upload(uploaded_current, "bookings/current/") if uploaded_current else None
        if not current_picture and not error:
            error = "Merci d'ajouter une photo de tes cheveux."

        inspiration_paths = []
        for upload in request.FILES.getlist("inspiration_pictures"):
            saved = _save_upload(upload, "bookings/inspiration/")
            if saved:
                inspiration_paths.append(saved)

        if not error:
            try:
                booking = request_haircut.execute(
                    provider_id=str(provider.id),
                    service_id=data.get("service_id"),
                    client_contact={"name": data.get("client_name"), "phone": data.get("client_phone")},
                    location=location,
                    desired_date=desired_date,
                    hair_length=data.get("hair_length"),
                    meche=meche_bool,
                    current_hair_picture=current_picture,
                    inspiration_pictures=inspiration_paths,
                    free_text=data.get("free_text", ""),
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

    return render(
        request,
        "interface/provider_detail.html",
        {
            "provider": provider,
            "services": services,
            "zones": zones,
            "message": message,
            "error": error,
            "pricing_data": json.dumps(pricing_data),
            "default_starting_price": _format_price(min(starting_prices)) if starting_prices else None,
            "salon_location_label": salon_location_label,
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
        notifier=notifier,
    )
    return redirect("interface:home")


def _get_service_or_404(service_slug: str):
    return get_object_or_404(MarketingService, slug=service_slug)


def _get_zone_or_404(zone_slug: str):
    return get_object_or_404(Zone, slug=zone_slug)


def _zone_options(active_zone=None):
    zones = list(Zone.objects.all().order_by("name"))
    if active_zone and not any(zone.slug == active_zone.slug for zone in zones):
        zones.append(active_zone)
    return zones


def _build_service_request_form(request, service_meta: MarketingService | None, zone):
    form = ServiceRequestForm(request.POST or None)
    request_success = False

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
            record.save()
            request_success = True
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
        highlights=service_meta.highlights,
        main_image=service_meta.resolved_main_image,
        gallery=_gallery_from_service(service_meta),
        meta_description=service_meta.meta_description,
    )


def _apply_zone_marketing(service_meta: MarketingService, marketing_zone: MarketingZone):
    if not marketing_zone:
        return _to_service_content(service_meta)

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

    return ServiceContent(
        name=service_meta.name,
        intro=" ".join([part for part in intro_parts if part]),
        highlights=merged_highlights,
        main_image=marketing_zone.resolved_hero_image or service_meta.resolved_main_image,
        gallery=_gallery_from_service(service_meta),
        meta_description=meta_description,
    )


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
    city_intro = marketing_content.location_intro
    highlights = marketing_content.highlights
    meta_description = marketing_content.meta_description

    return render(
        request,
        "interface/service_page.html",
        {
            "service": service_meta,
            "zone": None,
            "providers": providers,
            "zones": _zone_options(),
            "intro": intro,
            "city_intro": city_intro,
            "highlights": highlights,
            "hero_image": hero_image,
            "gallery_images": gallery_images,
            "meta_description": meta_description,
            "request_form": request_form,
            "request_success": request_success,
        },
    )


def service_city_page(request, service_slug: str, city_slug: str):
    service_meta = _get_service_or_404(service_slug)
    zone = _get_zone_or_404(city_slug)
    marketing_zone = MarketingZone.objects.filter(zone=zone).first()
    marketing_content = build_marketing_content(
        service=_apply_zone_marketing(service_meta, marketing_zone),
        location_name=zone.name,
    )
    intro = marketing_content.intro
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
            "city_intro": city_intro,
            "highlights": highlights,
            "hero_image": hero_image,
            "gallery_images": gallery_images,
            "meta_description": meta_description,
            "request_form": request_form,
            "request_success": request_success,
        },
    )


def service_city_district_page(request, service_slug: str, city_slug: str, district_slug: str):
    service_meta = _get_service_or_404(service_slug)
    zone = _get_zone_or_404(district_slug)
    marketing_zone = MarketingZone.objects.filter(zone=zone).first()
    marketing_content = build_marketing_content(
        service=_apply_zone_marketing(service_meta, marketing_zone),
        location_name=zone.name,
    )
    intro = marketing_content.intro
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
            "city_intro": city_intro,
            "highlights": highlights,
            "hero_image": hero_image,
            "gallery_images": gallery_images,
            "meta_description": meta_description,
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
            "answer": "Le prestataire qui correspond à ta demande te répond généralement en quelques heures avec un créneau clair.",
        },
        {
            "question": "Travaillez-vous à domicile ou en salon ?",
            "answer": "Les deux : déplacement à domicile possible, ou accueil chez le prestataire / en salon partenaire selon la prestation.",
        },
        {
            "question": "Comment préparer ma demande ?",
            "answer": "Suis simplement les indications du formulaire, pensées pour aider le prestataire à bien comprendre ton besoin.",
        },
        {
            "question": "Comment se passe le paiement ?",
            "answer": "Une empreinte bancaire est prise : l'acompte n'est validé qu'après accord commun avec le prestataire, puis le reste se règle directement avec lui (cash, Lydia...).",
        },
    ]

    return render(
        request,
        "interface/about.html",
        {
            "faq_items": faq_items,
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
