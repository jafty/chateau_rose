from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0016_provider_pending_reminder_sent_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="client_reminder_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
