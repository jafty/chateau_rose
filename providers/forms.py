from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import forms
from django.contrib.auth import get_user_model
from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm
from django.template import loader

from booking.models import Provider, ProviderBlockedSlot, ProviderPhoto, Service
from chateaurose.infrastructure.email_notifier import EmailNotifier


class ProviderPartnershipRequestForm(forms.Form):
    name = forms.CharField(
        label="Nom et prénom",
        max_length=255,
    )
    email = forms.EmailField(label="Email", required=True)
    social = forms.CharField(
        label="Instagram ou réseau social",
        required=False,
        max_length=255,
    )
    message = forms.CharField(
        label="Parle-nous de tes prestations",
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Décris tes spécialités, zones, disponibilités, etc.",
    )


class ProviderSignupForm(UserCreationForm):
    name = forms.CharField(label="Nom de la prestataire ou du prestataire", max_length=255)
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
        help_text="Quartier ou zone où tu accueilles ta clientèle.",
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


class ProviderPasswordResetForm(PasswordResetForm):
    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        if settings.BREVO_API_KEY:
            subject = loader.render_to_string(subject_template_name, context)
            subject = "".join(subject.splitlines())
            body = loader.render_to_string(email_template_name, context)
            notifier = EmailNotifier()
            notifier.notify(recipient=to_email, subject=subject, body=body)
            return
        super().send_mail(
            subject_template_name,
            email_template_name,
            context,
            from_email,
            to_email,
            html_email_template_name=html_email_template_name,
        )


class ProviderInfoForm(forms.ModelForm):
    class Meta:
        model = Provider
        fields = ("availabilities", "additional_info")
        widgets = {
            "availabilities": forms.Textarea(attrs={"rows": 4}),
            "additional_info": forms.Textarea(attrs={"rows": 4}),
        }


class ProviderServiceForm(forms.ModelForm):
    base_price_euros = forms.CharField(label="Prix (hors frais de service)")
    meche_bonus_euros = forms.CharField(label="Supplément mèches", required=False)
    at_home_bonus_euros = forms.CharField(label="Supplément domicile", required=False)

    class Meta:
        model = Service
        fields = (
            "name",
            "image",
            "image_url",
            "base_price_euros",
            "meche_bonus_euros",
            "at_home_bonus_euros",
        )

    @staticmethod
    def _euros_to_cents(raw_value: str | None, *, allow_blank: bool = True) -> int:
        normalized = (raw_value or "").replace(",", ".").strip()
        if not normalized:
            if allow_blank:
                return 0
            raise forms.ValidationError("Ce champ est requis.")
        try:
            euros = Decimal(normalized)
        except (InvalidOperation, TypeError):
            raise forms.ValidationError("Merci d'indiquer un montant valide.")

        cents = int((euros * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if cents < 0:
            raise forms.ValidationError("Le montant doit être positif.")
        return cents

    @staticmethod
    def cents_to_euros(cents_value: int | None) -> str:
        cents_value = cents_value or 0
        return f"{Decimal(cents_value) / Decimal('100'):.2f}".replace(".", ",")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["base_price_euros"] = self.cents_to_euros(self.instance.base_price_cents)
            self.initial["meche_bonus_euros"] = self.cents_to_euros(self.instance.meche_bonus_cents)
            self.initial["at_home_bonus_euros"] = self.cents_to_euros(self.instance.at_home_bonus_cents)

    def clean_base_price_euros(self):
        return self._euros_to_cents(self.cleaned_data.get("base_price_euros"), allow_blank=False)

    def clean_meche_bonus_euros(self):
        return self._euros_to_cents(self.cleaned_data.get("meche_bonus_euros"))

    def clean_at_home_bonus_euros(self):
        return self._euros_to_cents(self.cleaned_data.get("at_home_bonus_euros"))

    def save(self, commit=True):
        self.instance.base_price_cents = self.cleaned_data["base_price_euros"]
        self.instance.meche_bonus_cents = self.cleaned_data["meche_bonus_euros"]
        self.instance.at_home_bonus_cents = self.cleaned_data["at_home_bonus_euros"]
        return super().save(commit=commit)


class ProviderBlockedSlotForm(forms.ModelForm):
    class Meta:
        model = ProviderBlockedSlot
        fields = ("starts_at", "ends_at", "reason")
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason"].required = False
        self.fields["reason"].initial = "Ce créneau n'est plus disponible"

    def clean_reason(self):
        reason = (self.cleaned_data.get("reason") or "").strip()
        return reason or "Ce créneau n'est plus disponible"

    def save(self, commit=True):
        self.instance.is_recurring = False
        self.instance.weekdays = ""
        self.instance.starts_time = None
        self.instance.ends_time = None
        self.instance.recurrence_starts_on = None
        self.instance.recurrence_ends_on = None
        self.instance.source = ProviderBlockedSlot.SOURCE_MANUAL
        self.instance.is_active = True
        return super().save(commit=commit)


class ProviderPhotoForm(forms.ModelForm):
    class Meta:
        model = ProviderPhoto
        fields = ("image", "image_url", "caption", "order")
