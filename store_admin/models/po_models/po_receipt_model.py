from django.db import models


class PurchaseReceipt(models.Model):
    po_receipt_id = models.AutoField(primary_key=True)
    po_id = models.IntegerField()
    po_invoice_id = models.IntegerField()
    receipt_total = models.DecimalField(decimal_places=2, max_digits=10)

    po_receive_id = models.IntegerField(null=True, blank=True)
    comments = models.TextField(null=True, blank=True)
    status_id = models.SmallIntegerField(default=1)

    created_by = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.IntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'store_admin_purchase_receipt'


class PurchaseReceiptItem(models.Model):
    po_receipt_item_id = models.AutoField(primary_key=True)
    po_receipt_id = models.IntegerField(null=True, blank=True)
    product_id = models.IntegerField()
    po_invoice_id = models.IntegerField()
    received_date = models.DateField(null=True, blank=True)
    received_qty = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'store_admin_purchase_receipt_items'