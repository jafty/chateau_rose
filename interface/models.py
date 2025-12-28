from django.db import models

from interface.validators import validate_absolute_or_root_relative_url


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
        help_text="Upload an image or provide an absolute URL or /root-relative path.",
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
        help_text="Upload an image or provide an absolute URL or /root-relative path.",
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
        help_text="Upload an image or provide an absolute URL or /root-relative path.",
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


class ServiceRequest(models.Model):
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
    client_name = models.CharField(max_length=255)
    client_phone = models.CharField(max_length=64)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Demande {self.marketing_service.name} ({self.client_name})"
