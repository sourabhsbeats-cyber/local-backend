from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store_admin", "0015_add_vendoraddress_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="vendoraddress",
            name="attention",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="vendoraddress",
            name="phone",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="vendoraddress",
            name="fax",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
