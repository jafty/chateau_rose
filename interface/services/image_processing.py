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

    base_name, _ = os.path.splitext(image_field.name)
    image_field.save(f"{base_name}.webp", ContentFile(buffer.getvalue()), save=False)
