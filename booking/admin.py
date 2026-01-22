from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple

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
        widget=FilteredSelectMultiple("zones", is_stacked=False),
    )
    marketing_services = forms.ModelMultipleChoiceField(
        queryset=MarketingService.objects.all(),
        required=False,
        widget=FilteredSelectMultiple("services", is_stacked=False),
    )

    class Meta:
        model = Provider
        fields = (
            "name",
            "description",
            "contact_phone",
            "contact_email",
            "salon_zone",
            "salon_address",
            "profile_image",
            "location_mode",
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
class ProviderAdmin(ImportExportModelAdmin):
    form = ProviderAdminForm
    list_display = (
        "name",
        "contact_phone",
        "contact_email",
        "salon_zone",
        "location_mode",
        "user",
    )
    list_filter = ("location_mode",)
    inlines = []
    resource_class = ProviderResource


class ProviderPhotoInline(admin.TabularInline):
    model = ProviderPhoto
    extra = 1
    fields = ("image", "caption", "order")
    ordering = ("order",)


ProviderAdmin.inlines.append(ProviderPhotoInline)


@admin.register(ProviderPhoto)
class ProviderPhotoAdmin(ImportExportModelAdmin):
    list_display = ("provider", "caption", "order")
    list_filter = ("provider",)
    search_fields = ("caption",)
    resource_class = ProviderPhotoResource


@admin.register(Service)
class ServiceAdmin(ImportExportModelAdmin):
    list_display = ("name", "slug", "provider", "base_price_cents")
    list_filter = ("provider",)
    search_fields = ("name", "slug")
    resource_class = ServiceResource
    form = type(
        "ServiceAdminForm",
        (forms.ModelForm,),
        {
            "hair_length_adjustments": forms.JSONField(
                required=False,
                help_text="JSON longueur -> supplément en centimes (ex: {\"court\":0, \"mi-long\":1000, \"long\":2000}).",
            ),
            "meche_bonus_cents": forms.IntegerField(
                required=False,
                help_text="Supplément en centimes lorsque l'option mèches fournies est cochée.",
            ),
            "Meta": type(
                "Meta",
                (),
                {
                    "model": Service,
                    "fields": ("provider", "name", "slug", "base_price_cents", "hair_length_adjustments", "meche_bonus_cents"),
                },
            ),
        },
    )


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
    list_display = ("booking_id", "provider", "service", "status", "created_at")
    list_filter = ("status", "provider")
