from django.urls import path

from . import views

app_name = "interface"

urlpatterns = [
    path("", views.home, name="home"),
]
