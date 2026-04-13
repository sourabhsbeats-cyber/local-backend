from django.db import migrations


def add_missing_vendorbank_columns(apps, schema_editor):
    connection = schema_editor.connection
    table_name = "store_admin_vendorbank"

    with connection.cursor() as cursor:
        existing_columns = {
            col.name for col in connection.introspection.get_table_description(cursor, table_name)
        }

        if "bank_branch" not in existing_columns:
            schema_editor.execute(
                "ALTER TABLE store_admin_vendorbank ADD COLUMN bank_branch varchar(80) NULL"
            )

        if "bank_country" not in existing_columns:
            schema_editor.execute(
                "ALTER TABLE store_admin_vendorbank ADD COLUMN bank_country varchar(100) NULL"
            )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("store_admin", "0018_update_standard_payment_term_names"),
    ]

    operations = [
        migrations.RunPython(add_missing_vendorbank_columns, migrations.RunPython.noop),
    ]
