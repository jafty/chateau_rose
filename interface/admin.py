from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.html import format_html, format_html_join

from import_export.admin import ImportExportModelAdmin

from interface.resources import (
    MarketingServiceImageResource,
    MarketingServiceResource,
    MarketingServiceZoneResource,
    MarketingZoneResource,
)

from interface.models import (
    ClientReview,
    MarketingService,
    MarketingSubService,
    MarketingServiceImage,
    MarketingServiceZone,
    MarketingZone,
    ServiceRequest,
    Interaction,
    ProviderBookingDraft,
    QuickCheckoutPage,
)
from interface.services.booking_requests import resolve_stored_media_url


class MarketingServiceImageInline(admin.TabularInline):
    model = MarketingServiceImage
    extra = 1
    fields = ("image", "caption", "order")


@admin.register(MarketingService)
class MarketingServiceAdmin(ImportExportModelAdmin):
    list_display = ("name", "slug", "is_visible_on_homepage", "homepage_order")
    list_filter = ("is_visible_on_homepage",)
    list_editable = ("is_visible_on_homepage", "homepage_order")
    ordering = ("homepage_order", "name")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "slug",
                    "is_visible_on_homepage",
                    "homepage_order",
                    "long_title",
                    "short_intro",
                    "intro",
                    "long_description",
                    "highlights",
                    "meta_description",
                )
            },
        ),
        ("Image", {"fields": ("main_image",)}),
    )
    inlines = [MarketingServiceImageInline]
    resource_class = MarketingServiceResource


@admin.register(MarketingSubService)
class MarketingSubServiceAdmin(admin.ModelAdmin):
    class Form(forms.ModelForm):
        providers = forms.ModelMultipleChoiceField(
            queryset=None,
            required=False,
            widget=FilteredSelectMultiple("prestataires", is_stacked=False),
        )

        class Meta:
            model = MarketingSubService
            fields = "__all__"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            from booking.models import Provider

            self.fields["providers"].queryset = Provider.objects.order_by("name")

    form = Form
    list_display = ("name", "service", "is_visible", "order")
    list_filter = ("service", "is_visible")
    search_fields = ("name", "slug", "service__name")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("service",)


@admin.register(MarketingZone)
class MarketingZoneAdmin(ImportExportModelAdmin):
    list_display = ("zone",)
    search_fields = ("zone__name", "zone__slug")
    autocomplete_fields = ("zone",)
    fieldsets = (
        (None, {"fields": ("zone", "intro", "highlights", "meta_description")}),
        ("Image", {"fields": ("hero_image",)}),
    )
    resource_class = MarketingZoneResource


@admin.register(MarketingServiceZone)
class MarketingServiceZoneAdmin(ImportExportModelAdmin):
    list_display = ("service", "zone")
    search_fields = ("service__name", "service__slug", "zone__name", "zone__slug")
    autocomplete_fields = ("service", "zone")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "service",
                    "zone",
                    "long_title",
                    "short_intro",
                    "intro",
                    "long_description",
                    "highlights",
                    "meta_description",
                )
            },
        ),
        ("Image", {"fields": ("hero_image",)}),
    )
    resource_class = MarketingServiceZoneResource


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "marketing_service",
        "zone",
        "client_name",
        "client_phone",
        "client_email",
        "hair_length",
        "meche_provided",
        "created_at",
        "inspiration_pictures_count",
    )
    list_filter = ("marketing_service", "zone")
    search_fields = ("client_name", "client_phone", "client_email", "details", "inspiration_picture_urls")
    readonly_fields = ("inspiration_pictures_preview", "created_at")
    fields = (
        "marketing_service",
        "zone",
        "location_preference",
        "client_name",
        "client_phone",
        "client_email",
        "salon_area",
        "client_address",
        "desired_date",
        "availabilities",
        "hair_length",
        "meche_provided",
        "details",
        "inspiration_picture_urls",
        "inspiration_pictures_preview",
        "created_at",
    )

    @admin.display(description="Photos")
    def inspiration_pictures_count(self, obj):
        return len(obj.inspiration_picture_urls or [])

    @admin.display(description="Aperçu photos")
    def inspiration_pictures_preview(self, obj):
        urls = obj.inspiration_picture_urls or []
        if not urls:
            return "-"

        resolved_urls = [self._resolve_inspiration_url(url) for url in urls if url]
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

    def _resolve_inspiration_url(self, url: str) -> str:
        return resolve_stored_media_url(url) or ""


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = (
        "kind",
        "status",
        "source_label",
        "contact_name",
        "contact",
        "created_at",
        "updated_at",
    )
    list_filter = ("kind", "status", "created_at")
    search_fields = (
        "source_label",
        "contact_name",
        "contact_email",
        "contact_phone",
        "subject",
        "message",
        "next_action",
        "notes",
    )
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Contact")
    def contact(self, obj):
        return obj.contact_phone or obj.contact_email or "-"

@admin.register(ClientReview)
class ClientReviewAdmin(admin.ModelAdmin):
    list_display = ("client_name", "media_kind", "rating", "is_featured", "is_active", "created_at")
    list_filter = ("is_featured", "is_active", "rating")
    search_fields = ("client_name", "review_text")
    fields = ("client_name", "review_text", "media_kind", "photo", "photo_url", "video", "video_url", "rating", "is_featured", "is_active")


@admin.register(MarketingServiceImage)
class MarketingServiceImageAdmin(ImportExportModelAdmin):
    list_display = ("service", "caption", "order")
    list_filter = ("service",)
    search_fields = ("caption",)
    resource_class = MarketingServiceImageResource


@admin.register(ProviderBookingDraft)
class ProviderBookingDraftAdmin(admin.ModelAdmin):
    class Form(forms.ModelForm):
        class Meta:
            model = ProviderBookingDraft
            fields = ("provider", "source", "client_name", "client_email", "payload")
            widgets = {"payload": forms.Textarea(attrs={"rows": 8})}

    form = Form
    list_display = ("provider", "source", "client_email", "client_name", "updated_at", "completed_at")
    list_filter = ("provider", "source", "completed_at")
    search_fields = ("client_email", "client_name", "provider__name")
    readonly_fields = ("token", "created_by", "created_at", "updated_at")
    fields = (
        "provider",
        "source",
        "client_name",
        "client_email",
        "payload",
        "token",
        "created_by",
        "completed_at",
        "created_at",
        "updated_at",
    )

    @admin.display(description="Statut")
    def status(self, obj):
        return "Complété" if obj.completed_at else "En attente"

    def save_model(self, request, obj, form, change):
        if not change and obj.source == ProviderBookingDraft.SOURCE_ADMIN and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(QuickCheckoutPage)
class QuickCheckoutPageAdmin(admin.ModelAdmin):
    class Form(forms.ModelForm):
        provider_salon_zone = forms.CharField(
            required=False,
            label="Zone salon prestataire",
            help_text="Modifie aussi la zone salon de la fiche prestataire.",
        )

        class Meta:
            model = QuickCheckoutPage
            fields = "__all__"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            provider = getattr(self.instance, "provider", None)
            self.fields["provider_salon_zone"].initial = (getattr(provider, "salon_zone", "") or "").strip()

        def clean(self):
            cleaned_data = super().clean()
            location_preference = cleaned_data.get("location_preference")
            salon_zone = (cleaned_data.get("provider_salon_zone") or "").strip()
            provider = cleaned_data.get("provider") or getattr(self.instance, "provider", None)

            # Keep the in-memory provider aligned before model validation runs.
            # QuickCheckoutPage.clean() checks provider.salon_zone for salon bookings.
            if provider is not None:
                provider.salon_zone = salon_zone
                self.instance.provider = provider

            if location_preference == "salon" and not salon_zone:
                self.add_error(
                    "provider_salon_zone",
                    "La zone du salon est obligatoire quand le lieu du rendez-vous est « en salon ».",
                )
            return cleaned_data

        def save(self, commit=True):
            instance = super().save(commit=commit)
            provider = instance.provider
            salon_zone = (self.cleaned_data.get("provider_salon_zone") or "").strip()
            if provider and provider.pk:
                current_salon_zone = (
                    type(provider).objects.filter(pk=provider.pk)
                    .values_list("salon_zone", flat=True)
                    .first()
                    or ""
                ).strip()
                if current_salon_zone != salon_zone:
                    provider.salon_zone = salon_zone
                    provider.save(update_fields=["salon_zone"])
            return instance

    form = Form
    list_display = ("provider", "service", "client_email", "final_price_cents", "reservation_fee_cents", "is_active", "expires_at", "created_at")
    list_filter = ("is_active", "provider", "service")
    search_fields = ("client_email", "client_name", "provider__name", "service__name")
    readonly_fields = ("created_at", "updated_at", "completed_at")
    fields = (
        "provider",
        "service",
        "client_name",
        "client_email",
        "desired_date",
        "hair_length",
        "location_preference",
        "provider_salon_zone",
        "client_address",
        "free_text",
        "final_price_cents",
        "reservation_fee_cents",
        "is_active",
        "expires_at",
        "completed_at",
        "created_at",
        "updated_at",
    )
