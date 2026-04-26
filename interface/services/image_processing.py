import os
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps


def compress_image_field(image_field, *, max_px: int, quality: int = 80) -> None:
    if not image_field:
        return

    try:
        image_field.seek(0)
        with Image.open(image_field) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            image.thumbnail((max_px, max_px), Image.LANCZOS)
            buffer = BytesIO()
            image.save(buffer, format="WEBP", quality=quality, method=6, optimize=True)
    except Exception:
        image_field.seek(0)
        return

    original_filename = os.path.basename(image_field.name or "image")
    stem, _ = os.path.splitext(original_filename)
    image_field.save(f"{stem}.webp", ContentFile(buffer.getvalue()), save=False)
