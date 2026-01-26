"""
URL configuration for chateaurose project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from interface.sitemaps import sitemaps
from interface import views as interface_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("interface.urls")),
    path("booking/", include("booking.urls")),
    path("espace_pro/", include("providers.urls")),
    path("robots.txt", interface_views.robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps()}),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()

if settings.SERVE_MEDIA and settings.MEDIA_ROOT:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
