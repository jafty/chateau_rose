from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0017_booking_client_reminder_sent_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="provider",
            name="deposit_cents",
            field=models.IntegerField(default=2000, help_text="Montant fixe de l'acompte en centimes."),
        ),
    ]
