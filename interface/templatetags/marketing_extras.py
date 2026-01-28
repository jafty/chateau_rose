import re

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
TAG_RE = re.compile(r"<[a-zA-Z][^>]*>")


@register.filter
def sanitize_marketing_html(value: str) -> str:
    if not value:
        return ""

    raw_value = str(value)
    normalized = raw_value.replace("\r\n", "\n").replace("\r", "\n")
    if not TAG_RE.search(raw_value):
        cleaned = bleach.clean(normalized, tags=[], attributes={}, strip=True)
        return mark_safe(cleaned.replace("\n", "<br>"))

    cleaned = bleach.clean(
        normalized,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )
    return mark_safe(cleaned.replace("\n", "<br>"))
