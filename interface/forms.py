from datetime import datetime

from django import forms
from django.utils import timezone

from booking.models import Provider
from chateaurose.infrastructure.provider_catalog import SALON_LOCATION_LABEL
from interface.models import MarketingService, ServiceRequest


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultiFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            return [super().clean(data, initial)]

        errors = []
        cleaned_files = []
        for item in data:
            try:
                cleaned_files.append(super().clean(item, initial))
            except forms.ValidationError as exc:
                errors.extend(exc.error_list)

        if errors:
            raise forms.ValidationError(errors)
        return cleaned_files


class ServiceRequestForm(forms.ModelForm):
    marketing_service = forms.ModelChoiceField(
        queryset=MarketingService.objects.all(),
        label="Service",
    )
    location_preference = forms.ChoiceField(
        label="Où veux-tu réaliser la prestation ?",
        choices=ServiceRequest.LOCATION_PREFERENCE_CHOICES,
        initial=ServiceRequest.LOCATION_PREFERENCE_CLIENT_HOME,
        widget=forms.RadioSelect,
    )
    availabilities = forms.MultipleChoiceField(
        label="Disponibilités",
        required=True,
        choices=ServiceRequest.AVAILABILITY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )
    client_email = forms.EmailField(
        label="Ton email",
        required=True,
    )
    client_phone = forms.CharField(
        label="Ton numéro WhatsApp (optionnel)",
        required=False,
    )
    inspiration_picture = forms.ImageField(
        label="Photo de référence (optionnel)",
        required=False,
    )

    class Meta:
        model = ServiceRequest
        fields = [
            "marketing_service",
            "location_preference",
            "client_email",
            "client_phone",
            "details",
            "availabilities",
        ]
        widgets = {
            "details": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "client_phone": "Ton numéro WhatsApp (optionnel)",
            "details": "Décris ta demande",
            "availabilities": "Tes disponibilités",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["details"].required = True
        self.fields["client_email"].widget.attrs.setdefault("autocomplete", "email")
        self.fields["client_phone"].widget.attrs.setdefault("autocomplete", "tel")
        self.fields["details"].widget.attrs.setdefault(
            "placeholder",
            "Exemple : knotless braids taille moyenne, semaine prochaine, chez moi / chez la coiffeuse, rendu naturel et soigné.",
        )
        self.fields["inspiration_picture"].widget.attrs.setdefault("class", "request-file-input")

    def clean_client_phone(self):
        raw_phone = (self.cleaned_data.get("client_phone") or "").strip()
        if not raw_phone:
            return ""

        phone = "".join(char for char in raw_phone if char.isdigit() or char == "+")
        if len(phone.replace("+", "")) < 8:
            raise forms.ValidationError("Merci de renseigner un numéro valide ou laisse ce champ vide.")
        return phone

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data


class ProviderBookingRequestForm(forms.Form):
    service_id = forms.IntegerField(label="Service souhaité")
    client_name = forms.CharField(label="Ton nom")
    client_email = forms.EmailField(label="Email")
    location = forms.CharField(label="Lieu de prestation", required=False)
    client_address = forms.CharField(label="Adresse complète", required=False)
    location_preference = forms.ChoiceField(
        choices=(("salon", "Chez la prestataire"), ("domicile", "À domicile")),
        required=False,
    )
    desired_date = forms.CharField(label="Date souhaitée")
    hair_length = forms.CharField(label="Longueur de cheveux", required=False)
    general_adjustments = forms.JSONField(label="Suppléments", required=False)
    meche = forms.BooleanField(label="Besoin de mèches fournies", required=False)
    current_hair_picture_file = forms.FileField(label="Photo de tes cheveux", required=False)
    current_hair_picture = forms.CharField(required=False)
    inspiration_pictures = MultipleFileField(
        label="Photos d'inspiration",
        required=False,
        widget=MultiFileInput(attrs={"multiple": True}),
    )
    free_text = forms.CharField(label="Infos complémentaires", required=False, widget=forms.Textarea)
    payment_auth_id = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        self.provider = kwargs.pop("provider", None)
        self.require_payment_auth = kwargs.pop("require_payment_auth", True)
        self.require_current_hair_picture = kwargs.pop("require_current_hair_picture", True)
        super().__init__(*args, **kwargs)

    def clean_desired_date(self):
        raw_value = self.cleaned_data.get("desired_date")
        if not raw_value:
            raise forms.ValidationError("Merci d'utiliser une date au format JJ/MM/AAAA HH:MM.")

        for date_format in ("%Y-%m-%dT%H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(raw_value, date_format)
                aware_date = timezone.make_aware(parsed)
                return aware_date.isoformat()
            except (ValueError, TypeError):
                continue

        raise forms.ValidationError("Merci d'utiliser une date au format JJ/MM/AAAA HH:MM.")

    def clean(self):
        cleaned_data = super().clean()
        location_choice = (cleaned_data.get("location") or "").strip()
        client_address = (cleaned_data.get("client_address") or "").strip()
        location_preference = cleaned_data.get("location_preference")
        location = location_choice

        if self.provider:
            if self.provider.location_mode == Provider.LOCATION_MODE_SALON_ONLY:
                location = self.provider.salon_zone or SALON_LOCATION_LABEL
                location_preference = "salon"
            elif self.provider.location_mode == Provider.LOCATION_MODE_HYBRID:
                if location_preference == "salon":
                    location = self.provider.salon_zone or SALON_LOCATION_LABEL
                elif location_preference == "domicile" or location_choice:
                    location = location_choice
                    location_preference = location_preference or "domicile"
                else:
                    raise forms.ValidationError(
                        "Merci de choisir si tu préfères venir chez la prestataire ou demander un déplacement."
                    )
            else:
                location_preference = location_preference or "domicile"

        if location_preference == "salon":
            if not self.provider or not self.provider.salon_zone:
                raise forms.ValidationError(
                    "Le lieu chez la prestataire n'est pas encore renseigné."
                )
            if not self.provider.salon_address:
                raise forms.ValidationError(
                    "L'adresse de la prestataire doit être renseignée pour confirmer un rendez-vous."
                )
        elif not client_address:
            raise forms.ValidationError("Merci d'indiquer ton adresse complète.")

        if not location:
            raise forms.ValidationError("Merci de choisir un lieu.")

        if self.require_current_hair_picture and not cleaned_data.get("current_hair_picture_file") and not cleaned_data.get("current_hair_picture"):
            raise forms.ValidationError("Merci d'ajouter une photo de tes cheveux.")

        if self.require_payment_auth and not cleaned_data.get("payment_auth_id"):
            raise forms.ValidationError(
                "Merci d'ajouter une empreinte bancaire pour sécuriser la demande."
            )

        if self.provider and not self.provider.provides_meche:
            cleaned_data["meche"] = False


        selected_adjustments = cleaned_data.get("general_adjustments")
        if selected_adjustments in (None, ""):
            cleaned_data["general_adjustments"] = []
        elif isinstance(selected_adjustments, list):
            cleaned_data["general_adjustments"] = [str(item).strip() for item in selected_adjustments if str(item).strip()]
        else:
            raise forms.ValidationError("Format de suppléments invalide.")
        cleaned_data["location"] = location
        cleaned_data["location_preference"] = location_preference
        cleaned_data["client_address"] = client_address
        return cleaned_data

    def get_inspiration_files(self):
        return self.files.getlist("inspiration_pictures")


class ProviderQuestionForm(forms.Form):
    client_name = forms.CharField(label="Ton nom")
    client_email = forms.EmailField(label="Email")
    message = forms.CharField(label="Ta question", widget=forms.Textarea(attrs={"rows": 4}))
