from django.db import migrations, models


def ensure_meche_bonus(apps, schema_editor):
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


def remove_meche_bonus(apps, schema_editor):
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
        ("booking", "0005_ensure_meche_bonus_cents"),
    ]

    operations = [
        migrations.RunPython(ensure_meche_bonus, reverse_code=remove_meche_bonus),
    ]
