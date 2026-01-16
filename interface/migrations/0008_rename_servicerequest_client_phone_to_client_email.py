from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("interface", "0007_servicerequest_location_preference"),
    ]

    operations = [
        migrations.RenameField(
            model_name="servicerequest",
            old_name="client_phone",
            new_name="client_email",
        ),
    ]
