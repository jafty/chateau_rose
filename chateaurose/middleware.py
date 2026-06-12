from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.http import HttpResponsePermanentRedirect
from django.shortcuts import render
from django.utils.cache import patch_vary_headers


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
    preview_cookie_name = "maintenance_preview"
    preview_cookie_salt = "chateaurose.maintenance-preview"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.MAINTENANCE_MODE:
            return self.get_response(request)

        if self._is_exempt_path(request.path_info):
            response = self.get_response(request)
            self._update_preview_cookie(request, response)
            return response

        if self._can_preview_site(request):
            response = self.get_response(request)
            self._update_preview_cookie(request, response)
            return response

        response = render(
            request,
            "maintenance.html",
            {
                "contact_email": settings.MAINTENANCE_CONTACT_EMAIL,
            },
            status=503,
        )
        response["Retry-After"] = str(settings.MAINTENANCE_RETRY_AFTER_SECONDS)
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        patch_vary_headers(response, ["Cookie"])
        return response

    def _is_exempt_path(self, path: str) -> bool:
        return any(
            path == prefix.rstrip("/") or path.startswith(prefix)
            for prefix in self.exempt_path_prefixes
        )

    def _can_preview_site(self, request) -> bool:
        return self._is_admin_user(request) or self._has_valid_preview_cookie(request)

    def _is_admin_user(self, request) -> bool:
        user = getattr(request, "user", None)
        if user and user.is_authenticated and (user.is_staff or user.is_superuser):
            return True

        user_id = request.session.get("_auth_user_id")
        if not user_id:
            return False

        user_model = get_user_model()
        try:
            session_user = user_model.objects.only(
                "id", "is_active", "is_staff", "is_superuser"
            ).get(pk=user_id)
        except user_model.DoesNotExist:
            return False
        return bool(
            session_user.is_active
            and (session_user.is_staff or session_user.is_superuser)
        )

    def _has_valid_preview_cookie(self, request) -> bool:
        cookie_value = request.COOKIES.get(self.preview_cookie_name)
        if not cookie_value:
            return False
        try:
            payload = signing.loads(
                cookie_value,
                salt=self.preview_cookie_salt,
                max_age=settings.MAINTENANCE_PREVIEW_COOKIE_MAX_AGE_SECONDS,
            )
        except signing.BadSignature:
            return False
        return payload == {"preview": "admin"}

    def _update_preview_cookie(self, request, response) -> None:
        if self._is_admin_user(request):
            response.set_cookie(
                self.preview_cookie_name,
                signing.dumps(
                    {"preview": "admin"},
                    salt=self.preview_cookie_salt,
                ),
                max_age=settings.MAINTENANCE_PREVIEW_COOKIE_MAX_AGE_SECONDS,
                httponly=True,
                secure=request.is_secure(),
                samesite="Lax",
            )
        elif self.preview_cookie_name in request.COOKIES:
            response.delete_cookie(
                self.preview_cookie_name,
                samesite="Lax",
            )
