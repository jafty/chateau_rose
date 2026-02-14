from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0024_providerphoto_media_kind_providerphoto_video_and_more"),
        ("booking", "0024_service_at_home_bonus_cents"),
    ]

    operations = [
        migrations.AddField(
            model_name="provider",
            name="deposit_percentage",
            field=models.PositiveSmallIntegerField(
                default=30,
                help_text="Pourcentage de l'estimation utilisé pour calculer l'acompte.",
            ),
        ),
    ]
