from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from booking.models import Zone
from interface.models import MarketingService


class StaticViewSitemap(Sitemap):
    priority = 0.6
    changefreq = "weekly"

    def items(self):
        return [
            "interface:home",
            "interface:about",
            "interface:provider_list",
            "interface:legal_notice",
            "interface:terms_of_sale",
            "interface:terms_of_use",
            "interface:privacy_policy",
        ]

    def location(self, item):
        return reverse(item)


class ServiceSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return MarketingService.objects.all()

    def location(self, item: MarketingService):
        return reverse("interface:service_page", args=[item.slug])


class ServiceCitySitemap(Sitemap):
    priority = 0.7
    changefreq = "weekly"

    def items(self):
        services = list(MarketingService.objects.all())
        zones = list(Zone.objects.all())
        return [(service, zone) for service in services for zone in zones]

    def location(self, item):
        service, zone = item
        return reverse("interface:service_city_page", args=[service.slug, zone.slug])


def sitemaps():
    return {
        "static": StaticViewSitemap,
        "services": ServiceSitemap,
        "service_cities": ServiceCitySitemap,
    }
