from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("interface", "0029_alter_providerbookingdraft_provider")]

    operations = [
        migrations.AddField(
            model_name="providerbookingdraft",
            name="follow_up_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
