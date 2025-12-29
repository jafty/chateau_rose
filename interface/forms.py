from django import forms

from booking.models import Zone
from interface.models import MarketingService, ServiceRequest


class ServiceRequestForm(forms.ModelForm):
    marketing_service = forms.ModelChoiceField(
        queryset=MarketingService.objects.all(),
        label="Service souhaité",
    )
    zone = forms.ModelChoiceField(
        queryset=Zone.objects.all(),
        required=False,
        label="Zone",
        help_text="Facultatif : nous orientons vers un prestataire proche.",
    )

    class Meta:
        model = ServiceRequest
        fields = ["marketing_service", "zone", "client_name", "client_phone", "details"]
        widgets = {
            "details": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "client_name": "Votre nom",
            "client_phone": "Téléphone",
            "details": "Détails ou besoin",
        }
