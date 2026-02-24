from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("interface", "0018_remove_quickcheckoutpage_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="quickcheckoutpage",
            name="final_price_cents",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Prix final convenu avec la/le prestataire (en centimes).",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="quickcheckoutpage",
            name="reservation_fee_cents",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Frais de réservation payés en ligne (en centimes, déduits du prix final).",
            ),
            preserve_default=False,
        ),
        migrations.RunSQL(
            sql=(
                "UPDATE interface_quickcheckoutpage "
                "SET final_price_cents = fixed_price_cents, "
                "reservation_fee_cents = fixed_price_cents"
            ),
            reverse_sql=(
                "UPDATE interface_quickcheckoutpage "
                "SET fixed_price_cents = reservation_fee_cents"
            ),
        ),
        migrations.AlterField(
            model_name="quickcheckoutpage",
            name="hair_length",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.RemoveField(
            model_name="quickcheckoutpage",
            name="fixed_price_cents",
        ),
        migrations.RemoveField(
            model_name="quickcheckoutpage",
            name="general_adjustment",
        ),
        migrations.RemoveField(
            model_name="quickcheckoutpage",
            name="location",
        ),
        migrations.RemoveField(
            model_name="quickcheckoutpage",
            name="meche",
        ),
    ]
