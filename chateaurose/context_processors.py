from __future__ import annotations

from django.conf import settings


def canonical_url(request):
    host = settings.CANONICAL_HOST or request.get_host()
    scheme = settings.CANONICAL_SCHEME or request.scheme
    return {"canonical_url": f"{scheme}://{host}{request.get_full_path()}"}
