from django.db import migrations, models


def ensure_meche_bonus_cents(apps, schema_editor):
    """
    Safety net for deployments where the service table was missing the
    `meche_bonus_cents` column (e.g., migrations not applied). Adds the column
    if it does not exist yet.
    """

    Service = apps.get_model("booking", "Service")

    with schema_editor.connection.cursor() as cursor:
        columns = [
            col.name
            for col in schema_editor.connection.introspection.get_table_description(
                cursor, Service._meta.db_table
            )
        ]

    if "meche_bonus_cents" in columns:
        return

    field = models.IntegerField(default=0)
    field.set_attributes_from_name("meche_bonus_cents")
    schema_editor.add_field(Service, field)


def remove_meche_bonus_cents(apps, schema_editor):
    Service = apps.get_model("booking", "Service")

    with schema_editor.connection.cursor() as cursor:
        columns = [
            col.name
            for col in schema_editor.connection.introspection.get_table_description(
                cursor, Service._meta.db_table
            )
        ]

    if "meche_bonus_cents" not in columns:
        return

    field = Service._meta.get_field("meche_bonus_cents")
    schema_editor.remove_field(Service, field)


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0004_provider_media"),
    ]

    operations = [
        migrations.RunPython(
            ensure_meche_bonus_cents,
            reverse_code=remove_meche_bonus_cents,
        )
    ]
