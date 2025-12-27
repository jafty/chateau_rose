from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


def validate_absolute_or_root_relative_url(value: str | None) -> None:
    """Allow http/https URLs or root-relative paths starting with '/'."""

    if not value:
        return

    if value.startswith("/"):
        return

    validator = URLValidator(schemes=["http", "https"])
    try:
        validator(value)
    except ValidationError as exc:
        raise ValidationError("Enter a valid URL or path starting with '/'.") from exc
