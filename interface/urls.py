from django.urls import path

from . import views

app_name = "interface"

urlpatterns = [
    path("", views.home, name="home"),
    path("villes/<slug:city_slug>/", views.city_page, name="city_page"),
    path("a-propos/", views.about, name="about"),
    path("mentions-legales/", views.legal_notice, name="legal_notice"),
    path("cgv/", views.terms_of_sale, name="terms_of_sale"),
    path("cgu/", views.terms_of_use, name="terms_of_use"),
    path("confidentialite/", views.privacy_policy, name="privacy_policy"),
    path("prestataires/", views.provider_list, name="provider_list"),
    path(
        "prestataires/coiffure-afro-a-domicile/",
        views.at_home_provider_list,
        name="at_home_provider_list",
    ),
    path("prestataires/<int:provider_id>/", views.provider_detail, name="provider_detail"),
    path(
        "prestataires/payment-intent/",
        views.provider_payment_intent,
        name="provider_payment_intent",
    ),
    path(
        "prestataires/booking-draft/",
        views.provider_booking_draft,
        name="provider_booking_draft",
    ),
    path(
        "prestataires/payment-return/",
        views.provider_payment_return,
        name="provider_payment_return",
    ),
    path("mentions-legales-rgpd/", views.legal, name="legal"),
    path("zones/recherche/", views.zone_search, name="zone_search"),
    path("bookings/<str:booking_id>/provider-action/", views.provider_action, name="provider_action"),
    path("bookings/<str:booking_id>/client-action/", views.client_action, name="client_action"),
    path("bookings/<str:booking_id>/confirmation/", views.client_confirmation, name="client_confirmation"),
    path("bookings/<str:booking_id>/proposition/", views.client_proposal, name="client_proposal"),
    path("services/<slug:service_slug>/", views.service_page, name="service_page"),
    path("services/<slug:service_slug>/<slug:city_slug>/", views.service_city_page, name="service_city_page"),
    path(
        "services/<slug:service_slug>/<slug:city_slug>/<slug:district_slug>/",
        views.service_city_district_page,
        name="service_city_district_page",
    ),
]
