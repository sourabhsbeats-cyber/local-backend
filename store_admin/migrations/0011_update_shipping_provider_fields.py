from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store_admin', '0010_add_vendor_payment_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='shippingproviders',
            name='carrier_code',
            field=models.CharField(max_length=100, db_index=True),
        ),
        migrations.AlterField(
            model_name='shippingproviders',
            name='class_code',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='shippingproviders',
            name='tracking_url',
            field=models.URLField(blank=True, max_length=2000, null=True),
        ),
    ]
