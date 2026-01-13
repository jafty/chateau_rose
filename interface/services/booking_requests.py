import os

from django.core.files.storage import default_storage


def format_price(cents: int) -> str:
    euros = cents / 100
    if cents % 100 == 0:
        return f"{euros:.0f} €"
    return f"{euros:.2f} €"


def build_pricing_data(services):
    pricing_data = {}
    starting_prices = []
    for service in services:
        service.price_display = format_price(service.base_price_cents)
        adjustments = service.hair_length_adjustments or {}
        min_adj = min(adjustments.values()) if adjustments else 0
        starting_price = service.base_price_cents + min_adj
        starting_prices.append(starting_price)
        pricing_data[str(service.id)] = {
            "base": service.base_price_cents,
            "lengths": adjustments,
            "meche_bonus": service.meche_bonus_cents,
            "starting_from": starting_price,
        }
    return pricing_data, starting_prices


def save_upload(file_obj, prefix: str):
    if not file_obj:
        return None
    filename = file_obj.name
    return default_storage.save(os.path.join(prefix, filename), file_obj)


def save_current_hair_picture(file_obj):
    return save_upload(file_obj, "bookings/current/")


def save_inspiration_pictures(files):
    inspiration_paths = []
    for upload in files:
        saved = save_upload(upload, "bookings/inspiration/")
        if saved:
            inspiration_paths.append(saved)
    return inspiration_paths
