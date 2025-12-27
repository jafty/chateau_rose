from django.db import models


class MarketingService(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    intro = models.TextField(blank=True)
    highlights = models.JSONField(default=list, blank=True)
    main_image = models.ImageField(upload_to="marketing/services/main/", blank=True, null=True)
    meta_description = models.TextField(blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class MarketingServiceImage(models.Model):
    service = models.ForeignKey(MarketingService, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="marketing/services/gallery/")
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return f"Image pour {self.service}"


class MarketingCity(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    intro = models.TextField(blank=True)
    main_image = models.ImageField(upload_to="marketing/cities/main/", blank=True, null=True)
    meta_description = models.TextField(blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


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
    meta_description = models.TextField(blank=True)

    class Meta:
        ordering = ("city__name",)
        unique_together = (("service", "city"),)

    def __str__(self):
        return f"{self.service} - {self.city}"


class MarketingServiceCityImage(models.Model):
    service_city = models.ForeignKey(
        MarketingServiceCity, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="marketing/service_city/gallery/")
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return f"Image pour {self.service_city}"
