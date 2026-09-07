from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class ProviderGalleryTemplateTests(SimpleTestCase):
    def render_provider(self, photos):
        provider = SimpleNamespace(
            name="Awa",
            display_h1="Awa",
            description="",
            location_mode_label="À Toulouse",
            availabilities="",
        )
        return render_to_string(
            "interface/provider_detail.html",
            {
                "provider": provider,
                "gallery_photos": photos,
                "services": [],
                "service_categories": [],
                "visible_service_categories": [],
                "zones": [],
                "published_reviews": [],
                "before_appointment_items": [],
                "pricing_data": "{}",
            },
        )

    def test_video_is_rendered_and_registered_with_the_gallery_viewer(self):
        video = SimpleNamespace(
            resolved_url="https://cdn.example.com/result.mp4",
            caption="Résultat vidéo",
            is_video=True,
        )

        html = self.render_provider([video])

        self.assertIn('<video src="https://cdn.example.com/result.mp4"', html)
        self.assertIn('data-gallery-kind="video"', html)
        self.assertIn("hero-collage--count-1", html)

    def test_media_after_the_fourth_item_remains_available_to_the_modal(self):
        photos = [
            SimpleNamespace(
                resolved_url=f"https://cdn.example.com/result-{index}.jpg",
                caption=f"Résultat {index}",
                is_video=False,
            )
            for index in range(5)
        ]

        html = self.render_provider(photos)

        self.assertEqual(html.count("data-gallery-index="), 5)
        self.assertIn("gallery-source-only", html)
        self.assertIn("hero-collage--count-4", html)
