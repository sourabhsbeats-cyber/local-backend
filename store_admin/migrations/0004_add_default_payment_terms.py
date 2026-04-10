from django.db import migrations

def add_default_payment_terms(apps, schema_editor):
    PaymentTerm = apps.get_model('store_admin', 'PaymentTerm')
    terms = [
        {'name': 'Last date of next to next month (Forcetech)', 'frequency': 60, 'type': 2},
        {'name': 'Last date of next month (Bambury)', 'frequency': 30, 'type': 2},
        {'name': '14th of next month (Ingram)', 'frequency': 30, 'type': 2},
    ]
    for term in terms:
        PaymentTerm.objects.get_or_create(name=term['name'], defaults=term)

class Migration(migrations.Migration):

    dependencies = [
        ('store_admin', '0003_alter_vendoraddress_table'),
    ]

    operations = [
        migrations.RunPython(add_default_payment_terms),
    ]