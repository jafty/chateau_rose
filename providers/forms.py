from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class ProviderSignupForm(UserCreationForm):
    name = forms.CharField(label="Nom du prestataire", max_length=255)
    contact_email = forms.EmailField(label="Email de contact")
    contact_phone = forms.CharField(label="Téléphone", max_length=64)

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
