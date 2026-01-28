from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0019_service_general_adjustments"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="general_adjustment",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
