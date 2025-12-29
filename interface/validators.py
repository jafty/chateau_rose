import re

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


RELATIVE_STATIC_PATTERN = re.compile(r"[\w\-./]+$")


def validate_absolute_or_root_relative_url(value: str | None) -> None:
    """Allow http/https URLs, root-relative paths, or relative static paths."""

    if not value:
        return

    if value.startswith("/"):
        return

    # Allow relative paths such as "static/marketing/foo.jpg" so we can
    # reference committed assets without uploading media files.
    if "://" not in value and not value.startswith("//"):
        if RELATIVE_STATIC_PATTERN.fullmatch(value):
            return
        raise ValidationError("Enter a valid URL or relative path.")

    validator = URLValidator(schemes=["http", "https"])
    try:
        validator(value)
    except ValidationError as exc:
        raise ValidationError("Enter a valid URL or path starting with '/'.") from exc
