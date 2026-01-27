from django.contrib import admin

from import_export.admin import ImportExportModelAdmin

from interface.resources import (
    MarketingServiceImageResource,
    MarketingServiceResource,
    MarketingServiceZoneResource,
    MarketingZoneResource,
)

from interface.models import (
    MarketingService,
    MarketingServiceImage,
    MarketingServiceZone,
    MarketingZone,
    ServiceRequest,
)


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
        (None, {"fields": ("name", "slug", "intro", "highlights", "meta_description")}),
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
        (None, {"fields": ("service", "zone", "intro", "highlights", "meta_description")}),
        ("Image", {"fields": ("hero_image",)}),
    )
    resource_class = MarketingServiceZoneResource


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ("marketing_service", "zone", "client_name", "client_email", "created_at")
    list_filter = ("marketing_service", "zone")
    search_fields = ("client_name", "client_email", "details")


@admin.register(MarketingServiceImage)
class MarketingServiceImageAdmin(ImportExportModelAdmin):
    list_display = ("service", "caption", "order")
    list_filter = ("service",)
    search_fields = ("caption",)
    resource_class = MarketingServiceImageResource
