import os
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps


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
        general_adjustments = service.general_adjustments or {}
        general_adj_total = sum(
            value for value in general_adjustments.values() if isinstance(value, (int, float))
        )
        min_adj = min(adjustments.values()) if adjustments else 0
        starting_price = service.base_price_cents + min_adj + general_adj_total
        starting_prices.append(starting_price)
        pricing_data[str(service.id)] = {
            "base": service.base_price_cents,
            "lengths": adjustments,
            "general_adjustments_total": general_adj_total,
            "meche_bonus": service.meche_bonus_cents,
            "starting_from": starting_price,
            "deposit_cents": service.provider.deposit_cents,
        }
    return pricing_data, starting_prices


def _compress_image(file_obj, max_px: int = 700, quality: int = 80):
    try:
        file_obj.seek(0)
        with Image.open(file_obj) as image:
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")
            image.thumbnail((max_px, max_px), Image.LANCZOS)
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=quality, optimize=True)
        return ContentFile(buffer.getvalue()), ".jpg"
    except Exception:
        file_obj.seek(0)
        return file_obj, os.path.splitext(file_obj.name)[1]


def save_upload(file_obj, prefix: str):
    if not file_obj:
        return None
    compressed, extension = _compress_image(file_obj)
    original_name = os.path.basename(file_obj.name)
    base_name, _ = os.path.splitext(original_name)
    filename = f"{base_name}{extension or ''}"
    return default_storage.save(os.path.join(prefix, filename), compressed)


def save_current_hair_picture(file_obj):
    return save_upload(file_obj, "bookings/current/")


def save_inspiration_pictures(files):
    inspiration_paths = []
    for upload in files:
        saved = save_upload(upload, "bookings/inspiration/")
        if saved:
            inspiration_paths.append(saved)
    return inspiration_paths
