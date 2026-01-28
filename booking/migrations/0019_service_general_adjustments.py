from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0018_provider_deposit_cents"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="general_adjustments",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
