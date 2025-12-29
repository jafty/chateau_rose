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
    desired_date = forms.DateTimeField(
        label="Date souhaitée",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "inputmode": "numeric",
                "placeholder": "JJ/MM/AAAA HH:MM",
            },
            format="%Y-%m-%dT%H:%M",
        ),
        help_text="Format : JJ/MM/AAAA HH:MM (24h)",
    )

    class Meta:
        model = ServiceRequest
        fields = [
            "marketing_service",
            "zone",
            "desired_date",
            "client_name",
            "client_phone",
            "details",
        ]
        widgets = {
            "details": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "client_name": "Ton nom",
            "client_phone": "Téléphone",
            "details": "Détails ou besoin",
        }
