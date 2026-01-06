from django import forms
from django.urls import reverse

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
        help_text=(
            "Indique ton quartier si tu veux une prestation à domicile,"
            " pour être mis(e) en relation avec un prestataire proche."
        ),
    )
    location_preference = forms.ChoiceField(
        label="Où veux-tu réaliser la prestation ?",
        choices=ServiceRequest.LOCATION_PREFERENCE_CHOICES,
        initial=ServiceRequest.LOCATION_PREFERENCE_CLIENT_HOME,
        widget=forms.RadioSelect,
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
            "location_preference",
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["zone"].widget.attrs.update(
            {
                "data-zone-search-url": reverse("interface:zone_search"),
                "data-zone-value-field": "id",
                "data-zone-label-field": "name",
                "data-zone-search-placeholder": "Cherche une zone ou un quartier",
            }
        )
