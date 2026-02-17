import json
import tempfile

from django.core.management import call_command
from django.test import TestCase

from interface.models import MarketingService


class ImportMarketingContentCommandTest(TestCase):
    def test_command_imports_services(self):
        payload = {
            "services": [
                {
                    "slug": "tresses",
                    "name": "Tresses",
                    "intro": "Base intro",
                    "short_intro": "Intro courte",
                    "long_description": "Description longue",
                    "long_title": "Titre long",
                    "main_image_url": "https://static.example.com/service.jpg",
                    "gallery": ["https://static.example.com/s1.jpg"],
                    "highlights": ["Rapide"],
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w+", suffix=".json") as tmp:
            json.dump(payload, tmp)
            tmp.flush()

            call_command("import_marketing_content", file=tmp.name)

        service = MarketingService.objects.get(slug="tresses")
        self.assertEqual(service.intro, "Base intro")
        self.assertEqual(service.short_intro, "Intro courte")
        self.assertEqual(service.long_description, "Description longue")
        self.assertEqual(service.long_title, "Titre long")
        self.assertEqual(service.main_image_url, "https://static.example.com/service.jpg")
        self.assertEqual(
            list(service.images.values_list("image_url", flat=True)),
            ["https://static.example.com/s1.jpg"],
        )
