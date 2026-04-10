from decimal import Decimal
from django.db import models
from django.utils import timezone

from store_admin.vendor_models import VendorPaymentLog, VendorPaymentLogItem  # If needed
from store_admin.purchase_models import POStatus, POPaymentStatus  # Import enums


class Invoice(models.Model):
    invoice_id = models.AutoField(primary_key=True)
    purchase_order_id = models.IntegerField(db_index=True)
    vendor_id = models.IntegerField(db_index=True)
    
    invoice_number = models.CharField(max_length=100, unique=True)
    invoice_date = models.DateField(default=timezone.now)
    due_date = models.DateField(blank=True, null=True)
    
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    status = models.IntegerField(
        choices=POPaymentStatus.choices,
        default=POPaymentStatus.UNPAID,
        db_index=True
    )
    
    created_by = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "store_admin_invoice"

    def __str__(self):
        return f"Invoice-{self.invoice_number} | Vendor-{self.vendor_id}"


class InvoiceItem(models.Model):
    item_id = models.AutoField(primary_key=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    product_id = models.IntegerField(db_index=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = "store_admin_invoice_item"

    def save(self, *args, **kwargs):
        # Auto calculate total price
        self.total_price = (self.quantity * self.unit_price).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"InvoiceItem-{self.item_id} | Invoice-{self.invoice.invoice_number}"


class InvoicePayment(models.Model):
    payment_id = models.AutoField(primary_key=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    
    payment_date = models.DateField(default=timezone.now)
    payment_mode = models.CharField(max_length=50, default="Unknown")
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    reference_number = models.CharField(max_length=200, blank=True, null=True)
    bank_name = models.CharField(max_length=200, blank=True, null=True)
    card_holder = models.CharField(max_length=200, blank=True, null=True)
    
    status = models.IntegerField(
        choices=POPaymentStatus.choices,
        default=POPaymentStatus.UNPAID,
        db_index=True
    )
    
    created_by = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "store_admin_invoice_payment"

    def __str__(self):
        return f"InvoicePayment-{self.payment_id} | Invoice-{self.invoice.invoice_number}"