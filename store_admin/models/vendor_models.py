from django.contrib import admin

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.forms import DateTimeField

from store_admin.helpers import name_validator, email_validator, mobile_validator
from store_admin.models import PaymentTerm
from store_admin.models.geo_models import Country,State
#from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.address_model import Addresses

class VendorStatus(models.IntegerChoices):
    PENDING = 0, "Pending"
    IN_PROCESS = 1, "In Process"
    ACTIVE = 2, "Active"
    REJECT = 3, "Reject"
    ON_HOLD = 4, "On Hold"

class Vendor(models.Model):
    id = models.AutoField(primary_key=True)
    vendor_code = models.CharField(max_length=50)
    vendor_name = models.CharField(max_length=120)
    gst_number = models.CharField(max_length=50, blank=True, null=True)
    tax_percent = models.DecimalField(decimal_places=2,max_digits=10,default=0.0, null=True)
    min_order_value = models.DecimalField(decimal_places=2,max_digits=10,default=0.0, blank=True, null=True)
    is_taxable = models.IntegerField(blank=True, null=True, default=0)
    default_warehouse = models.IntegerField(default=0, blank=True, null=True)
    payment_term = models.IntegerField(default=0, blank=True, null=True)
    bank_name = models.CharField(max_length=120, blank=True, null=True)
    company_abn = models.CharField(max_length=15, blank=True, null=True)
    company_acn = models.CharField(max_length=15, blank=True, null=True)
    bank_branch = models.CharField(max_length=80, blank=True, null=True)
    account_number = models.CharField(max_length=20, blank=True, null=True)
    reminder = models.TextField(blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    currency = models.CharField(max_length=10, blank=True, null=True)

   # documents = models.FileField(upload_to='imports/vendors/', null=True, blank=True)
    created_by = models.IntegerField(default=0)
    updated_by = models.IntegerField(default=0)
    status = models.IntegerField(
        choices=VendorStatus.choices,
        default=VendorStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    #class Meta:
    #    db_table = "vendor_master"

class VendorDocuments(models.Model):
    file_id = models.AutoField(primary_key=True)
    vendor_id = models.PositiveIntegerField()
    file_path = models.FileField(upload_to="vendor_documents/", null=True, blank=True)
    file_name = models.CharField(max_length=80, blank=True)
    created_by = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "store_admin_vendor_documents"

class VendorBank(models.Model):
    id = models.AutoField(primary_key=True)
    vendor_id = models.PositiveIntegerField()
    account_holder = models.CharField(max_length=255)
    bank_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=255)
    bic = models.CharField(max_length=50)
    created_by = models.PositiveIntegerField(default=0)

    #class Meta:
     #   db_table = "vendor_banks"


class VendorContact(models.Model):
    id = models.AutoField(primary_key=True)
    vendor_id = models.PositiveIntegerField()
    department = models.CharField(max_length=100)
    email = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    first_name = models.CharField(max_length=100, validators=[name_validator], blank=True)
    last_name = models.CharField(max_length=100, validators=[name_validator], blank=True)
    role = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_by = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now=True)

   # class Meta:
    #    db_table = "vendor_contacts"

class VendorAddress(models.Model):
    id = models.AutoField(primary_key=True)
    vendor_id = models.PositiveIntegerField()
    address_type = models.CharField(
        max_length=20,
    )
    address_id = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now=True)
    created_by = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "store_admin_vendoraddress"
        managed = False


class VendorWarehouse(models.Model):
    # IDs kept as integers to avoid formal Foreign Key constraints
    warehouse_id = models.AutoField(primary_key=True)
    vendor_id = models.IntegerField()
    country_id = models.IntegerField(null=True, blank=True)
    state_id = models.IntegerField(null=True, blank=True)

    # UI Fields
    name = models.CharField(max_length=100)  # Warehouse Name
    delivery_name = models.CharField(max_length=100, blank=True)  # Delivery Contact Name
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    zip = models.CharField(max_length=20)
    is_primary = models.BooleanField(default=False)

    # Audit Fields
    created_by = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "store_admin_vendor_warehouses"
    def __str__(self):
        return self.name