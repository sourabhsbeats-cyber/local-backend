from decimal import Decimal, ROUND_HALF_UP

from django.db import models

class POApprovalStatus(models.IntegerChoices):
    DRAFT = 0, "Draft"
    PENDING = 1, "Pending Approval"
    APPROVED = 2, "Approved"

class POReceiveStatus(models.IntegerChoices):
    NOT_RECEIVED = 0, "Not Received"
    PARTIALLY_RECEIVED = 1, "Partially Received"
    RECEIVED = 2, "Received"

class POBillingStatus(models.IntegerChoices):
    NOT_BILLED = 0, "Not Billed"
    PARTIALLY_BILLED = 1, "Partially Billed"
    BILLED = 2, "Billed"

#----------------------------------------------------------------------------------------#
#--------------------------- Purchase Receive -------------------------------------------#
#----------------------------------------------------------------------------------------#

class PurchaseOrderTransactions(models.Model):
    po_trans_id = models.AutoField(primary_key=True)
    po_id = models.IntegerField()
    prev_status = models.IntegerField(choices=POApprovalStatus.choices,
        default=0,
        blank=True,
        null=True)
    prev_updated_at = models.DateTimeField(auto_now_add=True)
    prev_status_description = models.CharField(max_length=200)
    current_status = models.IntegerField(choices=POApprovalStatus.choices,
        default=0,
        blank=True,
        null=True)
    current_status_description = models.CharField(max_length=200)
    created_at = models.DateField(auto_now=True)
    created_by = models.IntegerField()

class PurchaseReceives(models.Model):
    po_receive_id       = models.AutoField(primary_key=True)
    po_id               = models.IntegerField(blank=False)
    vendor_id           = models.IntegerField(blank=False)
    po_number           = models.CharField(max_length=20)
    po_receive_number   = models.CharField(max_length=20)
    received_date       = models.DateField(blank=True, null=True)
    status_id           = models.IntegerField(choices=POReceiveStatus.choices, default=0, blank=True, null=True)
    internal_ref_notes  = models.TextField(blank=True, null=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    created_by          = models.IntegerField(blank=True, null=True)

    is_billed           = models.IntegerField(default=0)
    class Meta:
        db_table = 'store_admin_purchase_receives'

class PurchaseReceivedItems(models.Model):
    received_item_id    = models.AutoField(primary_key=True)
    po_receive_id       = models.IntegerField(blank=True, null=True)
    product_id          = models.IntegerField(blank=True, null=True)
    item_id             = models.IntegerField(blank=True, null=True)
    received_qty        = models.IntegerField(default=1)
    status_id           = models.IntegerField(default=0)
    created_by          = models.IntegerField(blank=True, null=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'store_admin_purchase_received_items'

class PurchaseReceiveFiles(models.Model):
    po_order_receive_file_id = models.AutoField(primary_key=True)
    po_receive_id            = models.IntegerField()
    image_path               = models.FileField(upload_to="purchase_order/", null=True, blank=True)
    uploaded_at              = models.DateTimeField(auto_now_add=True)
    created_at              = models.DateTimeField(auto_now_add=True)
    created_by              = models.IntegerField()

    class Meta:
        db_table = 'store_admin_purchase_received_files'


#-------------------------------------------------------------------------------------------#
#--------------------------- Purchase Order ------------------------------------------------#
#-------------------------------------------------------------------------------------------#
#EOF Purchase order receives
class PurchaseOrder(models.Model):
    po_id = models.AutoField(primary_key=True)
    po_number = models.CharField(max_length=20)
    vendor_id = models.IntegerField()
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
        choices=POApprovalStatus.choices,
        default=0,
        blank=True,
        null=True
    )
    created_by = models.IntegerField(blank=True, null=True)
    sub_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # qty*price
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # subtital 's tax amount
    summary_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # subtotal + taxamount
    surcharge_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # surchase_total
    shipping_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # shipping_charge

    is_archived = models.IntegerField(blank=False, default=0)

    def save(self, *args, **kwargs):
        sub_total = Decimal(self.sub_total)
        surcharge_total = Decimal(self.surcharge_total)
        shipping_charge = Decimal(self.shipping_charge) 
        final_total = sub_total+surcharge_total+shipping_charge
        self.line_total = final_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)

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
    #To track the received qty from Purchase Orders receives
    received_qty = models.IntegerField(blank=True, null=True, default=0)
    # To track the pending qty from Purchase Orders receives
    pending_qty = models.IntegerField(blank=True, null=True, default=0)
    ordered_qty = models.IntegerField(blank=True, null=True, default=0)

    order_ref = models.CharField(max_length=80, blank=True, null=True)
    order_type = models.CharField(max_length=80, blank=True, null=True)
    def save(self, *args, **kwargs):
        # Auto calculate line amount:
        is_create = self.pk is None

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

        # ---- Qty logic ----
        if is_create:
            self.ordered_qty = self.qty
            self.received_qty = 0
            self.pending_qty = self.qty
        #else:
        #    self.pending_qty = max(self.ordered_qty - self.received_qty, 0)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"PO Item {self.item_id}"

    class Meta:
        db_table = 'store_admin_purchase_order_item'

class PurchaseOrderVendor(models.Model):
    po_vendor_id = models.AutoField(primary_key=True)
    po_id  = models.IntegerField()
    po_number = models.CharField(max_length=80)
    order_date = models.DateTimeField(blank=True, null= True)
    invoice_date = models.DateTimeField(blank=True, null= True)
    invoice_due_date = models.DateTimeField(blank=True, null= True)
    invoice_ref_number = models.CharField(max_length=80) #vendor_invoice_ref_number
    delivery_ref_number = models.CharField(max_length=80) #vendor_invoice_ref_number

    created_by = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'store_admin_purchase_order_vendor_details'

class PurchaseOrderShipping(models.Model):
    po_shipping_id = models.AutoField(primary_key=True)
    po_id  = models.IntegerField()

    provider = models.CharField(max_length=80)
    website = models.CharField(max_length=180)
    tracking_number = models.CharField(max_length=80)

    created_by = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        db_table = 'store_admin_purchase_order_shipping_details'

class PurchaseOrderFiles(models.Model):
    po_order_file_id = models.AutoField(primary_key=True)
    po_id            = models.IntegerField()
    image_path       = models.FileField(upload_to="purchase_order/", null=True, blank=True)
    uploaded_at      = models.DateTimeField(auto_now_add=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    created_by       = models.IntegerField()

    class Meta:
        db_table = 'store_admin_purchase_order_files'


#--------------------------------------------------------------------------------------------------#
#----------------------------------Purchase Bills--------------------------------------------------#
#--------------------------------------------------------------------------------------------------#
#Purchase Bills
class PurchaseBills(models.Model):
    id = models.AutoField(primary_key=True)

    vendor_id = models.IntegerField()
    vendor_abn = models.CharField(max_length=20)

    warehouse = models.IntegerField()

    bill_no = models.CharField(max_length=50)
    bill_order_number = models.CharField(max_length=50)

    bill_date = models.DateField()
    due_date = models.DateField()

    payment_term_id = models.IntegerField()
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2)

    bill_status = models.IntegerField(default=0)
    billing_notes = models.TextField(blank=True, null=True)

    sub_total = models.DecimalField(max_digits=12, decimal_places=2)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2)

    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    surcharge_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.IntegerField(blank=False, default=0)
    class Meta:
        db_table = "store_admin_purchase_bills"

    def __str__(self):
        return self.bill_no

class PurchaseBillItems(models.Model):
    id = models.AutoField(primary_key=True)
    purchase_bill_id = models.IntegerField()  # NO FK
    product_id = models.IntegerField()
    po_item_id = models.IntegerField()
    po_receive_id = models.IntegerField()
    received_item_id = models.IntegerField()

    received_qty = models.PositiveIntegerField()

    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    line_total_updated = models.DecimalField(max_digits=12, decimal_places=2)
    is_archived = models.IntegerField(blank=False, default=0)
    class Meta:
        db_table = "store_admin_purchase_bill_items"

class PurchaseBillFiles(models.Model):
    purchase_bill_id = models.IntegerField()  # NO FK
    file = models.FileField(upload_to="purchase_bills/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_archived = models.IntegerField(blank=False, default=0)
    class Meta:
        db_table = "store_admin_purchase_bill_files"

#--------------------------------------------------------------------------------------------------#
#---------------------------------- Purchase Payments ---------------------------------------------#
#--------------------------------------------------------------------------------------------------#
class PurchasePaymentItems(models.Model):
    id = models.AutoField(primary_key=True)

    purchase_payment_id = models.IntegerField()   # NO FK
    purchase_bill_id = models.IntegerField()      # NO FK

    bill_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)

    payment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_withheld = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    payment_created_date = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "store_admin_purchase_payment_items"

class PurchasePayments(models.Model):
    id = models.AutoField(primary_key=True)

    vendor_id = models.IntegerField()
    warehouse = models.IntegerField(blank=True, null=True, default=0)

    payment_no = models.CharField(max_length=50, unique=True)

    payment_date = models.DateField()
    mode_of_payment = models.CharField(max_length=50)
    paid_through = models.CharField(max_length=50)

    payment_made_amount = models.DecimalField(max_digits=12, decimal_places=2)
    bank_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    card_number = models.CharField(max_length=50, blank=True, null=True)
    reference_number = models.CharField(max_length=50, blank=True, null=True)

    deduct_tds = models.BooleanField(default=False)

    notes = models.TextField(blank=True, null=True)

    payment_status = models.IntegerField(default=0)
    # 0 = Draft, 1 = Completed, 2 = Cancelled

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "store_admin_purchase_payments"

    def __str__(self):
        return self.payment_no

class PurchasePaymentFiles(models.Model):
    purchase_payment_id = models.IntegerField()  # NO FK
    file = models.FileField(upload_to="purchase_payments/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "store_admin_purchase_payment_files"