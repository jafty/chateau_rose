from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0013_remove_provider_works_in_salon_only_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="booking",
            old_name="client_phone",
            new_name="client_email",
        ),
    ]
