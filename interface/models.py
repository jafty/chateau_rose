from django.db import models


class MarketingService(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    intro = models.TextField(blank=True)
    highlights = models.JSONField(default=list, blank=True)
    main_image = models.ImageField(upload_to="marketing/services/main/", blank=True, null=True)
    main_image_url = models.URLField(max_length=500, blank=True)
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


class MarketingServiceImage(models.Model):
    service = models.ForeignKey(MarketingService, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="marketing/services/gallery/")
    image_url = models.URLField(max_length=500, blank=True)
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


class MarketingCity(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    intro = models.TextField(blank=True)
    main_image = models.ImageField(upload_to="marketing/cities/main/", blank=True, null=True)
    main_image_url = models.URLField(max_length=500, blank=True)
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


class MarketingDistrict(models.Model):
    city = models.ForeignKey(MarketingCity, on_delete=models.CASCADE, related_name="districts")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    intro = models.TextField(blank=True)
    meta_description = models.TextField(blank=True)

    class Meta:
        ordering = ("name",)
        unique_together = (("city", "slug"), ("city", "name"))

    def __str__(self):
        return f"{self.name} ({self.city})"


class MarketingServiceCity(models.Model):
    service = models.ForeignKey(MarketingService, on_delete=models.CASCADE, related_name="city_overrides")
    city = models.ForeignKey(MarketingCity, on_delete=models.CASCADE, related_name="service_overrides")
    intro = models.TextField(blank=True)
    highlights = models.JSONField(default=list, blank=True)
    main_image = models.ImageField(upload_to="marketing/service_city/main/", blank=True, null=True)
    main_image_url = models.URLField(max_length=500, blank=True)
    meta_description = models.TextField(blank=True)

    class Meta:
        ordering = ("city__name",)
        unique_together = (("service", "city"),)

    def __str__(self):
        return f"{self.service} - {self.city}"

    @property
    def resolved_main_image(self):
        if self.main_image:
            return self.main_image.url
        if self.main_image_url:
            return self.main_image_url
        return None


class MarketingServiceCityImage(models.Model):
    service_city = models.ForeignKey(
        MarketingServiceCity, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="marketing/service_city/gallery/")
    image_url = models.URLField(max_length=500, blank=True)
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return f"Image pour {self.service_city}"

    @property
    def resolved_url(self):
        if self.image:
            return self.image.url
        return self.image_url or None
