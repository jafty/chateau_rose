from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0019_service_general_adjustments"),
    ]

    operations = [
        migrations.AddField(
            model_name="provider",
            name="provides_meche",
            field=models.BooleanField(default=True, help_text="Active si la prestataire fournit les mèches."),
        ),
    ]
