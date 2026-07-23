from __future__ import annotations

import json

from django.conf import settings

from chateaurose.seo import build_absolute_url, build_base_url
from interface.marketing_cities import MARKETING_CITY_ENTRIES


def canonical_url(request):
    base_url = build_base_url(request)
    canonical = f"{base_url}{request.get_full_path()}"
    og_image_url = build_absolute_url(request, settings.DEFAULT_OG_IMAGE_PATH)

    business_address = {
        "@type": "PostalAddress",
        "streetAddress": settings.BUSINESS_STREET_ADDRESS,
        "postalCode": settings.BUSINESS_POSTAL_CODE,
        "addressLocality": settings.BUSINESS_CITY,
        "addressCountry": settings.BUSINESS_COUNTRY,
    }
    business_schema_id = f"{base_url}#business"
    business_phone_tel = settings.BUSINESS_PHONE.replace(" ", "")
    business_schema = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "@id": business_schema_id,
        "name": settings.BUSINESS_NAME,
        "url": base_url,
        "telephone": business_phone_tel,
        "address": business_address,
    }

    return {
        "canonical_url": canonical,
        "og_image_url": og_image_url,
        "business_name": settings.BUSINESS_NAME,
        "business_phone": settings.BUSINESS_PHONE,
        "business_phone_tel": business_phone_tel,
        "business_street_address": settings.BUSINESS_STREET_ADDRESS,
        "business_postal_code": settings.BUSINESS_POSTAL_CODE,
        "business_city": settings.BUSINESS_CITY,
        "business_country": settings.BUSINESS_COUNTRY,
        "business_schema_id": business_schema_id,
        "business_schema_json": json.dumps(business_schema, ensure_ascii=False),
    }


def analytics_flags(request):
    user = getattr(request, "user", None)
    is_authenticated = bool(getattr(user, "is_authenticated", False))
    is_staff = bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
    session_excluded = bool(getattr(request, "session", {}).get("analytics_excluded", False))
    analytics_enabled = not settings.DEBUG and not is_authenticated and not is_staff and not session_excluded
    return {"analytics_enabled": analytics_enabled}


def marketing_cities(_request):
    return {"marketing_cities": MARKETING_CITY_ENTRIES}
