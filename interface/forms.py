from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

from chateaurose.domain.services.reviews import rating_label
from chateaurose.domain.exceptions import ValidationError as DomainValidationError
from chateaurose.domain.services.booking_deadlines import require_minimum_notice

from booking.models import Provider
from chateaurose.infrastructure.provider_catalog import SALON_LOCATION_LABEL
from interface.models import MarketingService, ServiceRequest


class ServiceRequestForm(forms.ModelForm):
    marketing_service = forms.ModelChoiceField(
        queryset=MarketingService.objects.all(),
        label="Service",
    )
    contact = forms.CharField(
        label="Ton contact (WhatsApp ou email)",
        required=True,
    )
    availabilities = forms.MultipleChoiceField(
        label="Tes disponibilités",
        choices=ServiceRequest.AVAILABILITY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    class Meta:
        model = ServiceRequest
        fields = [
            "marketing_service",
            "availabilities",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contact"].required = True
        self.fields["contact"].widget.attrs.setdefault("autocomplete", "email")
        self.fields["contact"].widget.attrs.setdefault("inputmode", "email")
        self.fields["contact"].widget.attrs.setdefault(
            "placeholder",
            "Ex : 06 12 34 56 78 ou toi@email.com",
        )
        self.fields["availabilities"].help_text = "Coche les créneaux qui te vont."

    def clean_contact(self):
        raw_contact = (self.cleaned_data.get("contact") or "").strip()
        if not raw_contact:
            raise forms.ValidationError("Renseigne un numéro WhatsApp ou un email.")

        if "@" in raw_contact:
            try:
                validate_email(raw_contact)
            except ValidationError:
                raise forms.ValidationError(
                    "Entre un email valide ou un numéro WhatsApp valide."
                )
            return {"kind": "email", "value": raw_contact.lower()}

        phone = "".join(char for char in raw_contact if char.isdigit() or char == "+")
        if len(phone.replace("+", "")) < 8:
            raise forms.ValidationError(
                "Entre un numéro WhatsApp valide ou un email valide."
            )
        return {"kind": "phone", "value": phone}

    def save(self, commit=True):
        instance = super().save(commit=False)
        contact = self.cleaned_data.get("contact") or {}
        if contact.get("kind") == "email":
            instance.client_email = contact.get("value", "")
            instance.client_phone = ""
        else:
            instance.client_phone = contact.get("value", "")
            instance.client_email = ""
        instance.details = ""
        if commit:
            instance.save()
        return instance


class GenericBookingRequestForm(forms.Form):
    client_name = forms.CharField(label="Ton prénom et nom")
    client_email = forms.EmailField(label="Email")
    client_phone = forms.CharField(label="Téléphone / WhatsApp")
    desired_date = forms.CharField(label="Date ou disponibilités souhaitées")
    location_preference = forms.ChoiceField(
        label="Préférence de lieu",
        choices=(("salon", "Chez la prestataire"), ("domicile", "À domicile")),
        required=False,
    )
    hair_length = forms.CharField(label="Longueur de cheveux", required=False)
    requested_options = forms.CharField(label="Options souhaitées", required=False)
    service_fee_coupon_code = forms.CharField(label="Code promo", required=False)

    def clean_desired_date(self):
        raw_value = (self.cleaned_data.get("desired_date") or "").strip()
        if not raw_value:
            raise forms.ValidationError(
                "Indique une date, un horaire ou tes disponibilités."
            )
        for date_format in ("%Y-%m-%dT%H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(raw_value, date_format)
                return timezone.make_aware(parsed).isoformat()
            except (ValueError, TypeError):
                continue
        return raw_value

    def clean_requested_options(self):
        raw_value = (self.cleaned_data.get("requested_options") or "").strip()
        if not raw_value:
            return []
        return [item.strip() for item in raw_value.split(",") if item.strip()]

    def clean_location_preference(self):
        return self.cleaned_data.get("location_preference") or "salon"


class ProviderBookingRequestForm(forms.Form):
    service_id = forms.IntegerField(label="Service souhaité")
    client_name = forms.CharField(label="Ton nom")
    client_email = forms.EmailField(label="Email")
    location = forms.CharField(label="Lieu de prestation", required=False)
    location_preference = forms.ChoiceField(
        choices=(("salon", "Chez la prestataire"), ("domicile", "À domicile")),
        required=False,
    )
    desired_date = forms.CharField(label="Date souhaitée")
    hair_length = forms.CharField(label="Longueur de cheveux", required=False)
    general_adjustments = forms.JSONField(label="Suppléments", required=False)
    meche = forms.BooleanField(label="Besoin de mèches fournies", required=False)
    service_fee_coupon_code = forms.CharField(label="Code partenaire", required=False)
    payment_auth_id = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        self.provider = kwargs.pop("provider", None)
        self.require_payment_auth = kwargs.pop("require_payment_auth", True)
        self.partial_prefill_mode = kwargs.pop("partial_prefill_mode", False)
        super().__init__(*args, **kwargs)
        if self.partial_prefill_mode:
            self.fields["client_name"].required = False
            self.fields["client_email"].required = False
            self.fields["desired_date"].required = False

    def clean_desired_date(self):
        raw_value = self.cleaned_data.get("desired_date")
        if self.partial_prefill_mode and not raw_value:
            return ""
        if not raw_value:
            raise forms.ValidationError(
                "Merci d'utiliser une date au format JJ/MM/AAAA HH:MM."
            )

        for date_format in ("%Y-%m-%dT%H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(raw_value, date_format)
                aware_date = timezone.make_aware(parsed)
                try:
                    require_minimum_notice(
                        desired_at=aware_date,
                        now=timezone.now(),
                    )
                except DomainValidationError as exc:
                    raise forms.ValidationError(str(exc)) from exc
                return aware_date.isoformat()
            except (ValueError, TypeError):
                continue

        raise forms.ValidationError(
            "Merci d'utiliser une date au format JJ/MM/AAAA HH:MM."
        )

    def clean(self):
        cleaned_data = super().clean()
        location_choice = (cleaned_data.get("location") or "").strip()
        location_preference = cleaned_data.get("location_preference")
        location = location_choice

        if self.partial_prefill_mode:
            cleaned_data["location"] = location
            cleaned_data["location_preference"] = location_preference
            selected_adjustments = cleaned_data.get("general_adjustments")
            if selected_adjustments in (None, ""):
                cleaned_data["general_adjustments"] = []
            elif isinstance(selected_adjustments, list):
                cleaned_data["general_adjustments"] = [
                    str(item).strip()
                    for item in selected_adjustments
                    if str(item).strip()
                ]
            else:
                raise forms.ValidationError("Format de suppléments invalide.")

            return cleaned_data

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
        elif not location:
            self.add_error(
                "location", "Merci de choisir une zone pour le rendez-vous à domicile."
            )

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
            cleaned_data["general_adjustments"] = [
                str(item).strip() for item in selected_adjustments if str(item).strip()
            ]
        else:
            raise forms.ValidationError("Format de suppléments invalide.")

        cleaned_data["location"] = location
        cleaned_data["location_preference"] = location_preference
        cleaned_data["client_address"] = ""
        return cleaned_data


class ProviderQuestionForm(forms.Form):
    client_name = forms.CharField(label="Ton nom")
    client_email = forms.EmailField(label="Email")
    message = forms.CharField(
        label="Ta question", widget=forms.Textarea(attrs={"rows": 4})
    )


class VerifiedReviewForm(forms.Form):
    rating = forms.ChoiceField(
        label="Ta note",
        choices=[(str(i), rating_label(i)) for i in range(1, 6)],
        widget=forms.RadioSelect,
    )
    comment = forms.CharField(
        label="Ton avis",
        widget=forms.Textarea(
            attrs={"rows": 5, "placeholder": "Raconte ton expérience en quelques mots."}
        ),
    )
    consent_to_publish = forms.BooleanField(
        label="J'accepte que mon avis soit relu puis publié sur Château Rose avec mon prénom abrégé.",
        required=True,
    )

    def clean_comment(self):
        comment = (self.cleaned_data.get("comment") or "").strip()
        if not comment:
            raise forms.ValidationError("Écris un court avis pour continuer.")
        return comment
