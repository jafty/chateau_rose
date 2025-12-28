from django.db import migrations


def forwards(apps, schema_editor):
    Service = apps.get_model("booking", "Service")
    ProviderMarketingService = apps.get_model("booking", "ProviderMarketingService")
    MarketingService = apps.get_model("interface", "MarketingService")

    marketing_by_slug = {ms.slug: ms.id for ms in MarketingService.objects.all()}

    rows = set()
    services = Service.objects.exclude(slug="").values_list("provider_id", "slug")
    for provider_id, service_slug in services:
        marketing_id = marketing_by_slug.get(service_slug)
        if not marketing_id:
            continue
        key = (provider_id, marketing_id)
        if key in rows:
            continue
        rows.add(key)
        ProviderMarketingService.objects.get_or_create(
            provider_id=provider_id, service_id=marketing_id
        )


def backwards(apps, schema_editor):
    ProviderMarketingService = apps.get_model("booking", "ProviderMarketingService")
    Service = apps.get_model("booking", "Service")
    MarketingService = apps.get_model("interface", "MarketingService")

    marketing_by_slug = {ms.slug: ms.id for ms in MarketingService.objects.all()}
    services = Service.objects.exclude(slug="").values_list("provider_id", "slug")
    pairs = set()
    for provider_id, service_slug in services:
        marketing_id = marketing_by_slug.get(service_slug)
        if not marketing_id:
            continue
        pairs.add((provider_id, marketing_id))

    if pairs:
        for provider_id, marketing_id in pairs:
            ProviderMarketingService.objects.filter(
                provider_id=provider_id, service_id=marketing_id
            ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0007_provider_zones_providermarketingservice_and_more"),
        ("interface", "0003_alter_marketingcity_main_image_url_and_more"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
