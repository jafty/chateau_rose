from __future__ import annotations

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class CanonicalHostRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        canonical_host = settings.CANONICAL_HOST
        if canonical_host:
            request_host = request.get_host()
            request_hostname = request_host.split(":", 1)[0]
            canonical_hostname = canonical_host.split(":", 1)[0]
            if (
                request_hostname != canonical_hostname
                and request.method in {"GET", "HEAD"}
            ):
                canonical_scheme = settings.CANONICAL_SCHEME or request.scheme
                canonical_url = (
                    f"{canonical_scheme}://{canonical_host}{request.get_full_path()}"
                )
                return HttpResponsePermanentRedirect(canonical_url)
        return self.get_response(request)
