from decimal import Decimal, ROUND_HALF_UP

from django.db import models

class POStatus(models.IntegerChoices):
    CREATED = 0, "Created"
    APPROVED = 1, "Approved"
    CANCELLED = 2, "Cancelled"
    COMPLETED = 3, "Completed"

class PurchaseOrder(models.Model):
    po_id = models.AutoField(primary_key=True)
    vendor_id = models.IntegerField(max_length=50)
    vendor_code = models.CharField(max_length=50)
    vendor_name = models.CharField(max_length=200)
    currency_code = models.CharField(max_length=10, blank=True, null=True)
    vendor_reference = models.CharField(max_length=200, blank=True, null=True)
    warehouse_id = models.IntegerField(blank=True, null=True)
    order_date = models.DateField(blank=True, null=True)
    delivery_date = models.DateField(blank=True, null=True)
    invoice_date = models.DateField(blank=True, null=True)
    delivery_name = models.CharField(max_length=200, blank=True, null=True)
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    suburb = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    post_code = models.CharField(max_length=20, blank=True, null=True)
    country_id = models.IntegerField(blank=True, null=True)
    tax_percentage = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    payment_term_id = models.IntegerField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    comments = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status_id = models.IntegerField(
        choices=POStatus.choices,
        default=0,
        blank=True,
        null=True
    )
    created_by = models.IntegerField(blank=True, null=True)
    sub_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # qty*price
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # subtital 's tax amount
    summary_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # subtotal + taxamount



    #discount_amt = models.DecimalField(max_digits=12, decimal_places=2,
     #                                  default=0)  # subtotal's discount percentage amount
    #exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    #discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    class Meta:
        db_table = 'store_admin_purchase_order'

    def __str__(self):
        return f"PO-{self.po_id}"

class PurchaseOrderItem(models.Model):
    item_id = models.AutoField(primary_key=True)
    #purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    #product = models.ForeignKey("Product", on_delete=models.SET_NULL, null=True)
    po_id  = models.IntegerField(blank=True, null=True)
    product_id  = models.IntegerField(blank=True, null=True)
    qty = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    tax_percentage = models.DecimalField(max_digits=10, decimal_places=2, default=0) #tax %
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0) # disc %

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0) #qty*price
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0) #subtital 's tax amount
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0) #subtotal + taxamount
    discount_amt = models.DecimalField(max_digits=12, decimal_places=2, default=0) #subtotal's discount percentage amount

    created_by = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    unit = models.CharField(max_length=10, blank=True, null=True)
    def save(self, *args, **kwargs):
        # Auto calculate line amount:
        qty = Decimal(self.qty)
        price = Decimal(self.price)
        discount_pct = Decimal(self.discount_percentage)
        tax_pct = Decimal(self.tax_percentage)
        subtotal_before_discount = qty * price
        discount_amt = subtotal_before_discount * (discount_pct / Decimal('100'))
        subtotal_after_discount = subtotal_before_discount - discount_amt
        tax_amount = subtotal_after_discount * (tax_pct / Decimal('100'))
        line_total = subtotal_after_discount + tax_amount
        self.subtotal = subtotal_after_discount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.discount_amt = discount_amt.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.tax_amount = tax_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.line_total = line_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"PO Item {self.item_id}"

    class Meta:
        db_table = 'store_admin_purchase_order_item'