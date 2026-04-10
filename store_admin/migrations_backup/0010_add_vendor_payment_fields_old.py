from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('store_admin', '000Y_previous_migration'),  # replace with the last migration file
    ]

    operations = [
        migrations.AddField(
            model_name='vendor',
            name='card_type',
            field=models.CharField(max_length=20, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vendor',
            name='cardholder_name',
            field=models.CharField(max_length=100, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vendor',
            name='card_last_four',
            field=models.CharField(max_length=4, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vendor',
            name='card_expiry',
            field=models.CharField(max_length=7, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vendor',
            name='paypal_email',
            field=models.EmailField(max_length=254, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vendor',
            name='paypal_merchant_id',
            field=models.CharField(max_length=50, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vendor',
            name='paypal_environment',
            field=models.CharField(max_length=20, default='sandbox'),
        ),
        migrations.AddField(
            model_name='vendor',
            name='paypal_transaction_fee',
            field=models.DecimalField(max_digits=5, decimal_places=2, default=0.00),
        ),
        migrations.AddField(
            model_name='vendor',
            name='wallet_type',
            field=models.CharField(max_length=100, blank=True, null=True),
        ),
    ]