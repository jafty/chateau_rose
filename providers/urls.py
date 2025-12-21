from django.urls import path

from . import views

app_name = "providers"

urlpatterns = [
    path("", views.index, name="providers_index"),
]
