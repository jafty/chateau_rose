from django import forms

from interface.models import ServiceRequest


class ServiceRequestForm(forms.ModelForm):
    class Meta:
        model = ServiceRequest
        fields = ["client_name", "client_phone", "details"]
        widgets = {
            "details": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "client_name": "Votre nom",
            "client_phone": "Téléphone",
            "details": "Détails ou besoin",
        }
