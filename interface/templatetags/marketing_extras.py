import bleach
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ALLOWED_TAGS = [
    "b",
    "br",
    "em",
    "h4",
    "h5",
    "h6",
    "i",
    "li",
    "ol",
    "p",
    "strong",
    "ul",
]
ALLOWED_ATTRIBUTES = {}


@register.filter
def sanitize_marketing_html(value: str) -> str:
    if not value:
        return ""

    raw_value = str(value)
    if "<" not in raw_value and ">" not in raw_value:
        cleaned = bleach.clean(raw_value, tags=[], attributes={}, strip=True)
        return mark_safe(cleaned.replace("\n", "<br>"))

    cleaned = bleach.clean(
        raw_value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )
    return mark_safe(cleaned)
