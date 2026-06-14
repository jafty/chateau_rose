from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from import_export.admin import ImportExportModelAdmin

from booking.resources import (
    ProviderMarketingServiceResource,
    ProviderPhotoResource,
    ProviderResource,
    ProviderZoneResource,
    ServiceResource,
    ZoneResource,
)

from .models import (
    Booking,
    Provider,
    ProviderBeforeAppointmentItem,
    ProviderMarketingService,
    ProviderBlockedSlot,
    ProviderPhoto,
    ProviderServiceFeeCoupon,
    ProviderZone,
    Service,
    ServiceCategory,
    Zone,
)
from interface.models import MarketingService, MarketingSubService, ProviderBookingDraft
from chateaurose.domain.exceptions import DomainError
from chateaurose.domain.use_cases import assign_provider_to_booking
from chateaurose.infrastructure.booking_repository import DjangoBookingRepository
from chateaurose.infrastructure.email_notifier import EmailNotifier
from chateaurose.infrastructure.provider_catalog import DjangoProviderCatalog
from interface.services.booking_requests import resolve_stored_media_url
from interface.services.image_processing import compress_image_field


class MarketingSubServiceMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.service.name} · {obj.name}"


class BookingProviderAssignmentForm(forms.Form):
    provider = forms.ModelChoiceField(
        queryset=Provider.objects.order_by("name"),
        label="Prestataire",
    )
    service = forms.ModelChoiceField(
        queryset=Service.objects.select_related("provider").order_by("provider__name", "name"),
        label="Service prestataire",
    )
    compatibility_override = forms.BooleanField(
        required=False,
        label="Forcer malgré une incompatibilité d'intention",
        help_text="À utiliser uniquement pour les anciennes demandes dont le rattachement marketing est incomplet.",
    )

    def clean(self):
        cleaned_data = super().clean()
        provider = cleaned_data.get("provider")
        service = cleaned_data.get("service")
        if provider and service and service.provider_id != provider.id:
            raise forms.ValidationError("Le service sélectionné n'appartient pas à cette prestataire.")
        return cleaned_data


class ProviderAdminForm(forms.ModelForm):
    zones = forms.ModelMultipleChoiceField(
        queryset=Zone.objects.all(),
        required=False,
        widget=FilteredSelectMultiple("zones", is_stacked=False),
    )
    marketing_services = forms.ModelMultipleChoiceField(
        queryset=MarketingService.objects.all(),
        required=False,
        widget=FilteredSelectMultiple("services", is_stacked=False),
    )
    marketing_sub_services = MarketingSubServiceMultipleChoiceField(
        queryset=MarketingSubService.objects.select_related("service").all(),
        required=False,
        widget=FilteredSelectMultiple("sous-services", is_stacked=False),
        help_text=(
            "Sélectionne ici les sous-services associés à cette prestataire. "
            "Le service marketing parent est automatiquement associé si nécessaire."
        ),
    )

    class Meta:
        model = Provider
        fields = (
            "name",
            "description",
            "seo_h1",
            "availabilities",
            "additional_info",
            "contact_phone",
            "contact_email",
            "deposit_cents",
            "deposit_percentage",
            "service_fee_percentage",
            "salon_zone",
            "salon_address",
            "profile_image",
            "provides_meche",
            "location_mode",
            "categorized_services_enabled",
            "homepage_order",
            "is_visible_on_website",
            "user",
            "zones",
            "marketing_services",
            "marketing_sub_services",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["zones"].initial = self.instance.zones.all()
            self.fields["marketing_services"].initial = self.instance.marketing_services.all()
            self.fields["marketing_sub_services"].initial = (
                self.instance.marketing_sub_services.select_related("service").all()
            )

    def save(self, commit=True):
        provider = super().save(commit=commit)
        if not provider.pk:
            return provider

        selected_zones = self.cleaned_data.get("zones")
        selected_services = self.cleaned_data.get("marketing_services")
        selected_sub_services = self.cleaned_data.get("marketing_sub_services")

        if selected_zones is not None:
            ProviderZone.objects.filter(provider=provider).exclude(zone__in=selected_zones).delete()
            for zone in selected_zones:
                ProviderZone.objects.get_or_create(provider=provider, zone=zone)

        if selected_services is not None:
            ProviderMarketingService.objects.filter(provider=provider).exclude(
                service__in=selected_services
            ).delete()
            for service in selected_services:
                ProviderMarketingService.objects.get_or_create(provider=provider, service=service)

        if selected_sub_services is not None:
            provider.marketing_sub_services.set(selected_sub_services)
            parent_services = {sub_service.service for sub_service in selected_sub_services}
            for service in parent_services:
                ProviderMarketingService.objects.get_or_create(provider=provider, service=service)

        if provider.categorized_services_enabled:
            unassigned_services = provider.services.filter(category__isnull=True)
            if unassigned_services.exists():
                fallback_category, _ = ServiceCategory.objects.get_or_create(
                    provider=provider,
                    name="Autres services",
                    defaults={"order": 999},
                )
                unassigned_services.update(category=fallback_category)

        return provider


@admin.register(Provider)
class ProviderAdmin(ImportExportModelAdmin):
    form = ProviderAdminForm
    list_display = (
        "name",
        "contact_phone",
        "contact_email",
        "deposit_cents",
        "deposit_percentage",
        "service_fee_percentage",
        "salon_zone",
        "provides_meche",
        "location_mode",
        "categorized_services_enabled",
        "homepage_order",
        "is_visible_on_website",
        "user",
    )
    list_filter = ("location_mode", "is_visible_on_website")
    inlines = []
    resource_class = ProviderResource
    actions = ("generate_lead_prefill_links", "recompress_profile_images")

    @admin.action(description="Générer un lien de brouillon prérempli (lead)")
    def generate_lead_prefill_links(self, request, queryset):
        generated_count = 0
        for provider in queryset:
            draft = ProviderBookingDraft.objects.create(
                provider=provider,
                source=ProviderBookingDraft.SOURCE_ADMIN,
                created_by=request.user if getattr(request.user, "is_authenticated", False) else None,
                client_name="",
                client_email="",
                payload={
                    "service_id": "",
                    "service_name": "",
                    "client_name": "",
                    "client_email": "",
                    "desired_date": "",
                    "location_preference": "",
                    "location": "",
                    "client_address": "",
                    "hair_length": "",
                    "general_adjustments": [],
                    "meche": False,
                    "free_text": "",
                    "current_hair_picture": "",
                    "inspiration_pictures": [],
                },
            )
            provider_link = (
                reverse("interface:provider_detail", args=[provider.id])
                + f"?recap={draft.token}#booking-wizard"
            )
            self.message_user(
                request,
                format_html(
                    (
                        "{} · lien lead prérempli : <a href='{}' target='_blank' rel='noopener'>{}</a>"
                        " · ouvre ce lien, complète les champs à préremplir, puis clique sur"
                        " « Voir mon récapitulatif » pour enregistrer le brouillon."
                    ),
                    provider.name,
                    provider_link,
                    provider_link,
                ),
                level=messages.SUCCESS,
            )
            generated_count += 1

        if generated_count == 0:
            self.message_user(request, "Aucun prestataire sélectionné.", level=messages.WARNING)

    @admin.action(description="Optimiser les photos de profil sélectionnées")
    def recompress_profile_images(self, request, queryset):
        processed = 0
        for provider in queryset:
            if not provider.profile_image:
                continue
            compress_image_field(provider.profile_image, max_px=320, quality=76)
            provider.save(update_fields=["profile_image"])
            processed += 1
        self.message_user(
            request,
            f"{processed} photo(s) de profil optimisée(s).",
            level=messages.SUCCESS if processed else messages.WARNING,
        )


class ProviderPhotoInline(admin.TabularInline):
    model = ProviderPhoto
    extra = 1
    fields = ("media_kind", "image", "image_url", "video", "video_url", "caption", "order")
    ordering = ("order",)


ProviderAdmin.inlines.append(ProviderPhotoInline)


class ProviderBeforeAppointmentItemInline(admin.TabularInline):
    model = ProviderBeforeAppointmentItem
    extra = 1
    fields = ("label", "order")
    ordering = ("order", "id")


ProviderAdmin.inlines.append(ProviderBeforeAppointmentItemInline)


@admin.register(ProviderServiceFeeCoupon)
class ProviderServiceFeeCouponAdmin(admin.ModelAdmin):
    list_display = ("provider", "code", "is_active", "created_at")
    list_filter = ("provider", "is_active")
    search_fields = ("code", "provider__name")


@admin.register(ProviderPhoto)
class ProviderPhotoAdmin(ImportExportModelAdmin):
    list_display = ("provider", "media_kind", "caption", "order")
    list_filter = ("provider",)
    search_fields = ("caption",)
    resource_class = ProviderPhotoResource
    actions = ("recompress_gallery_images",)

    @admin.action(description="Optimiser les photos galerie sélectionnées")
    def recompress_gallery_images(self, request, queryset):
        processed = 0
        for photo in queryset:
            if not photo.image:
                continue
            compress_image_field(photo.image, max_px=720, quality=80)
            photo.save(update_fields=["image"])
            processed += 1
        self.message_user(
            request,
            f"{processed} image(s) galerie optimisée(s).",
            level=messages.SUCCESS if processed else messages.WARNING,
        )


class ServiceAdminForm(forms.ModelForm):
    hair_length_adjustments = forms.JSONField(
        required=False,
        help_text="JSON longueur -> supplément en centimes (ex: {\"court\":0, \"mi-long\":1000, \"long\":2000}).",
    )
    general_adjustments = forms.JSONField(
        required=False,
        help_text="JSON motif -> supplément en centimes (ajouté au total, ex: {\"motif\":500}).",
    )
    meche_bonus_cents = forms.IntegerField(
        required=False,
        help_text="Supplément en centimes lorsque l'option mèches fournies est cochée.",
    )
    at_home_bonus_cents = forms.IntegerField(
        required=False,
        help_text='Supplément en centimes appliqué quand la cliente choisit "à domicile".',
    )

    class Meta:
        model = Service
        fields = (
            "provider",
            "category",
            "name",
            "slug",
            "image",
            "image_url",
            "base_price_cents",
            "hair_length_adjustments",
            "general_adjustments",
            "meche_bonus_cents",
            "at_home_bonus_cents",
            "marketing_service",
            "marketing_sub_services",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        provider = None
        if self.instance and self.instance.pk:
            provider = self.instance.provider
        elif self.data.get("provider"):
            provider = Provider.objects.filter(pk=self.data.get("provider")).first()

        if provider:
            self.fields["category"].queryset = ServiceCategory.objects.filter(provider=provider)
            if provider.categorized_services_enabled:
                self.fields["category"].required = True
                self.fields["category"].help_text = (
                    "Obligatoire lorsque les services sont catégorisés pour cette prestataire."
                )

    def clean(self):
        cleaned_data = super().clean()
        provider = cleaned_data.get("provider")
        category = cleaned_data.get("category")
        if provider and provider.categorized_services_enabled and not category:
            raise forms.ValidationError(
                "Merci d'assigner une catégorie lorsque les services sont catégorisés."
            )
        return cleaned_data


@admin.register(Service)
class ServiceAdmin(ImportExportModelAdmin):
    list_display = ("name", "slug", "provider", "category", "marketing_service", "base_price_cents", "image_preview")
    list_filter = ("provider", "category", "marketing_service")
    search_fields = ("name", "slug")
    resource_class = ServiceResource
    form = ServiceAdminForm
    actions = ("recompress_service_images",)

    @admin.display(description="Image")
    def image_preview(self, obj):
        image_url = obj.resolved_image
        if not image_url:
            return "—"
        return format_html(
            '<img src="{}" alt="{}" style="max-width:64px;max-height:64px;border-radius:8px;border:1px solid #ddd;" />',
            image_url,
            obj.name,
        )

    @admin.action(description="Optimiser les images service sélectionnées")
    def recompress_service_images(self, request, queryset):
        processed = 0
        for service in queryset:
            if not service.image:
                continue
            compress_image_field(service.image, max_px=720, quality=80)
            service.save(update_fields=["image"])
            processed += 1
        self.message_user(
            request,
            f"{processed} image(s) service optimisée(s).",
            level=messages.SUCCESS if processed else messages.WARNING,
        )


class ServiceCategoryAdminForm(forms.ModelForm):
    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.none(),
        required=False,
        widget=FilteredSelectMultiple("services", is_stacked=False),
        help_text="Sélectionne les services à ranger dans cette catégorie.",
    )

    class Meta:
        model = ServiceCategory
        fields = ("provider", "name", "order", "services")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        provider = None
        if self.instance and self.instance.pk:
            provider = self.instance.provider
        elif self.data.get("provider"):
            provider = Provider.objects.filter(pk=self.data.get("provider")).first()

        queryset = Service.objects.all()
        if provider:
            queryset = queryset.filter(provider=provider)
        self.fields["services"].queryset = queryset

        if self.instance and self.instance.pk:
            self.fields["services"].initial = self.instance.services.all()

    def save(self, commit=True):
        category = super().save(commit=commit)
        if not category.pk:
            return category

        selected_services = self.cleaned_data.get("services")
        if selected_services is not None:
            Service.objects.filter(category=category).exclude(
                id__in=selected_services
            ).update(category=None)
            Service.objects.filter(id__in=selected_services).update(category=category)
        return category


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(ImportExportModelAdmin):
    form = ServiceCategoryAdminForm
    list_display = ("name", "provider", "order")
    list_filter = ("provider",)
    search_fields = ("name",)


@admin.register(Zone)
class ZoneAdmin(ImportExportModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    resource_class = ZoneResource


@admin.register(ProviderZone)
class ProviderZoneAdmin(ImportExportModelAdmin):
    list_display = ("provider", "zone")
    list_filter = ("provider", "zone")
    resource_class = ProviderZoneResource


@admin.register(ProviderMarketingService)
class ProviderMarketingServiceAdmin(ImportExportModelAdmin):
    list_display = ("provider", "service")
    list_filter = ("provider", "service")
    resource_class = ProviderMarketingServiceResource


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("booking_id", "booking_kind", "provider", "service", "status", "payment_status", "created_at", "inspiration_pictures_count")
    list_filter = ("booking_kind", "status", "payment_status", "provider")
    search_fields = ("booking_id", "client_name", "client_email", "payment_auth_id")
    readonly_fields = ("current_hair_picture_preview", "inspiration_pictures_preview")
    fieldsets = (
        (None, {"fields": (
            "booking_id", "booking_kind", "provider", "service",
            "requested_marketing_service", "requested_marketing_sub_service",
            "requested_service_label_snapshot", "requested_options", "status",
            "client_name", "client_email", "client_phone", "location",
            "location_preference", "client_address", "desired_date", "hair_length",
            "general_adjustments", "meche", "free_text", "estimated_price_cents",
            "provider_price_estimate_cents", "chateau_rose_fee_cents",
            "amount_due_now_cents", "payment_status", "proposed_price_cents",
            "proposed_date", "payment_auth_id", "locked_reservation_fee_cents",
            "created_at", "updated_at", "client_reminder_sent_at",
        )}),
        ("Legacy photos", {
            "classes": ("collapse",),
            "fields": (
                "current_hair_picture", "current_hair_picture_preview",
                "inspiration_pictures", "inspiration_pictures_preview",
            ),
        }),
    )


    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/assign-provider/",
                self.admin_site.admin_view(self.assign_provider_view),
                name="booking_booking_assign_provider",
            ),
        ]
        return custom_urls + urls

    def assign_provider_view(self, request, object_id):
        booking = self.get_object(request, object_id)
        if booking is None:
            messages.error(request, "Demande introuvable.")
            return redirect("..")

        if booking.status not in {Booking.STATUS_AWAITING_ALTERNATIVE_PROVIDER, Booking.STATUS_WAITING_PROVIDER_ASSIGNMENT}:
            messages.error(request, "Cette demande n'est pas en attente d'assignation prestataire.")
            return redirect(reverse("admin:booking_booking_change", args=[object_id]))

        if getattr(request, "method", "POST") != "POST":
            return render(
                request,
                "admin/booking/booking/assign_provider.html",
                {
                    **self.admin_site.each_context(request),
                    "title": "Assigner une prestataire",
                    "booking": booking,
                    "form": BookingProviderAssignmentForm(),
                    "opts": self.model._meta,
                },
            )

        post_data = request.POST.copy()
        if "service_id" in post_data and "service" not in post_data:
            legacy_service = Service.objects.select_related("provider").filter(id=post_data.get("service_id")).first()
            if legacy_service:
                post_data["service"] = str(legacy_service.id)
                post_data["provider"] = str(legacy_service.provider_id)
        form = BookingProviderAssignmentForm(post_data or None)
        if not form.is_valid():
            for error in form.non_field_errors():
                messages.error(request, error)
            for field, errors in form.errors.items():
                if field != "__all__":
                    messages.error(request, f"{form.fields[field].label} : {', '.join(errors)}")
            return redirect(reverse("admin:booking_booking_change", args=[object_id]))

        provider = form.cleaned_data["provider"]
        service = form.cleaned_data["service"]

        try:
            assign_provider_to_booking.execute(
                booking_id=booking.booking_id,
                provider_id=str(provider.id),
                service_id=str(service.id),
                booking_repository=DjangoBookingRepository(),
                provider_catalog=DjangoProviderCatalog(),
                notifier=EmailNotifier(),
                clock=type("Clock", (), {"now": timezone.now}),
                operations_email=getattr(settings, "OPERATIONS_EMAIL", "") or getattr(settings, "DEFAULT_FROM_EMAIL", ""),
                enforce_service_intent_match=not form.cleaned_data["compatibility_override"],
            )
        except DomainError as exc:
            messages.error(request, f"Assignation impossible : {exc}")
        else:
            messages.success(request, f"Demande assignée à {service.provider.name} · {service.name}.")
        return redirect(reverse("admin:booking_booking_change", args=[object_id]))

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        extra_context["assignment_form"] = BookingProviderAssignmentForm()
        extra_context["can_assign_provider"] = bool(
            obj and obj.status in {Booking.STATUS_AWAITING_ALTERNATIVE_PROVIDER, Booking.STATUS_WAITING_PROVIDER_ASSIGNMENT}
        )
        return super().change_view(request, object_id, form_url, extra_context)

    @admin.display(description="Photos")
    def inspiration_pictures_count(self, obj):
        return len(obj.inspiration_pictures or [])

    @admin.display(description="Aperçu photo cheveux")
    def current_hair_picture_preview(self, obj):
        url = self._resolve_media_url(obj.current_hair_picture)
        if not url:
            return "-"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Ouvrir l\'image</a><br>'
            '<img src="{}" alt="Photo cheveux" style="margin-top:4px;max-width:240px;max-height:240px;border-radius:8px;border:1px solid #ddd;" />',
            url,
            url,
        )

    @admin.display(description="Aperçu photos d'inspiration")
    def inspiration_pictures_preview(self, obj):
        urls = obj.inspiration_pictures or []
        if not urls:
            return "-"

        resolved_urls = [self._resolve_media_url(url) for url in urls if url]
        resolved_urls = [url for url in resolved_urls if url]
        if not resolved_urls:
            return "-"

        return format_html(
            '<div style="display:grid;gap:8px;">{}</div>',
            format_html_join(
                "",
                '<div><a href="{}" target="_blank" rel="noopener">Ouvrir l\'image {}</a><br><img src="{}" alt="Inspiration {}" style="margin-top:4px;max-width:240px;max-height:240px;border-radius:8px;border:1px solid #ddd;" /></div>',
                ((url, idx + 1, url, idx + 1) for idx, url in enumerate(resolved_urls)),
            ),
        )

    def _resolve_media_url(self, url: str) -> str:
        return resolve_stored_media_url(url) or ""


@admin.register(ProviderBlockedSlot)
class ProviderBlockedSlotAdmin(admin.ModelAdmin):
    class ProviderBlockedSlotAdminForm(forms.ModelForm):
        BLOCK_TYPE_ONE_TIME = "one_time"
        BLOCK_TYPE_RECURRING = "recurring"
        BLOCK_TYPE_CHOICES = (
            (BLOCK_TYPE_ONE_TIME, "Ponctuel (date + heure de début/fin)"),
            (BLOCK_TYPE_RECURRING, "Récurrent hebdomadaire (jours + plage horaire)"),
        )

        block_type = forms.ChoiceField(
            label="Type de blocage",
            choices=BLOCK_TYPE_CHOICES,
            widget=forms.RadioSelect,
            help_text=(
                "Choisis 'Ponctuel' pour bloquer un créneau unique, ou 'Récurrent' "
                "pour bloquer des jours chaque semaine."
            ),
        )

        class Meta:
            model = ProviderBlockedSlot
            fields = "__all__"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            is_recurring = bool(self.instance and self.instance.pk and self.instance.is_recurring)

            if self.data:
                is_recurring = self.data.get("block_type") == self.BLOCK_TYPE_RECURRING

            self.fields["block_type"].initial = (
                self.BLOCK_TYPE_RECURRING if is_recurring else self.BLOCK_TYPE_ONE_TIME
            )
            self.fields["starts_at"].help_text = "Obligatoire uniquement pour un blocage ponctuel."
            self.fields["ends_at"].help_text = "Obligatoire uniquement pour un blocage ponctuel."
            self.fields["weekdays"].help_text = (
                "Obligatoire uniquement en récurrent. Valeurs: 0=lundi, ..., 6=dimanche. "
                "Exemple: 0,2,4"
            )
            self.fields["starts_time"].help_text = "Obligatoire uniquement en récurrent."
            self.fields["ends_time"].help_text = "Obligatoire uniquement en récurrent."
            self.fields["recurrence_starts_on"].help_text = "Optionnel: date de début de la récurrence."
            self.fields["recurrence_ends_on"].help_text = "Optionnel: date de fin de la récurrence."

        def clean(self):
            cleaned_data = super().clean()
            block_type = cleaned_data.get("block_type", self.BLOCK_TYPE_ONE_TIME)
            is_recurring = block_type == self.BLOCK_TYPE_RECURRING
            cleaned_data["is_recurring"] = is_recurring
            self.instance.is_recurring = is_recurring

            if is_recurring:
                cleaned_data["starts_at"] = None
                cleaned_data["ends_at"] = None
            else:
                cleaned_data["weekdays"] = ""
                cleaned_data["starts_time"] = None
                cleaned_data["ends_time"] = None
                cleaned_data["recurrence_starts_on"] = None
                cleaned_data["recurrence_ends_on"] = None

            return cleaned_data

    form = ProviderBlockedSlotAdminForm
    list_display = ("provider", "is_recurring", "starts_at", "ends_at", "starts_time", "ends_time", "source", "is_active")
    list_filter = ("provider", "is_recurring", "source", "is_active")
    search_fields = ("provider__name", "reason")
    fields = (
        "provider",
        "block_type",
        "is_recurring",
        "starts_at",
        "ends_at",
        "weekdays",
        "starts_time",
        "ends_time",
        "recurrence_starts_on",
        "recurrence_ends_on",
        "source",
        "reason",
        "is_active",
    )
    readonly_fields = ("is_recurring",)
