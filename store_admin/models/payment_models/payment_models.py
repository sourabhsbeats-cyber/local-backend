from decimal import Decimal, ROUND_HALF_UP
from django.db import models


class PaymentStatus(models.IntegerChoices):
    INITIATED  = 1, "Initiated"
    PROCESSING = 2, "Processing"
    COMPLETED  = 3, "Completed"
    FAILED     = 4, "Failed"
    REVERSED   = 5, "Reversed"


class VendorPaymentLog(models.Model):
    payment_id          = models.AutoField(primary_key=True)
    vendor_id           = models.IntegerField(db_index=True)
    payment_mode        = models.CharField(max_length=50)
    amount_paid         = models.DecimalField(max_digits=12, decimal_places=2)
    surcharge           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    conversion_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    currency            = models.CharField(max_length=10, blank=True, null=True)
    payment_date        = models.DateField(db_index=True)
    reference_number    = models.CharField(max_length=200, blank=True, null=True)
    bank_name           = models.CharField(max_length=200, blank=True, null=True)
    account_number      = models.CharField(max_length=100, blank=True, null=True)
    card_holder         = models.CharField(max_length=200, blank=True, null=True)
    wallet_confirmation = models.CharField(max_length=200, blank=True, null=True)
    notes               = models.TextField(blank=True, null=True)
    status              = models.IntegerField(
        choices=PaymentStatus.choices,
        default=PaymentStatus.INITIATED,
        db_index=True
    )
    created_by          = models.IntegerField(blank=True, null=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "store_admin_vendor_payment_log"

    def __str__(self):
        return f"Payment-{self.payment_id} | Vendor-{self.vendor_id}"


class VendorPaymentLogItem(models.Model):
    item_id    = models.AutoField(primary_key=True)
    payment_id = models.IntegerField(db_index=True)
    invoice_id = models.IntegerField(db_index=True)

    class Meta:
        db_table = "store_admin_vendor_payment_log_items"

    def __str__(self):
        return f"PaymentItem-{self.item_id} | Payment-{self.payment_id}"