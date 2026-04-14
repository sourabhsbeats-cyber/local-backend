from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store_admin', '0023_vendorportalcredential'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentterm',
            name='term_option',
            field=models.CharField(
                choices=[
                    ('frequency', 'Frequency'),
                    ('nextMonth14', '14th of Next Month'),
                    ('nextMonthLastDay', 'Last day of Next Month'),
                    ('nextNextMonthLastDay', 'Last day of Next to Next Month'),
                ],
                default='frequency',
                max_length=32,
            ),
        ),
    ]
