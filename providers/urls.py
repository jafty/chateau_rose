from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "providers"

urlpatterns = [
    path("", views.index, name="providers_index"),
    path("compte/", views.account, name="account"),
    path("inscription/", views.signup, name="signup"),
    path("demandes/<str:booking_id>/", views.booking_detail, name="booking_detail"),
    path(
        "connexion/",
        auth_views.LoginView.as_view(template_name="providers/login.html"),
        name="login",
    ),
    path(
        "mot-de-passe/",
        views.ProviderPasswordResetView.as_view(
            template_name="providers/password_reset.html",
            email_template_name="providers/password_reset_email.html",
            subject_template_name="providers/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "mot-de-passe/envoye/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="providers/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "mot-de-passe/confirmation/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="providers/password_reset_confirm.html",
            success_url=reverse_lazy("providers:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "mot-de-passe/termine/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="providers/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path(
        "deconnexion/",
        auth_views.LogoutView.as_view(next_page="interface:home"),
        name="logout",
    ),
]
