from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store_admin", "0016_add_vendoraddress_contact_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="vendorcontact",
            name="is_primary",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="vendorcontact",
            name="mobile_no",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
