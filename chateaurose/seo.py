from __future__ import annotations

from django.conf import settings


def build_base_url(request) -> str:
    host = settings.CANONICAL_HOST or request.get_host()
    scheme = settings.CANONICAL_SCHEME or request.scheme
    return f"{scheme}://{host}"


def build_absolute_url(request, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{build_base_url(request)}{path}"
