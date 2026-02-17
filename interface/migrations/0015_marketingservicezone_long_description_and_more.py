from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("interface", "0014_marketingservice_long_description_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="marketingservicezone",
            name="long_description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="marketingservicezone",
            name="long_title",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="marketingservicezone",
            name="short_intro",
            field=models.TextField(blank=True),
        ),
    ]
