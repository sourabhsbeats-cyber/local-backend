from django.db import models

# Optional reference tables
class Brand(models.Model):
    brand_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=120)
    status = models.PositiveIntegerField(default=0)
    created_at = models.PositiveIntegerField()
    created_by = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'store_admin_brand'  # ✅ use your actual SQL table
        managed = False

    def __str__(self):
        return self.name


class Category(models.Model):
    category_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=120)

    is_primary = models.PositiveIntegerField(default=0)
    primary_category_id = models.PositiveIntegerField(default=None,null=True)

    status = models.PositiveIntegerField(default=0)
    created_at = models.PositiveIntegerField()
    created_by = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'store_admin_category'  # ✅ use your actual SQL table
        managed = False

    def __str__(self):
        return self.name


class Manufacturer(models.Model):
    manufacturer_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=120)
    status = models.PositiveIntegerField(default=0)
    created_at = models.PositiveIntegerField()
    created_by = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'store_admin_manufacturer'  # ✅ use your actual SQL table
        managed = False

    def __str__(self):
        return self.name


class UnitOfMeasurements(models.Model):
    measurement_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=120)
    short_name = models.CharField(max_length=10)
    status = models.PositiveIntegerField(default=0)
    created_at = models.PositiveIntegerField()
    created_by = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'store_admin_unit_of_measurements'  #  use your actual SQL table
        managed = False

    def __str__(self):
        return self.name


class AttributeDefinition(models.Model):
    attribute_id = models.AutoField(primary_key=True)
    attribute_name = models.CharField(
        max_length=150,
        unique=True,
        null=False
    )
    class AttributeType(models.TextChoices):
        TEXT = 'TEXT', 'Text'
        DROPDOWN = 'DROPDOWN', 'Dropdown'

    attribute_type = models.CharField(
        max_length=8,  # Max length of 'DROPDOWN'
        choices=AttributeType.choices,
        default=AttributeType.TEXT,
        null=False
    )

    default_value = models.CharField(
        max_length=255,
        null=True,  # Allows NULL in the database
        blank=True,  # Allows the field to be blank in forms/admin
        default=None  # Explicitly set default to None for NULL
    )
    option_list = models.TextField(
        null=True,
        blank=True,
        default=None
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    created_by = models.IntegerField(
        null=False
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'store_admin_attribute_definition'
        verbose_name = 'Store Admin Attribute Definition'
        verbose_name_plural = 'Store Admin Attribute Definitions'

    def __str__(self):
        return self.attribute_name


from django.db import models
from django.utils import timezone


class ShippingProviders(models.Model):
    carrier_id = models.AutoField(primary_key=True)
    carrier_name = models.CharField(max_length=255)
    carrier_code = models.CharField(max_length=100, db_index=True)
    class_code = models.CharField(max_length=100, blank=True, null=True)
    tracking_url = models.URLField(max_length=2000, blank=True, null=True)

    # Status field (typically an Integer or Char with choices)
    STATUS_CHOICES = [
        (1, 'Active'),
        (0, 'Inactive'),
    ]
    status = models.IntegerField(choices=STATUS_CHOICES, default=1)
    is_archived = models.IntegerField(choices=STATUS_CHOICES, default=0)

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.IntegerField()  # Or ForeignKey(User) if you have an auth system

    class Meta:
        db_table = 'store_admin_shipping_providers'
        verbose_name = 'Shipping Providers'

    def __str__(self):
        return f"{self.carrier_name} ({self.carrier_code})"