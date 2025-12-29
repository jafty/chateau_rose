from django.urls import path

from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "providers"

urlpatterns = [
    path("", views.index, name="providers_index"),
    path(
        "connexion/",
        auth_views.LoginView.as_view(template_name="providers/login.html"),
        name="login",
    ),
    path(
        "deconnexion/",
        auth_views.LogoutView.as_view(next_page="interface:home"),
        name="logout",
    ),
]
