from django.urls import path

from . import views

app_name = "interface"

urlpatterns = [
    path("", views.home, name="home"),
    path("a-propos/", views.about, name="about"),
    path("prestataires/", views.provider_list, name="provider_list"),
    path("prestataires/<int:provider_id>/", views.provider_detail, name="provider_detail"),
    path("bookings/<str:booking_id>/provider-action/", views.provider_action, name="provider_action"),
    path("bookings/<str:booking_id>/client-action/", views.client_action, name="client_action"),
    path("services/<slug:service_slug>/", views.service_page, name="service_page"),
    path("services/<slug:service_slug>/<slug:city_slug>/", views.service_city_page, name="service_city_page"),
    path(
        "services/<slug:service_slug>/<slug:city_slug>/<slug:district_slug>/",
        views.service_city_district_page,
        name="service_city_district_page",
    ),
]
