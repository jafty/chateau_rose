from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

register = template.Library()


@register.filter
def cents_to_euros(cents_value):
    if cents_value in (None, ""):
        return ""

    try:
        cents = Decimal(cents_value)
    except InvalidOperation:
        return ""

    euros = (cents / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{euros:.2f}".replace(".", ",") + " €"


@register.filter
def cents_to_euros_input(cents_value):
    if cents_value in (None, ""):
        return ""
    try:
        cents = Decimal(cents_value)
    except InvalidOperation:
        return ""
    euros = (cents / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{euros:.2f}".replace(".", ",")


@register.filter
def format_french_datetime(value):
    if not value:
        return ""

    months = (
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    )

    parsed = parse_datetime(str(value))
    if parsed:
        if timezone.is_aware(parsed):
            parsed = timezone.localtime(parsed)
        month = months[parsed.month - 1]
        return f"{parsed.day} {month} {parsed.year} à {parsed:%H}h{parsed:%M}"

    parsed_date = parse_date(str(value))
    if parsed_date:
        month = months[parsed_date.month - 1]
        return f"{parsed_date.day} {month} {parsed_date.year}"

    return value


@register.filter
def booking_status_label(status):
    if not status:
        return ""

    normalized = str(status).upper()
    labels = {
        "SUBMITTED": "Soumise",
        "PENDING_CLIENT_VALIDATION": "En attente client",
        "AWAITING_ALTERNATIVE_PROVIDER": "Alternative en recherche",
        "CONFIRMED": "Confirmée",
        "CANCELLED": "Annulée",
    }
    return labels.get(normalized, status)
