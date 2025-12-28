from django.contrib import admin

from interface.models import MarketingService, MarketingServiceImage, ServiceRequest


class MarketingServiceImageInline(admin.TabularInline):
    model = MarketingServiceImage
    extra = 1


@admin.register(MarketingService)
class MarketingServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MarketingServiceImageInline]


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ("marketing_service", "zone", "client_name", "client_phone", "created_at")
    list_filter = ("marketing_service", "zone")
    search_fields = ("client_name", "client_phone", "details")
