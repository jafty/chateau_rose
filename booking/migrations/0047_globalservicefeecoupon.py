from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0046_booking_type_adjustment_service_type_adjustments"),
    ]

    operations = [
        migrations.CreateModel(
            name="GlobalServiceFeeCoupon",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.CharField(max_length=64, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "code promo global",
                "verbose_name_plural": "codes promo globaux",
            },
        ),
    ]
