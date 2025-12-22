from django.contrib import admin

from .models import Booking, Provider, ProviderZone, Service, Zone


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_phone", "contact_email")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "provider", "base_price_cents")
    list_filter = ("provider",)


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(ProviderZone)
class ProviderZoneAdmin(admin.ModelAdmin):
    list_display = ("provider", "zone")
    list_filter = ("provider", "zone")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("booking_id", "provider", "service", "status", "created_at")
    list_filter = ("status", "provider")
