from django.contrib.auth import get_user_model
from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget, JSONWidget

from interface.models import MarketingService

from .models import Provider, ProviderMarketingService, ProviderPhoto, ProviderZone, Service, Zone


class ZoneResource(resources.ModelResource):
    class Meta:
        model = Zone
        fields = ("id", "name", "slug")
        export_order = ("id", "name", "slug")


class ProviderResource(resources.ModelResource):
    user = fields.Field(
        column_name="user_username",
        attribute="user",
        widget=ForeignKeyWidget(get_user_model(), "username"),
    )

    class Meta:
        model = Provider
        fields = (
            "id",
            "name",
            "description",
            "contact_phone",
            "contact_email",
            "deposit_cents",
            "salon_zone",
            "salon_address",
            "profile_image_url",
            "location_mode",
            "user",
        )
        export_order = fields


class ServiceResource(resources.ModelResource):
    provider = fields.Field(
        column_name="provider_id",
        attribute="provider",
        widget=ForeignKeyWidget(Provider, "id"),
    )
    hair_length_adjustments = fields.Field(
        column_name="hair_length_adjustments",
        attribute="hair_length_adjustments",
        widget=JSONWidget(),
    )
    general_adjustments = fields.Field(
        column_name="general_adjustments",
        attribute="general_adjustments",
        widget=JSONWidget(),
    )

    class Meta:
        model = Service
        fields = (
            "id",
            "provider",
            "name",
            "slug",
            "base_price_cents",
            "hair_length_adjustments",
            "general_adjustments",
            "meche_bonus_cents",
        )
        export_order = fields


class ProviderPhotoResource(resources.ModelResource):
    provider = fields.Field(
        column_name="provider_id",
        attribute="provider",
        widget=ForeignKeyWidget(Provider, "id"),
    )

    class Meta:
        model = ProviderPhoto
        fields = (
            "id",
            "provider",
            "image_url",
            "caption",
            "order",
        )
        export_order = fields


class ProviderZoneResource(resources.ModelResource):
    provider = fields.Field(
        column_name="provider_id",
        attribute="provider",
        widget=ForeignKeyWidget(Provider, "id"),
    )
    zone = fields.Field(
        column_name="zone_slug",
        attribute="zone",
        widget=ForeignKeyWidget(Zone, "slug"),
    )

    class Meta:
        model = ProviderZone
        fields = (
            "id",
            "provider",
            "zone",
        )
        export_order = fields


class ProviderMarketingServiceResource(resources.ModelResource):
    provider = fields.Field(
        column_name="provider_id",
        attribute="provider",
        widget=ForeignKeyWidget(Provider, "id"),
    )
    service = fields.Field(
        column_name="service_slug",
        attribute="service",
        widget=ForeignKeyWidget(MarketingService, "slug"),
    )

    class Meta:
        model = ProviderMarketingService
        fields = (
            "id",
            "provider",
            "service",
        )
        export_order = fields
