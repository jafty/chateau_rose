from django.contrib import admin
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
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (None, {"fields": ("name", "slug", "long_title", "short_intro", "intro", "long_description", "highlights", "meta_description")}),
        ("Image", {"fields": ("main_image",)}),
    )
    inlines = [MarketingServiceImageInline]
    resource_class = MarketingServiceResource


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
        "contact_email",
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
    list_display = ("provider", "client_email", "client_name", "updated_at", "completed_at")
    list_filter = ("provider", "completed_at")
    search_fields = ("client_email", "client_name", "provider__name")
    readonly_fields = ("token", "provider", "client_email", "client_name", "payload", "created_at", "updated_at")

    @admin.display(description="Statut")
    def status(self, obj):
        return "Complété" if obj.completed_at else "En attente"


@admin.register(QuickCheckoutPage)
class QuickCheckoutPageAdmin(admin.ModelAdmin):
    list_display = ("provider", "service", "client_email", "final_price_cents", "reservation_fee_cents", "is_active", "expires_at", "created_at")
    list_filter = ("is_active", "provider", "service")
    search_fields = ("client_email", "client_name", "provider__name", "service__name")
    readonly_fields = ("provider_salon_zone", "created_at", "updated_at", "completed_at")

    @admin.display(description="Zone salon prestataire")
    def provider_salon_zone(self, obj):
        if not obj.provider_id:
            return "-"
        return obj.provider.salon_zone or "Non renseignée (à compléter sur la fiche prestataire)."
