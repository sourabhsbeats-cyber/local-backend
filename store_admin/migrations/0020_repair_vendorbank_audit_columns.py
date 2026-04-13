from django.db import migrations


def add_missing_vendorbank_audit_columns(apps, schema_editor):
    connection = schema_editor.connection
    table_name = "store_admin_vendorbank"

    with connection.cursor() as cursor:
        existing_columns = {
            col.name for col in connection.introspection.get_table_description(cursor, table_name)
        }

        if "created_by" not in existing_columns:
            schema_editor.execute(
                "ALTER TABLE store_admin_vendorbank ADD COLUMN created_by int NULL DEFAULT 0"
            )

        if "created_at" not in existing_columns:
            schema_editor.execute(
                "ALTER TABLE store_admin_vendorbank ADD COLUMN created_at datetime NULL"
            )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("store_admin", "0019_repair_vendorbank_columns"),
    ]

    operations = [
        migrations.RunPython(add_missing_vendorbank_audit_columns, migrations.RunPython.noop),
    ]
