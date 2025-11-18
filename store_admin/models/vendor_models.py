from django.contrib import admin

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.forms import DateTimeField

from store_admin.models import PaymentTerm
from store_admin.models.geo_models import Country,State
#from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.address_model import Addresses

class Vendor(models.Model):
    id = models.AutoField(primary_key=True)
    salutation = models.CharField(max_length=20, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    display_name = models.CharField(max_length=255, blank=True)
    vendor_code = models.CharField(max_length=50, unique=True)
    email_address = models.CharField(max_length=255, blank=True)
    work_phone = models.CharField(max_length=50, blank=True)
    mobile_number = models.CharField(max_length=50, blank=True)

    registered_business = models.BooleanField(default=False)
    company_abn = models.CharField(max_length=50, blank=True)
    company_acn = models.CharField(max_length=50, blank=True)

    payment_term = models.ForeignKey(
        PaymentTerm, on_delete=models.SET_NULL, null=True
    )

    currency = models.CharField(max_length=10, blank=True)
    documents = models.CharField(max_length=255, blank=True)
    vendor_remarks = models.TextField(blank=True)

    created_by = models.IntegerField(default=0)
    updated_by = models.IntegerField(default=0)
    status = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    #class Meta:
    #    db_table = "vendor_master"


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
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    created_by = models.PositiveIntegerField(default=0)
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

