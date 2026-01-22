from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from booking.models import Provider


class ProviderSignupForm(UserCreationForm):
    name = forms.CharField(label="Nom du prestataire", max_length=255)
    contact_email = forms.EmailField(label="Email de contact")
    contact_phone = forms.CharField(label="Téléphone", max_length=64)
    location_mode = forms.ChoiceField(
        label="Où réalises-tu tes prestations ?",
        choices=Provider.LOCATION_MODE_CHOICES,
        initial=Provider.LOCATION_MODE_HYBRID,
        widget=forms.RadioSelect,
        help_text="Choisis si tu te déplaces, accueilles en salon/chez toi, ou les deux.",
    )
    salon_zone = forms.CharField(
        label="Zone du salon",
        required=False,
        help_text="Quartier ou zone où tu accueilles tes clientes.",
    )
    salon_address = forms.CharField(
        label="Adresse du salon",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Adresse complète, communiquée seulement après confirmation.",
    )

    email = forms.EmailField(label="Email", required=True)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True

    def save(self, commit=True):
        user = super().save(commit=commit)
        return user

    def clean(self):
        cleaned_data = super().clean()
        location_mode = cleaned_data.get("location_mode")
        salon_zone = (cleaned_data.get("salon_zone") or "").strip()
        salon_address = (cleaned_data.get("salon_address") or "").strip()

        if location_mode in (
            Provider.LOCATION_MODE_SALON_ONLY,
            Provider.LOCATION_MODE_HYBRID,
        ):
            if not salon_zone:
                self.add_error("salon_zone", "Merci d'indiquer la zone du salon.")
            if not salon_address:
                self.add_error("salon_address", "Merci d'indiquer l'adresse du salon.")

        cleaned_data["salon_zone"] = salon_zone
        cleaned_data["salon_address"] = salon_address
        return cleaned_data
