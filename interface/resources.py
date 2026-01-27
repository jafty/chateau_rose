from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget, JSONWidget

from booking.models import Zone

from .models import MarketingService, MarketingServiceImage, MarketingServiceZone, MarketingZone


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
            "intro",
            "highlights",
            "main_image_url",
            "meta_description",
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
            "highlights",
            "hero_image_url",
            "meta_description",
        )
        export_order = fields
