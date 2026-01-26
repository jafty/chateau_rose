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


class MarketingService(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    intro = models.TextField(blank=True)
    highlights = models.JSONField(default=list, blank=True)
    main_image = models.ImageField(upload_to="marketing/services/main/", blank=True, null=True)
    main_image_url = models.CharField(
        max_length=500,
        blank=True,
        validators=[validate_absolute_or_root_relative_url],
        help_text=(
            "Upload an image or provide an absolute URL, /root-relative path, "
            "or relative static asset path."
        ),
    )
    meta_description = models.TextField(blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

    @property
    def resolved_main_image(self):
        if self.main_image:
            return self.main_image.url
        if self.main_image_url:
            return self.main_image_url
        return None

    def save(self, *args, **kwargs):
        if _should_compress_image(self, "main_image"):
            compress_image_field(self.main_image, max_px=1200, quality=80)
        return super().save(*args, **kwargs)


class MarketingZone(models.Model):
    zone = models.OneToOneField(
        "booking.Zone",
        on_delete=models.CASCADE,
        related_name="marketing_profile",
    )
    intro = models.TextField(blank=True)
    highlights = models.JSONField(default=list, blank=True)
    hero_image = models.ImageField(upload_to="marketing/zones/main/", blank=True, null=True)
    hero_image_url = models.CharField(
        max_length=500,
        blank=True,
        validators=[validate_absolute_or_root_relative_url],
        help_text=(
            "Upload an image or provide an absolute URL, /root-relative path, "
            "or relative static asset path."
        ),
    )
    meta_description = models.TextField(blank=True)

    class Meta:
        ordering = ("zone__name",)

    def __str__(self):
        return f"Profil marketing - {self.zone.name}"

    @property
    def resolved_hero_image(self):
        if self.hero_image:
            return self.hero_image.url
        if self.hero_image_url:
            return self.hero_image_url
        return None


class MarketingServiceImage(models.Model):
    service = models.ForeignKey(MarketingService, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="marketing/services/gallery/", blank=True)
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

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return f"Image pour {self.service}"

    @property
    def resolved_url(self):
        if self.image:
            return self.image.url
        return self.image_url or None

    def save(self, *args, **kwargs):
        if _should_compress_image(self, "image"):
            compress_image_field(self.image, max_px=800, quality=80)
        return super().save(*args, **kwargs)


class ServiceRequest(models.Model):
    LOCATION_PREFERENCE_CLIENT_HOME = "client_home"
    LOCATION_PREFERENCE_SALON = "salon"
    LOCATION_PREFERENCE_CHOICES = (
        (LOCATION_PREFERENCE_CLIENT_HOME, "À domicile"),
        (LOCATION_PREFERENCE_SALON, "En salon / chez la prestataire ou le prestataire"),
    )

    marketing_service = models.ForeignKey(
        MarketingService,
        on_delete=models.CASCADE,
        related_name="service_requests",
    )
    zone = models.ForeignKey(
        "booking.Zone",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_requests",
    )
    location_preference = models.CharField(
        max_length=32,
        choices=LOCATION_PREFERENCE_CHOICES,
        default=LOCATION_PREFERENCE_CLIENT_HOME,
    )
    client_name = models.CharField(max_length=255)
    client_email = models.EmailField()
    client_address = models.TextField(blank=True)
    desired_date = models.DateTimeField()
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Demande {self.marketing_service.name} ({self.client_name})"
