from django import forms
from django.contrib import admin

from .models import (
    Booking,
    Provider,
    ProviderMarketingService,
    ProviderPhoto,
    ProviderZone,
    Service,
    Zone,
)
from interface.models import MarketingService


class ProviderAdminForm(forms.ModelForm):
    zones = forms.ModelMultipleChoiceField(
        queryset=Zone.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    marketing_services = forms.ModelMultipleChoiceField(
        queryset=MarketingService.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Provider
        fields = (
            "name",
            "description",
            "contact_phone",
            "contact_email",
            "profile_image",
            "works_in_salon_only",
            "user",
            "zones",
            "marketing_services",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["zones"].initial = self.instance.zones.all()
            self.fields["marketing_services"].initial = self.instance.marketing_services.all()

    def save(self, commit=True):
        provider = super().save(commit=commit)
        if not provider.pk:
            return provider

        selected_zones = self.cleaned_data.get("zones")
        selected_services = self.cleaned_data.get("marketing_services")

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

        return provider


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    form = ProviderAdminForm
    list_display = (
        "name",
        "contact_phone",
        "contact_email",
        "works_in_salon_only",
        "user",
    )
    inlines = []


class ProviderPhotoInline(admin.TabularInline):
    model = ProviderPhoto
    extra = 1
    fields = ("image", "caption", "order")
    ordering = ("order",)


ProviderAdmin.inlines.append(ProviderPhotoInline)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "provider", "base_price_cents")
    list_filter = ("provider",)
    search_fields = ("name", "slug")


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")


@admin.register(ProviderZone)
class ProviderZoneAdmin(admin.ModelAdmin):
    list_display = ("provider", "zone")
    list_filter = ("provider", "zone")


@admin.register(ProviderMarketingService)
class ProviderMarketingServiceAdmin(admin.ModelAdmin):
    list_display = ("provider", "service")
    list_filter = ("provider", "service")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("booking_id", "provider", "service", "status", "created_at")
    list_filter = ("status", "provider")
