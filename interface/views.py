import json
import uuid

from django import forms
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.conf import settings
from django.utils import timezone

from booking.models import Provider, Service, Zone
from chateaurose.domain.exceptions import DomainError
from chateaurose.domain.services.marketing_content import GalleryImage, ServiceContent, build_marketing_content
from chateaurose.domain.use_cases import finalize_booking as finalize_booking_uc
from chateaurose.domain.use_cases import request_haircut, update_proposal
from chateaurose.infrastructure.booking_repository import DjangoBookingRepository
from chateaurose.infrastructure.stripe_gateway import StripePaymentGateway
from chateaurose.infrastructure.email_notifier import EmailNotifier
from chateaurose.infrastructure.provider_catalog import (
    DjangoProviderCatalog,
    SALON_LOCATION_LABEL,
)
from interface.forms import ProviderBookingRequestForm, ServiceRequestForm
from interface.models import MarketingService, MarketingZone
from interface.services import booking_requests

repo = DjangoBookingRepository()
notifier = EmailNotifier()
payment_gateway = StripePaymentGateway()
provider_catalog = DjangoProviderCatalog()

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
    pricing_data, starting_prices = booking_requests.build_pricing_data(services)
    zones = provider.zones.all()
    message = None
    error = None
    salon_location_label = SALON_LOCATION_LABEL
    stripe_public_key = settings.STRIPE_PUBLIC_KEY
    require_payment_auth = bool(stripe_public_key)

    if request.method == "POST":
        form = ProviderBookingRequestForm(
            request.POST,
            request.FILES,
            provider=provider,
            require_payment_auth=require_payment_auth,
        )
        if form.is_valid():
            current_picture = booking_requests.save_current_hair_picture(
                form.cleaned_data["current_hair_picture_file"]
            )
            inspiration_paths = booking_requests.save_inspiration_pictures(
                form.get_inspiration_files()
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
                    desired_date=form.cleaned_data.get("desired_date"),
                    hair_length=form.cleaned_data.get("hair_length"),
                    meche=form.cleaned_data.get("meche", False),
                    current_hair_picture=current_picture,
                    inspiration_pictures=inspiration_paths,
                    free_text=form.cleaned_data.get("free_text", ""),
                    payment_auth_id=form.cleaned_data.get("payment_auth_id"),
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
            "default_starting_price": (
                booking_requests.format_price(min(starting_prices)) if starting_prices else None
            ),
            "salon_location_label": salon_location_label,
            "stripe_public_key": stripe_public_key,
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
    meche = payload.get("meche")

    if not all([provider_id, service_id, hair_length]) or meche is None:
        return JsonResponse({"error": "Informations manquantes."}, status=400)

    try:
        service = provider_catalog.get_service(provider_id, service_id)
    except KeyError:
        return JsonResponse({"error": "Service non disponible."}, status=400)

    length_adjustments = service.get("hair_length_adjustments", {})
    if hair_length not in length_adjustments:
        return JsonResponse({"error": "Longueur de cheveux non supportée."}, status=400)

    base_price = service["base_price_cents"]
    length_adj = length_adjustments[hair_length]
    meche_bonus = service.get("meche_bonus_cents", 0) if meche else 0
    estimated_price = base_price + length_adj + meche_bonus

    intent = payment_gateway.create_payment_intent(
        amount_cents=estimated_price,
        currency="EUR",
        reference=f"estimate-{uuid.uuid4().hex[:10]}",
    )

    return JsonResponse(
        {
            "client_secret": intent["client_secret"],
            "payment_auth_id": intent["id"],
            "amount_cents": estimated_price,
        }
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
