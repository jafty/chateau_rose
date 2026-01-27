from django.db import migrations, models
import django.db.models.deletion

import interface.validators

class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0018_provider_deposit_cents"),
        ("interface", "0009_servicerequest_client_address_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketingServiceZone",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("intro", models.TextField(blank=True)),
                ("highlights", models.JSONField(blank=True, default=list)),
                ("hero_image", models.ImageField(blank=True, null=True, upload_to="marketing/service_zones/main/")),
                ("hero_image_url", models.CharField(blank=True, help_text="Upload an image or provide an absolute URL, /root-relative path, or relative static asset path.", max_length=500, validators=[interface.validators.validate_absolute_or_root_relative_url])),
                ("meta_description", models.TextField(blank=True)),
                ("service", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="zone_overrides", to="interface.marketingservice")),
                ("zone", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="service_overrides", to="booking.zone")),
            ],
            options={
                "ordering": ("service__name", "zone__name"),
            },
        ),
        migrations.AddConstraint(
            model_name="marketingservicezone",
            constraint=models.UniqueConstraint(fields=("service", "zone"), name="unique_marketing_service_zone"),
        ),
    ]
