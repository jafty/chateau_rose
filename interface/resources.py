from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget, JSONWidget, ManyToManyWidget

from booking.models import Provider, Zone

from .models import (
    MarketingService,
    MarketingServiceImage,
    MarketingServiceZone,
    MarketingSubService,
    MarketingZone,
)


class MarketingServiceResource(resources.ModelResource):
    highlights = fields.Field(
        column_name="highlights",
        attribute="highlights",
        widget=JSONWidget(),
    )

    class Meta:
        model = MarketingService
        fields = (
            "id",
            "name",
            "slug",
            "is_visible_on_homepage",
            "homepage_order",
            "intro",
            "short_intro",
            "long_description",
            "long_title",
            "highlights",
            "main_image_url",
            "meta_description",
        )
        export_order = fields


class MarketingSubServiceResource(resources.ModelResource):
    service = fields.Field(
        column_name="service_slug",
        attribute="service",
        widget=ForeignKeyWidget(MarketingService, "slug"),
    )
    providers = fields.Field(
        column_name="provider_ids",
        attribute="providers",
        widget=ManyToManyWidget(Provider, field="id", separator=","),
    )
    generic_hair_length_adjustments = fields.Field(
        column_name="generic_hair_length_adjustments",
        attribute="generic_hair_length_adjustments",
        widget=JSONWidget(),
    )
    generic_general_adjustments = fields.Field(
        column_name="generic_general_adjustments",
        attribute="generic_general_adjustments",
        widget=JSONWidget(),
    )

    class Meta:
        model = MarketingSubService
        fields = (
            "id",
            "service",
            "name",
            "slug",
            "intro",
            "short_intro",
            "image_url",
            "providers",
            "generic_booking_enabled",
            "generic_base_price_cents",
            "generic_hair_length_adjustments",
            "generic_general_adjustments",
            "generic_meche_bonus_cents",
            "generic_at_home_bonus_cents",
            "generic_service_fee_percentage",
            "generic_price_label",
            "is_visible",
            "order",
        )
        export_order = fields


class MarketingZoneResource(resources.ModelResource):
    zone = fields.Field(
        column_name="zone_slug",
        attribute="zone",
        widget=ForeignKeyWidget(Zone, "slug"),
    )
    highlights = fields.Field(
        column_name="highlights",
        attribute="highlights",
        widget=JSONWidget(),
    )

    class Meta:
        model = MarketingZone
        fields = (
            "id",
            "zone",
            "intro",
            "short_intro",
            "long_description",
            "long_title",
            "highlights",
            "hero_image_url",
            "meta_description",
        )
        export_order = fields


class MarketingServiceImageResource(resources.ModelResource):
    service = fields.Field(
        column_name="service_slug",
        attribute="service",
        widget=ForeignKeyWidget(MarketingService, "slug"),
    )

    class Meta:
        model = MarketingServiceImage
        fields = (
            "id",
            "service",
            "image_url",
            "caption",
            "order",
        )
        export_order = fields


class MarketingServiceZoneResource(resources.ModelResource):
    service = fields.Field(
        column_name="service_slug",
        attribute="service",
        widget=ForeignKeyWidget(MarketingService, "slug"),
    )
    zone = fields.Field(
        column_name="zone_slug",
        attribute="zone",
        widget=ForeignKeyWidget(Zone, "slug"),
    )
    highlights = fields.Field(
        column_name="highlights",
        attribute="highlights",
        widget=JSONWidget(),
    )

    class Meta:
        model = MarketingServiceZone
        fields = (
            "id",
            "service",
            "zone",
            "intro",
            "short_intro",
            "long_description",
            "long_title",
            "highlights",
            "hero_image_url",
            "meta_description",
        )
        export_order = fields
