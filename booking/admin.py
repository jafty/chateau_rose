from django import forms
from django.contrib import admin

from .models import Booking, Provider, ProviderZone, Service, Zone
from interface import seo


def _city_and_district_choices():
    city_choices = [(c["slug"], c["name"]) for c in seo.CITIES]
    district_choices = []
    for city_slug, districts in seo.DISTRICTS_BY_CITY.items():
        district_choices.extend((d["slug"], f"{d['name']} ({city_slug})") for d in districts)
    return city_choices + district_choices


def _slug_to_name_map():
    mapping = {c["slug"]: c["name"] for c in seo.CITIES}
    for city_slug, districts in seo.DISTRICTS_BY_CITY.items():
        for d in districts:
            mapping[d["slug"]] = d["name"]
    return mapping


class ZoneAdminForm(forms.ModelForm):
    slug = forms.ChoiceField(choices=_city_and_district_choices())
    name = forms.CharField(disabled=True, required=False)

    class Meta:
        model = Zone
        fields = ("slug", "name")

    def clean(self):
        cleaned = super().clean()
        slug = cleaned.get("slug")
        if slug:
            cleaned["name"] = _slug_to_name_map().get(slug, cleaned.get("name"))
        return cleaned


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_phone", "contact_email")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "provider", "base_price_cents")
    list_filter = ("provider",)
    search_fields = ("name", "slug")


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    form = ZoneAdminForm


@admin.register(ProviderZone)
class ProviderZoneAdmin(admin.ModelAdmin):
    list_display = ("provider", "zone")
    list_filter = ("provider", "zone")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("booking_id", "provider", "service", "status", "created_at")
    list_filter = ("status", "provider")
