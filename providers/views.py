from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from booking.models import Booking, Provider


@login_required(login_url="providers:login")
def index(request):
    try:
        provider = Provider.objects.get(user=request.user)
    except Provider.DoesNotExist:
        return HttpResponseForbidden("Accès réservé aux prestataires enregistrés.")

    bookings = (
        Booking.objects.filter(provider=provider)
        .order_by("-created_at")
        .select_related("service")
    )

    return render(
        request,
        "providers/index.html",
        {
            "provider": provider,
            "bookings": bookings,
        },
    )
