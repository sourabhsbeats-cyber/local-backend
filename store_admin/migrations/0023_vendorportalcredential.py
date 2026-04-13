# Generated manually for vendor portal credentials

import django.db.models.deletion
from django.db import migrations, models

import store_admin.models.vendor_models


class Migration(migrations.Migration):

    dependencies = [
        ("store_admin", "0022_alter_vendor_payment_term_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="VendorPortalCredential",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("website_username", models.CharField(max_length=255)),
                ("website_user_email", models.EmailField(max_length=254)),
                (
                    "website_link",
                    models.CharField(
                        max_length=500,
                        validators=[store_admin.models.vendor_models.validate_https_http_url],
                    ),
                ),
                ("password_ciphertext", models.TextField()),
                ("otp_enabled", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_by", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "vendor",
                    models.OneToOneField(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portal_credential",
                        to="store_admin.vendor",
                    ),
                ),
            ],
            options={
                "db_table": "store_admin_vendor_portal_credential",
            },
        ),
    ]
