from django.db import models
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from store_admin.helpers import name_validator
from django.utils import timezone


def validate_https_http_url(value):
    if value is None or str(value).strip() == "":
        return
    URLValidator(schemes=("http", "https"))(value)

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
    LAST_NEXT_NEXT_MONTH = 1, "Last day of Next to Next Month"
    LAST_NEXT_MONTH = 2, "Last day of Next Month"
    FOURTEENTH_NEXT_MONTH = 3, "14th of Next Month"
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
    is_primary = models.BooleanField(default=False)
    department = models.CharField(max_length=100, default="Unknown")
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    mobile_no = models.CharField(max_length=50, blank=True, null=True)
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
    attention = models.CharField(max_length=255, blank=True, null=True)
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    suburb = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    post_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    fax = models.CharField(max_length=50, blank=True, null=True)
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


# -------------------------
# Vendor inventory — master dropdown options
# -------------------------
class VendorInventoryListType(models.TextChoices):
    INVENTORY_FREQUENCY = "inventory_frequency", "Inventory Frequency"
    INVENTORY_SOURCE = "inventory_source", "Inventory Source"
    PRODUCT_INVENTORY_SYNC = "product_inventory_sync", "Product Inventory Sync"
    INVOICE_RECEIVED_ON = "invoice_received_on", "Invoice Received On"
    TRACKING_RECEIVED_ON = "tracking_received_on", "Tracking Received On"
    PO_INTEGRATION_TYPE = "po_integration_type", "PO Integration Type"


class VendorInventoryMasterOption(models.Model):
    id = models.AutoField(primary_key=True)
    list_type = models.CharField(max_length=64, choices=VendorInventoryListType.choices, db_index=True)
    code = models.SlugField(max_length=64)
    label = models.CharField(max_length=120)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "store_admin_vendor_inventory_master_option"
        unique_together = [["list_type", "code"]]
        ordering = ["list_type", "sort_order", "label"]

    def __str__(self):
        return f"{self.list_type}:{self.code}"


# -------------------------
# Vendor inventory rows (per vendor, multiple entries)
# -------------------------
class VendorInventory(models.Model):
    id = models.AutoField(primary_key=True)
    # db_constraint=False: some MySQL schemas use a vendor id type that does not match Django’s FK column (3780).
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name="inventory_rows",
        db_constraint=False,
    )
    inventory_frequency = models.ForeignKey(
        VendorInventoryMasterOption,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    inventory_source = models.ForeignKey(
        VendorInventoryMasterOption,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    product_inventory_sync = models.ForeignKey(
        VendorInventoryMasterOption,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    invoice_received_on = models.ForeignKey(
        VendorInventoryMasterOption,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    tracking_received_on = models.ForeignKey(
        VendorInventoryMasterOption,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    po_integration_type = models.ForeignKey(
        VendorInventoryMasterOption,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    integration_weblink = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        validators=[validate_https_http_url],
        help_text="HTTPS/HTTP URL only; used for portal or feed links.",
    )
    created_by = models.PositiveIntegerField(default=0)
    updated_by = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "store_admin_vendor_inventory"
        ordering = ["-id"]

    def clean(self):
        super().clean()
        checks = [
            ("inventory_frequency", self.inventory_frequency, VendorInventoryListType.INVENTORY_FREQUENCY),
            ("inventory_source", self.inventory_source, VendorInventoryListType.INVENTORY_SOURCE),
            ("product_inventory_sync", self.product_inventory_sync, VendorInventoryListType.PRODUCT_INVENTORY_SYNC),
            ("invoice_received_on", self.invoice_received_on, VendorInventoryListType.INVOICE_RECEIVED_ON),
            ("tracking_received_on", self.tracking_received_on, VendorInventoryListType.TRACKING_RECEIVED_ON),
            ("po_integration_type", self.po_integration_type, VendorInventoryListType.PO_INTEGRATION_TYPE),
        ]
        for field_name, opt, expected in checks:
            if opt and opt.list_type != expected:
                raise ValidationError({field_name: "Selected value is not valid for this master list."})


# -------------------------
# Vendor website portal login (Super Admin only; password stored encrypted)
# -------------------------
class VendorPortalCredential(models.Model):
    id = models.AutoField(primary_key=True)
    vendor = models.OneToOneField(
        Vendor,
        on_delete=models.CASCADE,
        related_name="portal_credential",
        db_constraint=False,
    )
    website_username = models.CharField(max_length=255)
    website_user_email = models.EmailField(max_length=254)
    website_link = models.CharField(
        max_length=500,
        validators=[validate_https_http_url],
    )
    password_ciphertext = models.TextField()
    otp_enabled = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    updated_by = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "store_admin_vendor_portal_credential"

    def __str__(self):
        return f"Portal credential for vendor_id={self.vendor_id}"