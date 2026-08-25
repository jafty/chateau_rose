from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("booking", "0047_globalservicefeecoupon")]

    operations = [
        migrations.AlterField(
            model_name="bookingoffer",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING_CLIENT", "PENDING_CLIENT"),
                    ("ACCEPTED", "ACCEPTED"),
                    ("REJECTED", "REJECTED"),
                    ("EXPIRED", "EXPIRED"),
                    ("DIRECTLY_ACCEPTED", "DIRECTLY_ACCEPTED"),
                ],
                default="PENDING_CLIENT",
                max_length=24,
            ),
        ),
    ]
