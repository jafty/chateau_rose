from django.db import migrations, models


def backfill_state_entered_at(apps, schema_editor):
    Booking = apps.get_model("booking", "Booking")
    for booking in Booking.objects.all().iterator():
        if booking.status == "AWAITING_ALTERNATIVE_PROVIDER":
            reference = booking.alternative_requested_at or booking.updated_at or booking.created_at
        elif booking.status == "PENDING_CLIENT_VALIDATION":
            reference = booking.updated_at or booking.created_at
        else:
            reference = booking.updated_at or booking.created_at
        booking.state_entered_at = reference
        booking.save(update_fields=["state_entered_at"])


class Migration(migrations.Migration):
    dependencies = [("booking", "0043_alter_verifiedreview_booking_and_more")]

    operations = [
        migrations.AddField(
            model_name="provider",
            name="preferred_contact_method",
            field=models.CharField(
                choices=[
                    ("CHATEAU_ROSE", "Via Château Rose"),
                    ("EMAIL", "Email"),
                    ("PHONE", "Téléphone"),
                    ("WHATSAPP", "WhatsApp"),
                    ("CUSTOM", "Instructions personnalisées"),
                ],
                default="CHATEAU_ROSE",
                help_text="Moyen de contact communiqué à la clientèle uniquement après confirmation.",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="provider",
            name="post_confirmation_contact_instructions",
            field=models.TextField(
                blank=True,
                help_text="Instructions complémentaires communiquées uniquement après confirmation.",
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="state_entered_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Date d'entrée dans le statut courant, utilisée pour calculer son expiration.",
                null=True,
            ),
        ),
        migrations.RunPython(backfill_state_entered_at, migrations.RunPython.noop),
    ]
