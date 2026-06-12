from __future__ import annotations

from django.conf import settings
from django.http import HttpResponsePermanentRedirect
from django.shortcuts import render


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


class MaintenanceModeMiddleware:
    exempt_path_prefixes = ("/admin", "/static/", "/media/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            settings.MAINTENANCE_MODE
            and not self._is_exempt_path(request.path_info)
            and not self._is_admin_user(request)
        ):
            response = render(
                request,
                "maintenance.html",
                {
                    "contact_email": settings.MAINTENANCE_CONTACT_EMAIL,
                },
                status=503,
            )
            response["Retry-After"] = str(settings.MAINTENANCE_RETRY_AFTER_SECONDS)
            return response
        return self.get_response(request)

    def _is_exempt_path(self, path: str) -> bool:
        return any(
            path == prefix.rstrip("/") or path.startswith(prefix)
            for prefix in self.exempt_path_prefixes
        )

    def _is_admin_user(self, request) -> bool:
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and (user.is_staff or user.is_superuser)
        )
