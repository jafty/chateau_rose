from django.db import migrations, models


def add_meche_bonus(apps, schema_editor):
    Service = apps.get_model("booking", "Service")
    # Check if column exists
    with schema_editor.connection.cursor() as cursor:
        columns = [col.name for col in schema_editor.connection.introspection.get_table_description(cursor, Service._meta.db_table)]
    if "meche_bonus_cents" in columns:
        return
    field = models.IntegerField(default=0)
    field.set_attributes_from_name("meche_bonus_cents")
    schema_editor.add_field(Service, field)


def remove_meche_bonus(apps, schema_editor):
    Service = apps.get_model("booking", "Service")
    with schema_editor.connection.cursor() as cursor:
        columns = [col.name for col in schema_editor.connection.introspection.get_table_description(cursor, Service._meta.db_table)]
    if "meche_bonus_cents" not in columns:
        return
    field = Service._meta.get_field("meche_bonus_cents")
    schema_editor.remove_field(Service, field)


class Migration(migrations.Migration):

    dependencies = [
        (
            "booking",
            "0002_alter_service_unique_together_service_slug_zone_slug_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(add_meche_bonus, reverse_code=remove_meche_bonus),
    ]
