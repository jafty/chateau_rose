from django.contrib import admin

from interface.models import MarketingService, MarketingServiceImage


class MarketingServiceImageInline(admin.TabularInline):
    model = MarketingServiceImage
    extra = 1


@admin.register(MarketingService)
class MarketingServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MarketingServiceImageInline]
