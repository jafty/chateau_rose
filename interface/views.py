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
from interface import seo

repo = DjangoBookingRepository()
notifier = NotifierStub()
payment_gateway = PaymentGatewayStub()
provider_catalog = DjangoProviderCatalog()


def _save_upload(file_obj, prefix: str):
    if not file_obj:
        return None
    filename = file_obj.name
    return default_storage.save(os.path.join(prefix, filename), file_obj)


def home(request):
    providers = Provider.objects.all()
    zones = Zone.objects.all()
    return render(
        request,
        "interface/home.html",
        {
            "providers": providers,
            "zones": zones,
            "services": seo.SERVICES,
            "cities": seo.CITIES,
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
    for service in seo.SERVICES:
        if service["slug"] == service_slug:
            return service
    raise Http404()


def _get_city_or_404(city_slug: str):
    for city in seo.CITIES:
        if city["slug"] == city_slug:
            return city
    raise Http404()


def _get_districts_for_city(city_slug: str):
    return seo.DISTRICTS_BY_CITY.get(city_slug, [])


def _get_district_or_404(city_slug: str, district_slug: str):
    for district in _get_districts_for_city(city_slug):
        if district["slug"] == district_slug:
            return district
    raise Http404()


def service_page(request, service_slug: str):
    service_meta = _get_service_or_404(service_slug)
    providers = Provider.objects.filter(services__slug=service_slug).distinct()

    return render(
        request,
        "interface/service_page.html",
        {
            "service": service_meta,
            "city": None,
            "district": None,
            "providers": providers,
            "cities": seo.CITIES,
            "districts": [],
        },
    )


def service_city_page(request, service_slug: str, city_slug: str):
    service_meta = _get_service_or_404(service_slug)
    city_meta = _get_city_or_404(city_slug)
    district_list = _get_districts_for_city(city_slug)
    district_slugs = [d["slug"] for d in district_list]

    providers = (
        Provider.objects.filter(
            services__slug=service_slug,
            provider_zones__zone__slug__in=[city_slug, *district_slugs],
        )
        .distinct()
    )

    return render(
        request,
        "interface/service_page.html",
        {
            "service": service_meta,
            "city": city_meta,
            "district": None,
            "providers": providers,
            "cities": seo.CITIES,
            "districts": district_list,
        },
    )


def service_city_district_page(request, service_slug: str, city_slug: str, district_slug: str):
    service_meta = _get_service_or_404(service_slug)
    city_meta = _get_city_or_404(city_slug)
    district_meta = _get_district_or_404(city_slug, district_slug)

    providers = (
        Provider.objects.filter(
            services__slug=service_slug,
            provider_zones__zone__slug=district_slug,
        )
        .distinct()
    )

    return render(
        request,
        "interface/service_page.html",
        {
            "service": service_meta,
            "city": city_meta,
            "district": district_meta,
            "providers": providers,
            "cities": seo.CITIES,
            "districts": _get_districts_for_city(city_slug),
        },
    )
