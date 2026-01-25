from urllib.parse import urlparse

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models

from interface.validators import validate_absolute_or_root_relative_url
from interface.services.image_processing import compress_image_field


def _should_compress_image(instance: models.Model, field_name: str) -> bool:
    image_field = getattr(instance, field_name)
    if not image_field:
        return False
    if not instance.pk:
        return True
    try:
        previous = type(instance).objects.get(pk=instance.pk)
    except type(instance).DoesNotExist:
        return True
    previous_field = getattr(previous, field_name)
    if not previous_field:
        return True
    return image_field.name != previous_field.name


class Provider(models.Model):
    LOCATION_MODE_SALON_ONLY = "salon_only"
    LOCATION_MODE_CLIENT_HOME_ONLY = "client_home_only"
    LOCATION_MODE_HYBRID = "hybrid"
    LOCATION_MODE_CHOICES = (
        (LOCATION_MODE_SALON_ONLY, "Salon uniquement"),
        (LOCATION_MODE_CLIENT_HOME_ONLY, "À domicile uniquement"),
        (LOCATION_MODE_HYBRID, "Salon ou domicile"),
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    contact_phone = models.CharField(max_length=64, blank=True)
    contact_email = models.EmailField(blank=True)
    pending_reminder_sent_at = models.DateTimeField(null=True, blank=True)
    salon_zone = models.CharField(
        max_length=255,
        blank=True,
        help_text="Indique la zone ou le quartier où tu reçois au salon.",
    )
    salon_address = models.TextField(
        blank=True,
        help_text="Adresse complète du salon (communiquée après confirmation).",
    )
    profile_image = models.ImageField(upload_to="providers/profile/", blank=True, null=True)
    profile_image_url = models.CharField(
        max_length=500,
        blank=True,
        validators=[validate_absolute_or_root_relative_url],
        help_text=(
            "Upload an image or provide an absolute URL, /root-relative path, "
            "or relative static asset path."
        ),
    )
    location_mode = models.CharField(
        max_length=32,
        choices=LOCATION_MODE_CHOICES,
        default=LOCATION_MODE_HYBRID,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="provider_profile",
    )
    zones = models.ManyToManyField(
        "Zone",
        through="ProviderZone",
        related_name="providers",
        blank=True,
    )
    marketing_services = models.ManyToManyField(
        "interface.MarketingService",
        through="ProviderMarketingService",
        related_name="providers",
        blank=True,
    )

    def __str__(self):
        return self.name

    @property
    def resolved_profile_image(self):
        if self.profile_image:
            return self.profile_image.url
        return self.profile_image_url or None

    @property
    def location_mode_label(self):
        return dict(self.LOCATION_MODE_CHOICES).get(self.location_mode, "")

    def save(self, *args, **kwargs):
        if _should_compress_image(self, "profile_image"):
            compress_image_field(self.profile_image, max_px=1200, quality=80)
        return super().save(*args, **kwargs)


class Zone(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, default="")

    def __str__(self):
        return self.name


class Service(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="services")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, default="", blank=True)
    base_price_cents = models.IntegerField()
    hair_length_adjustments = models.JSONField(default=dict, blank=True)
    meche_bonus_cents = models.IntegerField(default=0)

    class Meta:
        unique_together = (("provider", "name"), ("provider", "slug"))

    def __str__(self):
        return f"{self.name} ({self.provider})"


class ProviderPhoto(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="providers/gallery/", blank=True)
    image_url = models.CharField(
        max_length=500,
        blank=True,
        validators=[validate_absolute_or_root_relative_url],
        help_text=(
            "Upload an image or provide an absolute URL, /root-relative path, "
            "or relative static asset path."
        ),
    )
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return f"Photo de {self.provider}"

    @property
    def resolved_url(self):
        if self.image:
            return self.image.url
        return self.image_url or None

    def save(self, *args, **kwargs):
        if _should_compress_image(self, "image"):
            compress_image_field(self.image, max_px=900, quality=80)
        return super().save(*args, **kwargs)


class ProviderZone(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="provider_zones")
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="zone_providers")

    class Meta:
        unique_together = ("provider", "zone")

    def __str__(self):
        return f"{self.provider} - {self.zone}"


class ProviderMarketingService(models.Model):
    provider = models.ForeignKey(
        Provider, on_delete=models.CASCADE, related_name="provider_marketing_services"
    )
    service = models.ForeignKey(
        "interface.MarketingService",
        on_delete=models.CASCADE,
        related_name="marketing_service_providers",
    )

    class Meta:
        unique_together = ("provider", "service")

    def __str__(self):
        return f"{self.provider} - {self.service}"


class Booking(models.Model):
    STATUS_CHOICES = [
        ("SUBMITTED", "SUBMITTED"),
        ("PENDING_CLIENT_VALIDATION", "PENDING_CLIENT_VALIDATION"),
        ("CONFIRMED", "CONFIRMED"),
        ("CANCELLED", "CANCELLED"),
    ]

    booking_id = models.CharField(max_length=64, unique=True)
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="bookings")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="bookings")
    client_name = models.CharField(max_length=255)
    client_email = models.EmailField()
    location = models.CharField(max_length=255)
    location_preference = models.CharField(max_length=32, blank=True)
    client_address = models.TextField(blank=True)
    desired_date = models.CharField(max_length=128)
    hair_length = models.CharField(max_length=64)
    meche = models.BooleanField()
    current_hair_picture = models.CharField(max_length=255)
    inspiration_pictures = models.JSONField(default=list)
    free_text = models.TextField(blank=True)
    estimated_price_cents = models.IntegerField()
    payment_auth_id = models.CharField(max_length=64)
    status = models.CharField(max_length=64, choices=STATUS_CHOICES)
    proposed_price_cents = models.IntegerField(null=True, blank=True)
    proposed_date = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(null=True, blank=True)
    client_reminder_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.booking_id} - {self.status}"

    @staticmethod
    def _resolve_media_url(path: str | None):
        if not path:
            return None

        parsed = urlparse(path)
        # Already absolute (http, https, etc.) or root-relative URL
        if parsed.scheme or path.startswith("/"):
            return path

        return default_storage.url(path)

    @property
    def resolved_current_hair_picture(self):
        return self._resolve_media_url(self.current_hair_picture)

    @property
    def resolved_inspiration_pictures(self):
        if not self.inspiration_pictures:
            return []

        resolved = []
        for picture in self.inspiration_pictures:
            url = self._resolve_media_url(picture)
            if url:
                resolved.append(url)
        return resolved
