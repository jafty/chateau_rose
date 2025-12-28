import json

from django.core.management.base import BaseCommand, CommandError

from chateaurose.domain.exceptions import ValidationError
from chateaurose.domain.use_cases import import_marketing_content
from chateaurose.infrastructure.marketing_repository import DjangoMarketingContentRepository


class Command(BaseCommand):
    help = "Bulk import marketing services from a JSON file"

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to the JSON payload file")
        parser.add_argument(
            "--format",
            default="json",
            help="Payload format (only 'json' is currently supported)",
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        fmt = options["format"]
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                raw_content = fh.read()
        except OSError as exc:
            raise CommandError(f"Impossible de lire le fichier: {exc}") from exc

        if fmt != "json":
            raise CommandError("Seul le format JSON est supporté")
        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise CommandError(f"JSON invalide: {exc}") from exc

        repository = DjangoMarketingContentRepository()
        try:
            result = import_marketing_content.execute(payload=payload, repository=repository)
        except ValidationError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Import terminé: "
                f"{result.services_count} services."
            )
        )
