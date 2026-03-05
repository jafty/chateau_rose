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
    ProviderBlockedSlot,
    ProviderPhoto,
    ProviderZone,
    Service,
    ServiceCategory,
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
            "availabilities",
            "additional_info",
            "contact_phone",
            "contact_email",
            "deposit_cents",
            "deposit_percentage",
            "salon_zone",
            "salon_address",
            "profile_image",
            "provides_meche",
            "location_mode",
            "categorized_services_enabled",
            "homepage_order",
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
        "salon_zone",
        "provides_meche",
        "location_mode",
        "categorized_services_enabled",
        "homepage_order",
        "user",
    )
    list_filter = ("location_mode",)
    inlines = []
    resource_class = ProviderResource


class ProviderPhotoInline(admin.TabularInline):
    model = ProviderPhoto
    extra = 1
    fields = ("media_kind", "image", "image_url", "video", "video_url", "caption", "order")
    ordering = ("order",)


ProviderAdmin.inlines.append(ProviderPhotoInline)


@admin.register(ProviderPhoto)
class ProviderPhotoAdmin(ImportExportModelAdmin):
    list_display = ("provider", "media_kind", "caption", "order")
    list_filter = ("provider",)
    search_fields = ("caption",)
    resource_class = ProviderPhotoResource


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
            "base_price_cents",
            "hair_length_adjustments",
            "general_adjustments",
            "meche_bonus_cents",
            "at_home_bonus_cents",
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
    list_display = ("name", "slug", "provider", "category", "base_price_cents")
    list_filter = ("provider", "category")
    search_fields = ("name", "slug")
    resource_class = ServiceResource
    form = ServiceAdminForm


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
    list_display = ("booking_id", "provider", "service", "status", "created_at")
    list_filter = ("status", "provider")


@admin.register(ProviderBlockedSlot)
class ProviderBlockedSlotAdmin(admin.ModelAdmin):
    list_display = ("provider", "starts_at", "ends_at", "source", "is_active")
    list_filter = ("provider", "source", "is_active")
    search_fields = ("provider__name", "reason")
    fields = ("provider", "starts_at", "ends_at", "source", "reason", "is_active")

