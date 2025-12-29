from django.contrib import admin

from interface.models import (
    MarketingService,
    MarketingServiceImage,
    MarketingZone,
    ServiceRequest,
)


class MarketingServiceImageInline(admin.TabularInline):
    model = MarketingServiceImage
    extra = 1
    fields = (("image", "image_url"), "caption", "order")


@admin.register(MarketingService)
class MarketingServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (None, {"fields": ("name", "slug", "intro", "highlights", "meta_description")}),
        ("Image", {"fields": (("main_image", "main_image_url"),)}),
    )
    inlines = [MarketingServiceImageInline]


@admin.register(MarketingZone)
class MarketingZoneAdmin(admin.ModelAdmin):
    list_display = ("zone",)
    search_fields = ("zone__name", "zone__slug")
    autocomplete_fields = ("zone",)
    fieldsets = (
        (None, {"fields": ("zone", "intro", "highlights", "meta_description")}),
        ("Image", {"fields": (("hero_image", "hero_image_url"),)}),
    )


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ("marketing_service", "zone", "client_name", "client_phone", "created_at")
    list_filter = ("marketing_service", "zone")
    search_fields = ("client_name", "client_phone", "details")
