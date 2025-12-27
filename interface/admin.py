from django.contrib import admin

from interface.models import (
    MarketingCity,
    MarketingDistrict,
    MarketingService,
    MarketingServiceCity,
    MarketingServiceCityImage,
    MarketingServiceImage,
)


class MarketingServiceImageInline(admin.TabularInline):
    model = MarketingServiceImage
    extra = 1


@admin.register(MarketingService)
class MarketingServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MarketingServiceImageInline]


@admin.register(MarketingCity)
class MarketingCityAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(MarketingDistrict)
class MarketingDistrictAdmin(admin.ModelAdmin):
    list_display = ("name", "city")
    search_fields = ("name", "slug", "city__name")
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ("city",)


class MarketingServiceCityImageInline(admin.TabularInline):
    model = MarketingServiceCityImage
    extra = 1


@admin.register(MarketingServiceCity)
class MarketingServiceCityAdmin(admin.ModelAdmin):
    list_display = ("service", "city")
    search_fields = ("service__name", "city__name")
    list_filter = ("city", "service")
    inlines = [MarketingServiceCityImageInline]
