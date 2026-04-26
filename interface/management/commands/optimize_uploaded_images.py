from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db import DatabaseError

from booking.models import Provider, ProviderPhoto, Service
from interface.models import (
    MarketingService,
    MarketingServiceImage,
    MarketingServiceZone,
    MarketingSubService,
    MarketingZone,
)
from interface.services.image_processing import compress_image_field


@dataclass(frozen=True)
class CompressionTarget:
    model: type
    field_name: str
    max_px: int
    quality: int = 80


TARGETS = (
    CompressionTarget(MarketingService, "main_image", 900),
    CompressionTarget(MarketingSubService, "image", 900),
    CompressionTarget(MarketingServiceImage, "image", 800),
    CompressionTarget(MarketingZone, "hero_image", 1200),
    CompressionTarget(MarketingServiceZone, "hero_image", 1200),
    CompressionTarget(Provider, "profile_image", 720),
    CompressionTarget(Service, "image", 720),
    CompressionTarget(ProviderPhoto, "image", 720),
)


class Command(BaseCommand):
    help = (
        "Recompress existing uploaded images (ImageField files) with the same "
        "rules used on save, so you can optimize media without manual re-upload."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist optimized files. Without this flag, the command runs in dry-run mode.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        inspected = 0
        processed = 0

        for target in TARGETS:
            queryset = target.model.objects.exclude(**{target.field_name: ""}).exclude(
                **{f"{target.field_name}__isnull": True}
            )
            try:
                iterator = queryset.iterator()
                for instance in iterator:
                    image_field = getattr(instance, target.field_name, None)
                    if not image_field:
                        continue
                    inspected += 1
                    if apply_changes:
                        compress_image_field(image_field, max_px=target.max_px, quality=target.quality)
                        instance.save(update_fields=[target.field_name])
                        processed += 1
            except DatabaseError:
                self.stdout.write(
                    self.style.WARNING(
                        f"Table indisponible pour {target.model.__name__}, modèle ignoré."
                    )
                )

        mode = "APPLY" if apply_changes else "DRY-RUN"
        if apply_changes:
            message = f"[{mode}] Images inspectées: {inspected} · Images retraitées: {processed}"
        else:
            message = (
                f"[{mode}] Images inspectées: {inspected} · "
                "Aucune écriture effectuée (ajoutez --apply pour traiter les fichiers)."
            )
        self.stdout.write(self.style.SUCCESS(message))
