import os

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from booking.models import Provider, Service, Zone
from chateaurose.domain.exceptions import DomainError
from chateaurose.domain.use_cases import finalize_booking as finalize_booking_uc
from chateaurose.domain.use_cases import request_haircut, update_proposal
from chateaurose.infrastructure.booking_repository import DjangoBookingRepository
from chateaurose.infrastructure.notifier_stub import NotifierStub
from chateaurose.infrastructure.payment_stub import PaymentGatewayStub
from chateaurose.infrastructure.provider_catalog import DjangoProviderCatalog
from interface.models import (
    MarketingCity,
    MarketingDistrict,
    MarketingService,
    MarketingServiceCity,
)

repo = DjangoBookingRepository()
notifier = NotifierStub()
payment_gateway = PaymentGatewayStub()
provider_catalog = DjangoProviderCatalog()

FEATURED_SERVICE_SLUGS = ["tresses", "locks", "tissage", "vanilles"]


def _default_highlights(service_name: str):
    return [
        "Temps de réponse rapide : on vous propose un créneau en quelques minutes.",
        "Brief clair : longueur, mèches fournies ou non, inspirations via photos ou liens.",
        f"Artistes spécialisés pour {service_name.lower()} à domicile ou en salon partenaire.",
    ]


def _save_upload(file_obj, prefix: str):
    if not file_obj:
        return None
    filename = file_obj.name
    return default_storage.save(os.path.join(prefix, filename), file_obj)


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
    return render(
        request,
        "interface/home.html",
        {
            "providers": providers,
            "zones": zones,
            "services": services,
            "featured_services": featured_services,
            "cities": list(MarketingCity.objects.all()),
        },
    )


def provider_list(request):
    providers = Provider.objects.all()
    return render(request, "interface/provider_list.html", {"providers": providers})


def provider_detail(request, provider_id):
    provider = get_object_or_404(Provider, id=provider_id)
    services = Service.objects.filter(provider=provider)
    zones = Zone.objects.filter(zone_providers__provider=provider)
    message = None
    error = None

    if request.method == "POST":
        data = request.POST
        meche_bool = data.get("meche") == "on"
        current_picture = data.get("current_hair_picture")
        uploaded_current = request.FILES.get("current_hair_picture_file")
        if uploaded_current:
            current_picture = _save_upload(uploaded_current, "bookings/current/")

        inspiration_paths = []
        for upload in request.FILES.getlist("inspiration_pictures"):
            saved = _save_upload(upload, "bookings/inspiration/")
            if saved:
                inspiration_paths.append(saved)

        try:
            booking = request_haircut.execute(
                provider_id=str(provider.id),
                service_id=data.get("service_id"),
                client_contact={"name": data.get("client_name"), "phone": data.get("client_phone")},
                location=data.get("location"),
                desired_date=data.get("desired_date"),
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
        {"provider": provider, "services": services, "zones": zones, "message": message, "error": error},
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


def _get_city_or_404(city_slug: str):
    return get_object_or_404(MarketingCity, slug=city_slug)


def _get_districts_for_city(city_slug: str):
    return list(MarketingDistrict.objects.filter(city__slug=city_slug))


def _get_district_or_404(city_slug: str, district_slug: str):
    return get_object_or_404(MarketingDistrict, city__slug=city_slug, slug=district_slug)


def _city_options(active_city=None):
    preferred_cities = list(MarketingCity.objects.all()[:6])
    if active_city and not any(city.slug == active_city.slug for city in preferred_cities):
        preferred_cities.append(active_city)
    return preferred_cities


def _merge_highlights(base_highlights, *, service_name: str, city=None, city_override=None):
    if city_override and city_override.highlights:
        return city_override.highlights

    highlights = base_highlights or []
    if not highlights:
        highlights = _default_highlights(service_name)

    if city and not (city_override and city_override.highlights):
        return [f"{highlight} ({city.name})" for highlight in highlights]
    return highlights


def _build_service_copy(service_meta, city_meta=None, city_override=None):
    base_intro = (
        service_meta.intro
        or f"{service_meta.name} réalisées par des coiffeuses afro sélectionnées, avec prise de rendez-vous simplifiée."
    )
    if city_meta:
        if city_override and city_override.intro:
            city_intro = city_override.intro
        else:
            city_intro = f"{base_intro} Nous intervenons à {city_meta.name} et ses quartiers avec des artistes locaux."
    else:
        city_intro = "Prestataires mobiles ou en salon sur Toulouse métropole."

    highlights = _merge_highlights(
        service_meta.highlights, service_name=service_meta.name, city=city_meta, city_override=city_override
    )
    return base_intro, city_intro, highlights


def service_page(request, service_slug: str):
    service_meta = _get_service_or_404(service_slug)
    providers = Provider.objects.filter(services__slug=service_slug).distinct()
    intro, city_intro, highlights = _build_service_copy(service_meta)
    hero_image = service_meta.main_image
    gallery_images = list(service_meta.images.all())

    meta_description = (
        service_meta.meta_description
        or f"{service_meta.name} par des coiffeuses afro sélectionnées. Réservation rapide à Toulouse et alentours."
    )

    return render(
        request,
        "interface/service_page.html",
        {
            "service": service_meta,
            "city": None,
            "district": None,
            "providers": providers,
            "cities": _city_options(),
            "districts": [],
            "intro": intro,
            "city_intro": city_intro,
            "highlights": highlights,
            "hero_image": hero_image,
            "gallery_images": gallery_images,
            "meta_description": meta_description,
        },
    )


def service_city_page(request, service_slug: str, city_slug: str):
    service_meta = _get_service_or_404(service_slug)
    city_meta = _get_city_or_404(city_slug)
    district_list = _get_districts_for_city(city_slug)
    district_slugs = [d.slug for d in district_list]
    service_city_override = MarketingServiceCity.objects.filter(service=service_meta, city=city_meta).first()
    intro, city_intro, highlights = _build_service_copy(service_meta, city_meta, service_city_override)

    if service_city_override and service_city_override.intro:
        intro = service_city_override.intro

    providers = (
        Provider.objects.filter(
            services__slug=service_slug,
            provider_zones__zone__slug__in=[city_slug, *district_slugs],
        )
        .distinct()
    )

    if service_city_override and service_city_override.images.exists():
        gallery_images = list(service_city_override.images.all())
    else:
        gallery_images = list(service_meta.images.all())

    hero_image = (
        (service_city_override and service_city_override.main_image)
        or city_meta.main_image
        or service_meta.main_image
    )

    meta_description = (
        (service_city_override and service_city_override.meta_description)
        or service_meta.meta_description
        or f"{service_meta.name} par des coiffeuses afro à {city_meta.name} et ses quartiers, réservation rapide."
    )

    return render(
        request,
        "interface/service_page.html",
        {
            "service": service_meta,
            "city": city_meta,
            "district": None,
            "providers": providers,
            "cities": _city_options(city_meta),
            "districts": district_list,
            "intro": intro,
            "city_intro": city_intro,
            "highlights": highlights,
            "hero_image": hero_image,
            "gallery_images": gallery_images,
            "meta_description": meta_description,
        },
    )


def service_city_district_page(request, service_slug: str, city_slug: str, district_slug: str):
    service_meta = _get_service_or_404(service_slug)
    city_meta = _get_city_or_404(city_slug)
    district_meta = _get_district_or_404(city_slug, district_slug)
    service_city_override = MarketingServiceCity.objects.filter(service=service_meta, city=city_meta).first()
    intro, city_intro, highlights = _build_service_copy(service_meta, city_meta, service_city_override)

    if service_city_override and service_city_override.intro:
        intro = service_city_override.intro

    providers = (
        Provider.objects.filter(
            services__slug=service_slug,
            provider_zones__zone__slug=district_slug,
        )
        .distinct()
    )

    if service_city_override and service_city_override.images.exists():
        gallery_images = list(service_city_override.images.all())
    else:
        gallery_images = list(service_meta.images.all())

    hero_image = (
        (service_city_override and service_city_override.main_image)
        or district_meta.city.main_image
        or service_meta.main_image
    )

    meta_description = (
        (service_city_override and service_city_override.meta_description)
        or service_meta.meta_description
        or f"{service_meta.name} par des artistes afro à {district_meta.name}, {city_meta.name}. Réservation en quelques minutes."
    )

    return render(
        request,
        "interface/service_page.html",
        {
            "service": service_meta,
            "city": city_meta,
            "district": district_meta,
            "providers": providers,
            "cities": _city_options(city_meta),
            "districts": _get_districts_for_city(city_slug),
            "intro": intro,
            "city_intro": city_intro,
            "highlights": highlights,
            "hero_image": hero_image,
            "gallery_images": gallery_images,
            "meta_description": meta_description,
        },
    )


def about(request):
    faq_items = [
        {
            "question": "Combien de temps pour obtenir une réponse ?",
            "answer": "Nous revenons vers vous en quelques minutes avec une proposition d'artiste et un créneau précis.",
        },
        {
            "question": "Travaillez-vous à domicile ou en salon ?",
            "answer": "Les deux : certaines prestations sont réalisées chez vous, d'autres en salon partenaire, selon vos préférences.",
        },
        {
            "question": "Comment préparer ma demande ?",
            "answer": "Ajoutez des photos d'inspiration, précisez la longueur souhaitée et indiquez si vous avez besoin de mèches.",
        },
        {
            "question": "Comment se passe le paiement ?",
            "answer": "Le paiement est sécurisé une fois l'artiste validé et le devis confirmé ensemble.",
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
