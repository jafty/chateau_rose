import os
from io import BytesIO
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps
from chateaurose.domain.services.pricing import compute_checkout_amounts_cents


def format_price(cents: int) -> str:
    euros = cents / 100
    if cents % 100 == 0:
        return f"{euros:.0f} €"
    return f"{euros:.2f} €"


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
        service.price_display = format_price(starting_price)
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
