from django.db import migrations, models

import interface.validators


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0030_provider_is_visible_on_website"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="providers/services/"),
        ),
        migrations.AddField(
            model_name="service",
            name="image_url",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Upload an image or provide an absolute URL, /root-relative path, "
                    "or relative static asset path."
                ),
                max_length=500,
                validators=[interface.validators.validate_absolute_or_root_relative_url],
            ),
        ),
    ]
