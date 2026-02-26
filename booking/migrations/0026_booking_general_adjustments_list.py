from django.db import migrations, models


def forward_copy_general_adjustment(apps, schema_editor):
    Booking = apps.get_model("booking", "Booking")
    for booking in Booking.objects.all().only("id", "general_adjustment"):
        value = (getattr(booking, "general_adjustment", "") or "").strip()
        booking.general_adjustments = [value] if value else []
        booking.save(update_fields=["general_adjustments"])


def backward_copy_general_adjustments(apps, schema_editor):
    Booking = apps.get_model("booking", "Booking")
    for booking in Booking.objects.all().only("id", "general_adjustments"):
        values = getattr(booking, "general_adjustments", None) or []
        booking.general_adjustment = values[0] if values else ""
        booking.save(update_fields=["general_adjustment"])


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0025_provider_deposit_percentage"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="general_adjustments",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(
            forward_copy_general_adjustment,
            reverse_code=backward_copy_general_adjustments,
        ),
        migrations.RemoveField(
            model_name="booking",
            name="general_adjustment",
        ),
    ]
