from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

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
