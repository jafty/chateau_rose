from urllib.parse import unquote, urlparse

from django.conf import settings
from django.core.files.storage import default_storage
from chateaurose.domain.services.pricing import (
    ceil_price_for_display_cents,
    compute_checkout_amounts_cents,
)


def format_price(cents: int) -> str:
    euros = cents / 100
    if cents % 100 == 0:
        return f"{euros:.0f} €"
    return f"{euros:.2f} €"


def format_marketing_price(cents: int) -> str:
    rounded_cents = ceil_price_for_display_cents(cents)
    return format_price(rounded_cents)


def build_pricing_data(services):
    pricing_data = {}
    starting_prices = []
    for service in services:
        service_fee_percentage = service.provider.service_fee_percentage or 15
        adjustments = service.hair_length_adjustments or {"standard": 0}
        general_adjustments = service.general_adjustments or {"standard": 0}
        min_adj = min(adjustments.values()) if adjustments else 0
        general_adj_total = 0
        starting_subtotal = service.base_price_cents + min_adj + general_adj_total
        starting_price = compute_checkout_amounts_cents(
            subtotal_cents=starting_subtotal,
            deposit_percentage=service.provider.deposit_percentage or 30,
            service_fee_percentage=service_fee_percentage,
        )["total_cents"]
        service.price_display = format_marketing_price(starting_price)
        starting_prices.append(starting_price)
        pricing_data[str(service.id)] = {
            "name": service.name,
            "base": service.base_price_cents,
            "lengths": adjustments,
            "general_adjustments": general_adjustments,
            "meche_bonus": service.meche_bonus_cents,
            "at_home_bonus": service.at_home_bonus_cents,
            "starting_from": starting_price,
            "deposit_percentage": service.provider.deposit_percentage,
            "service_fee_percentage": service_fee_percentage,
        }
    return pricing_data, starting_prices


def resolve_stored_media_url(path: str | None) -> str | None:
    if not path:
        return None

    cleaned = str(path).strip()
    if not cleaned:
        return None

    parsed = urlparse(cleaned)
    if cleaned.startswith("/"):
        return cleaned

    if parsed.scheme:
        media_url = urlparse(settings.MEDIA_URL or "")
        if media_url.scheme and media_url.netloc and parsed.netloc == media_url.netloc:
            media_prefix = media_url.path or "/"
            if parsed.path.startswith(media_prefix):
                storage_path = unquote(parsed.path[len(media_prefix) :].lstrip("/"))
                if storage_path:
                    return default_storage.url(storage_path)
        return cleaned

    return default_storage.url(cleaned)
