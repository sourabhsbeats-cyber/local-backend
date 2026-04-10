from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from store_admin.models.vendor_models import Vendor

# -------------------------
# Payment Status Choices
# -------------------------
class PaymentStatus(models.IntegerChoices):
    INITIATED = 1, "Initiated"
    PROCESSING = 2, "Processing"
    COMPLETED = 3, "Completed"
    FAILED = 4, "Failed"
    REVERSED = 5, "Reversed"

# -------------------------
# Vendor Payment Log
# -------------------------
class VendorPaymentLog(models.Model):
    payment_id = models.AutoField(primary_key=True)

    # Temporarily nullable for existing rows; remove null=True after migration/backfill
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name='payments',
        null=True
    )

    payment_mode = models.CharField(max_length=50)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    surcharge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    conversion_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    currency = models.CharField(max_length=10, blank=True, null=True)
    payment_date = models.DateField(db_index=True)
    reference_number = models.CharField(max_length=200, blank=True, null=True)
    bank_name = models.CharField(max_length=200, blank=True, null=True)
    account_number = models.CharField("Bank Account Number", max_length=100, blank=True, null=True)
    card_holder = models.CharField(max_length=200, blank=True, null=True)
    wallet_confirmation = models.CharField(max_length=200, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    status = models.IntegerField(
        choices=PaymentStatus.choices,
        default=PaymentStatus.INITIATED,
        db_index=True
    )

    created_by = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "store_admin_vendor_payment_log"

    def save(self, *args, **kwargs):
        # Automatically calculate total_paid
        self.total_paid = (
            Decimal(self.amount_paid or 0) +
            Decimal(self.surcharge or 0) +
            Decimal(self.conversion_charge or 0)
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)

    def __str__(self):
        vendor_id = self.vendor.id if self.vendor else "None"
        return f"Payment-{self.payment_id} | Vendor-{vendor_id}"


# -------------------------
# Vendor Payment Log Item
# -------------------------
class VendorPaymentLogItem(models.Model):
    item_id = models.AutoField(primary_key=True)

    # Temporarily nullable for existing rows; remove null=True after migration/backfill
    payment = models.ForeignKey(
        VendorPaymentLog,
        on_delete=models.CASCADE,
        related_name='items',
        null=True
    )

    invoice_id = models.IntegerField(db_index=True)  # Replace with ForeignKey if Invoice model exists

    class Meta:
        db_table = "store_admin_vendor_payment_log_items"

    def __str__(self):
        payment_id = self.payment.payment_id if self.payment else "None"
        return f"PaymentItem-{self.item_id} | Payment-{payment_id}"


