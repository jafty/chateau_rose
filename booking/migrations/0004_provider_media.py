import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0003_add_missing_meche_bonus_column"),
    ]

    operations = [
        migrations.AddField(
            model_name="provider",
            name="profile_image",
            field=models.ImageField(blank=True, null=True, upload_to="providers/profile/"),
        ),
        migrations.CreateModel(
            name="ProviderPhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="providers/gallery/")),
                ("caption", models.CharField(blank=True, max_length=255)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "provider",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="photos",
                        to="booking.provider",
                    ),
                ),
            ],
            options={"ordering": ("order", "id")},
        ),
    ]
