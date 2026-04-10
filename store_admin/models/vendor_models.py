from django.db import models
from store_admin.helpers import name_validator
from django.utils import timezone

# -------------------------
# Vendor Status Choices
# -------------------------
class VendorStatus(models.IntegerChoices):
    PENDING = 0, "Pending"
    IN_PROCESS = 1, "In Process"
    ACTIVE = 2, "Active"
    REJECT = 3, "Reject"
    ON_HOLD = 4, "On Hold"

# -------------------------
# Payment Terms Choices
# -------------------------
class PaymentTerms(models.IntegerChoices):
    LAST_NEXT_NEXT_MONTH = 1, "Last date of next to next month (Forcetech)"
    LAST_NEXT_MONTH = 2, "Last date of next month (Bambury)"
    FOURTEENTH_NEXT_MONTH = 3, "14th of next month (Ingram)"
    NET_45 = 4, "Net 45 Days"
    NET_60 = 5, "Net 60 Days"

# -------------------------
# Vendor Model
# -------------------------
class Vendor(models.Model):
    id = models.AutoField(primary_key=True)
    vendor_code = models.CharField(max_length=50, unique=True)
    vendor_company_name = models.CharField(max_length=120)
    vendor_name = models.CharField(max_length=120)
    gst_number = models.CharField(max_length=50, blank=True, null=True)
    tax_percent = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    is_taxable = models.BooleanField(default=False)

    company_acc_no = models.CharField(max_length=50, blank=True, null=True)
    company_website = models.CharField(max_length=255, blank=True, null=True)
    company_abn = models.CharField(max_length=15, blank=True, null=True)
    company_acn = models.CharField(max_length=15, blank=True, null=True)
    company_locality = models.CharField(max_length=120, blank=True, null=True)
    
    # Payment terms
    payment_term = models.IntegerField(choices=PaymentTerms.choices, default=PaymentTerms.LAST_NEXT_MONTH)

    # Payment notes
    wallet_notes = models.TextField(blank=True, null=True)
    credit_card_notes = models.TextField(blank=True, null=True)
    paypal_notes = models.TextField(blank=True, null=True)

    # Payment gateway & card/paypal info
    accepted_card = models.CharField(max_length=50, blank=True, null=True)
    payment_gateway = models.CharField(max_length=100, blank=True, null=True)
    processing_fee = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    three_d_secure = models.CharField(max_length=10, default="no")
    cardholder_name = models.CharField(max_length=100, blank=True, null=True)
    card_type = models.CharField(max_length=20, blank=True, null=True)
    card_last_four = models.CharField(max_length=4, blank=True, null=True)
    card_expiry = models.CharField(max_length=7, blank=True, null=True)
    paypal_email = models.EmailField(max_length=254, blank=True, null=True)
    paypal_merchant_id = models.CharField(max_length=50, blank=True, null=True)
    paypal_environment = models.CharField(max_length=20, default="sandbox")
    paypal_transaction_fee = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    # Vendor preferences
    preferred_shipping_provider = models.IntegerField(blank=True, null=True)
    vendor_locality = models.CharField(max_length=120, blank=True, null=True)
    currency = models.CharField(max_length=10, blank=True, null=True)
    auto_detect_invoice = models.CharField(max_length=10, default="no")
    allow_negative_balance = models.CharField(max_length=10, default="no")
    minimum_wallet_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    low_balance_email = models.EmailField(blank=True, null=True)
    wallet_type = models.CharField(max_length=100, blank=True, null=True)

    # Status & audit
    status = models.IntegerField(choices=VendorStatus.choices, default=VendorStatus.PENDING)
    created_by = models.IntegerField(default=0)
    updated_by = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.vendor_code} - {self.vendor_company_name}"

# -------------------------
# Vendor Bank Details
# -------------------------
class VendorBank(models.Model):
    id = models.AutoField(primary_key=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='banks', null=True)
    account_holder = models.CharField(max_length=255, default="Unknown")
    bank_name = models.CharField(max_length=255, default="Unknown")
    account_number = models.CharField(max_length=50, default="Unknown",
    verbose_name="Bank Account Number")
    bic = models.CharField(max_length=50, default="Unknown")
    bank_branch = models.CharField(max_length=80, blank=True, null=True)
    bank_country = models.CharField(max_length=100, blank=True, null=True)
    created_by = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

# -------------------------
# Vendor Documents
# -------------------------
class VendorDocuments(models.Model):
    file_id = models.AutoField(primary_key=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='documents', null=True)
    file_path = models.FileField(upload_to="vendor_documents/", null=True, blank=True)
    file_name = models.CharField(max_length=80, blank=True, default="Unknown")
    created_by = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "store_admin_vendor_documents"

# -------------------------
# Vendor Contact Details
# -------------------------
class VendorContact(models.Model):
    id = models.AutoField(primary_key=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='contacts', null=True)
    department = models.CharField(max_length=100, default="Unknown")
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    first_name = models.CharField(max_length=100, validators=[name_validator], blank=True, default="Unknown")
    last_name = models.CharField(max_length=100, validators=[name_validator], blank=True, default="Unknown")
    role = models.CharField(max_length=100, default="Unknown")
    description = models.TextField(blank=True, null=True)
    created_by = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

# -------------------------
# Vendor Address
# -------------------------
class VendorAddress(models.Model):
    id = models.AutoField(primary_key=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='addresses', null=True)
    address_type = models.CharField(max_length=20, default="Unknown")
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    suburb = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    post_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    created_by = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

# -------------------------
# Vendor Warehouse
# -------------------------
class VendorWarehouse(models.Model):
    warehouse_id = models.AutoField(primary_key=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='warehouses', null=True)
    country_id = models.IntegerField(null=True, blank=True)
    state_id = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=100, default="Unknown")
    delivery_name = models.CharField(max_length=100, blank=True, default="Unknown")
    address_line1 = models.CharField(max_length=255, default="Unknown")
    address_line2 = models.CharField(max_length=255, blank=True, default="Unknown")
    city = models.CharField(max_length=100, default="Unknown")
    zip = models.CharField(max_length=20, default="000000")
    is_primary = models.BooleanField(default=False)
    created_by = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "store_admin_vendor_warehouses"

    def __str__(self):
        return self.name