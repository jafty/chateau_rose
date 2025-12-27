import json
import tempfile

from django.core.management import call_command
from django.test import TestCase

from interface.models import (
    MarketingCity,
    MarketingDistrict,
    MarketingService,
    MarketingServiceCity,
)


class ImportMarketingContentCommandTest(TestCase):
    def test_command_imports_services_cities_and_overrides(self):
        payload = {
            "services": [
                {
                    "slug": "tresses",
                    "name": "Tresses",
                    "intro": "Base intro",
                    "main_image_url": "https://static.example.com/service.jpg",
                    "gallery": ["s1.jpg"],
                    "highlights": ["Rapide"],
                    "cities": [
                        {
                            "slug": "toulouse",
                            "name": "Toulouse",
                            "main_image_url": "https://static.example.com/city.jpg",
                            "districts": [
                                {"slug": "compans", "name": "Compans"},
                            ],
                            "override": {
                                "intro": "Override",
                                "main_image_url": "https://static.example.com/override.jpg",
                                "gallery": ["o1.jpg"],
                            },
                        }
                    ],
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w+", suffix=".json") as tmp:
            json.dump(payload, tmp)
            tmp.flush()

            call_command("import_marketing_content", file=tmp.name)

        service = MarketingService.objects.get(slug="tresses")
        self.assertEqual(service.intro, "Base intro")
        self.assertEqual(service.main_image_url, "https://static.example.com/service.jpg")
        self.assertEqual(list(service.images.values_list("image", flat=True)), ["s1.jpg"])

        city = MarketingCity.objects.get(slug="toulouse")
        self.assertEqual(city.name, "Toulouse")
        self.assertEqual(city.main_image_url, "https://static.example.com/city.jpg")
        self.assertTrue(MarketingDistrict.objects.filter(city=city, slug="compans").exists())

        override = MarketingServiceCity.objects.get(service=service, city=city)
        self.assertEqual(override.intro, "Override")
        self.assertEqual(override.main_image_url, "https://static.example.com/override.jpg")
        self.assertEqual(list(override.images.values_list("image", flat=True)), ["o1.jpg"])
