from decimal import Decimal, ROUND_HALF_UP

from django.db import models

class POStatus(models.IntegerChoices):
    DRAFT__PENDING = -1, "Draft|Pending"
    PARKED__PENDING = 0, "Parked|Pending"
    PLACED__PENDING = 1, "Placed|Pending"
    PLACED__SHIPPED = 2, "Placed|Shipped"
    PLACED__BACK_ORDER = 3, "Placed|Back Order"
    PARTIALLY_DELIVERED__PARTIALLY_DELIVERED = 4, "Partially Delivered|Partially Delivered"
    DELIVERED__DELIVERED = 5, "Delivered|Delivered" #All costs added and payments completed; PO is fully locked and tracking status must be Delivered
    CLOSED_DELIVERED = 6, "Closed|Delivered"

    #CANCELLED = 7, "Cancelled"

class POShippingStatus(models.IntegerChoices):
    PENDING = -1, "Pending"
    SHIPPED = 2, "Shipped"
    BACK_ORDER = 3, "Back Order"
    PARTIALLY_DELIVERED = 4, "Partially Delivered"
    ALL_RECEIVED = 6, "All stock received"
    DELIVERED = 5, "Delivered"

class POPaymentStatus(models.IntegerChoices):
    PAID = 1, "Paid"
    UNPAID = 2, "Unpaid"
    CANCELED = 3, "Cancelled"
    ON_HOLD = 4, "On Hold"

class POBillingStatus(models.IntegerChoices):
    CREATED = 0, "Created"
    NOT_BILLED = 1, "Not Billed"
    PARTIALLY_BILLED = 2, "Partially Billed"
    BILLED = 3, "Billed"

class LedgerEntryType(models.IntegerChoices):
    DEBIT = 1, "Debit"
    CREDIT = 2, "Credit"

po_status_list = [
    {"id": -1, "purchase_status": "Draft", "tracking_status": "Pending", "description": "Draft PO created by the team"},
    {"id": 0, "purchase_status": "Parked", "tracking_status": "Pending", "description": "Draft PO created by the team"},
    {"id": 1, "purchase_status": "Placed", "tracking_status": "Pending", "description": "PO sent to supplier; no dispatch yet"},
    {"id": 2, "purchase_status": "Placed", "tracking_status": "Shipped", "description": "PO sent; supplier has shipped goods"},
    {"id": 3, "purchase_status": "Placed", "tracking_status": "Back Order", "description": "PO sent; item is on back-order"},
    {"id": 4, "purchase_status": "Partially Delivered", "tracking_status": "Partially Delivered", "description": "Partial stock received"},
    {"id": 5, "purchase_status": "Delivered", "tracking_status": "Delivered", "description": "All stock received"},
    {"id": 6, "purchase_status": "Closed", "tracking_status": "Delivered", "description": "Fully locked and tracking must be Delivered"},
    {"id": 7, "purchase_status": "Cancelled", "tracking_status": "N/A", "description": "Cancelled PO"}
]
#----------------------------------------------------------------------------------------#
#--------------------------- Purchase Receive -------------------------------------------#
#----------------------------------------------------------------------------------------#


class PurchaseReceives(models.Model):
    po_receive_id       = models.AutoField(primary_key=True)
    po_id               = models.IntegerField(blank=False)
    vendor_id           = models.IntegerField(blank=False)
    po_number           = models.CharField(max_length=20)
    po_receive_number   = models.CharField(max_length=20)
    received_date       = models.DateField(blank=True, null=True)
    shipping_date       = models.DateField(blank=True, null=True)
    status_id           = models.IntegerField(choices=POStatus.choices, default=0, blank=True, null=True)
    internal_ref_notes  = models.TextField(blank=True, null=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now_add=True)
    created_by          = models.IntegerField(blank=True, null=True)
    updated_by          = models.IntegerField(blank=True, null=True)

    summary_total = models.DecimalField(max_digits=10, decimal_places=4, default=0.0)
    sub_total = models.DecimalField(max_digits=10, decimal_places=4, default=0.0)
    tax_total = models.DecimalField(max_digits=10, decimal_places=4, default=0.0)

    is_billed           = models.IntegerField(default=0)
    is_completed        = models.IntegerField(default=0)
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

class PurchaseOrderPrimaryDetails(models.Model):
    po_primary_id = models.AutoField(primary_key=True)
    po_id = models.IntegerField()

    po_status = models.IntegerField(choices=POStatus.choices,
        default=0,
        blank=True,
        null=True)
    shipping_status = models.IntegerField(choices=POShippingStatus.choices,
                                         default=0,
                                         blank=True,
                                         null=True)
    status_description = models.CharField(max_length=200,blank=True, null=True)
    po_number = models.CharField(max_length=80, blank=True, null=True)
    created_at = models.DateField(auto_now=True)
    created_by = models.IntegerField()
    is_primary = models.IntegerField()
    total_ordered = models.IntegerField()
    total_received = models.IntegerField()

    class Meta:
        db_table = 'store_admin_purchase_order_primary_details'

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

    parent_po_id = models.IntegerField(blank=True, null=True)

    tax_percentage = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    payment_term_id = models.IntegerField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    comments = models.TextField(blank=True, null=True)

    status_id = models.IntegerField(
        choices=POStatus.choices,
        default=-1,
        blank=True,
        null=True
    )
    completion_status = models.IntegerField(
        default=None,
        blank=True,
        null=True
    )
    payment_status_id = models.IntegerField(
        choices=POPaymentStatus.choices,
        default=0,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.IntegerField(blank=True, null=True)

    updated_by = models.IntegerField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

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
        db_table = 'store_admin_purchase_orders'

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
        db_table = 'store_admin_purchase_order_items'

class PurchaseOrderVendor(models.Model):
    po_vendor_id = models.AutoField(primary_key=True)
    po_id  = models.IntegerField()
    po_number = models.CharField(max_length=80)
    order_number = models.CharField(max_length=80)
    order_date = models.DateTimeField(blank=True, null= True)
    invoice_date = models.DateTimeField(blank=True, null= True)
    invoice_due_date = models.DateTimeField(blank=True, null= True)
    invoice_ref_number = models.CharField(max_length=80) #vendor_invoice_ref_number
    delivery_ref_number = models.CharField(max_length=80) #vendor_invoice_ref_number
    invoice_status = models.IntegerField(blank=True, null= True) #vendor_invoice_status

    created_by = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'store_admin_purchase_order_vendor_details'

class PurchaseOrderShipping(models.Model):
    po_shipping_id = models.AutoField(primary_key=True)
    po_id  = models.IntegerField()
    po_item_id  = models.IntegerField() #po_receive item id - product id
    receive_id  = models.IntegerField() #po_receive receive id

    provider = models.IntegerField(blank=True, null=True)
    website = models.CharField(max_length=180)
    tracking_number = models.CharField(max_length=80)

    shipped_date = models.DateField(blank=True, null=True)
    received_date = models.DateField(blank=True, null=True)

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


class PurchaseOrderInvoiceDetails(models.Model):
    po_invoice_id = models.AutoField(primary_key=True)
    po_id            = models.IntegerField()
    po_item_id       = models.IntegerField()
    receive_id       = models.IntegerField()
    po_amount        = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    invoice_number = models.CharField(max_length=45, null=True, blank=True)
    invoice_date     = models.DateField()
    invoice_due_date = models.DateField()
    invoice_payment_term_id = models.IntegerField(null=True)
    invoice_status_id = models.IntegerField(null=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    created_by       = models.IntegerField(default=0)

    class Meta:
        db_table = 'store_admin_purchase_order_invoice_details'


#--------------------------------------------------------------------------------------------------#
#----------------------------------Purchase Bills--------------------------------------------------#
#--------------------------------------------------------------------------------------------------#
#Purchase Bills
class PurchaseBills(models.Model):
    #form fields
    bill_id = models.AutoField(primary_key=True)
    vendor_id = models.IntegerField()
    vendor_abn = models.CharField(max_length=20)
    location = models.CharField(max_length=120)
    bill_no = models.CharField(max_length=50)
    bill_order_number = models.CharField(max_length=50)
    bill_date = models.DateField()
    due_date = models.DateField()
    payment_term_id = models.IntegerField()
    tax_total = models.DecimalField(max_digits=12, decimal_places=2)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    billing_notes = models.TextField(blank=True, null=True)
    #EOF Form fields
    #mapping & manage fields
    is_archived = models.IntegerField(blank=False, default=0)
    po_receive_id = models.IntegerField(blank=False, null=False)
    sub_total = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.IntegerField()
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.IntegerField()

    # final row calc fields
    surcharge_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    surcharge_tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount_percentage = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2) #Final bill total (UI / calculation result)
    #eof final row


    #internal fields
    bill_status = models.IntegerField(default=0)
    pending_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00) #Remaining payable
    bill_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00) #Authoritative payable amount
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00) #Total settled (payments + credits)
    is_completed = models.IntegerField()

    class Meta:
        db_table = "store_admin_purchase_bills"

    def __str__(self):
        return self.bill_no

class PurchaseBillItems(models.Model):
    purchase_bill_item_id = models.AutoField(primary_key=True)
    purchase_bill_id = models.IntegerField()  # NO FK
    product_id = models.IntegerField()
    po_item_id = models.IntegerField()
    po_receive_id = models.IntegerField()
    received_item_id = models.IntegerField()

    received_qty = models.PositiveIntegerField()

    line_total = models.DecimalField(max_digits=12, decimal_places=2) #respective calculated total
    line_total_updated = models.DecimalField(max_digits=12, decimal_places=2) # modified amount
    is_archived = models.IntegerField(blank=False, default=0)
    created_at = models.IntegerField()
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
    purchase_payment_item_id = models.AutoField(primary_key=True) #→
    purchase_payment_id = models.IntegerField()   # NO FK payment header (PurchasePayments.id)
    purchase_bill_id = models.IntegerField()      # NO FK bill being paid
    bill_amount = models.DecimalField(max_digits=12, decimal_places=2) #bill total at time of payment
    amount_due = models.DecimalField(max_digits=12, decimal_places=2) #bill balance at time of payment
    payment_amount = models.DecimalField(max_digits=12, decimal_places=2) #amount applied in this payment
    amount_withheld = models.DecimalField(max_digits=12, decimal_places=2, default=0) #TDS / withholding
    payment_created_date = models.DateField(blank=True, null=True) #date shown in UI

    class Meta:
        db_table = "store_admin_purchase_payment_items"

class PurchasePayments(models.Model):
    id = models.AutoField(primary_key=True)

    vendor_id = models.IntegerField()
    bill_id = models.IntegerField(blank=False, null=False)
    location = models.CharField(max_length=120, blank=True, null=True)

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
    created_by = models.IntegerField(blank=False, null=False)
    updated_by = models.IntegerField()
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


# payment credits flow
from django.db import models

class VendorPayments(models.Model):
    vendor_payment_id = models.BigAutoField(primary_key=True)

    vendor_id = models.IntegerField()

    payment_no = models.CharField(max_length=50)
    payment_date = models.DateField()

    payment_mode = models.CharField(max_length=30, blank=True, null=True)
    paid_through = models.CharField(max_length=30, blank=True, null=True)

    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    bank_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    notes = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "store_admin_vendor_payments"

class VendorPaymentAllocations(models.Model):
    payment_allocation_id = models.BigAutoField(primary_key=True)

    payment_id = models.BigIntegerField()
    bill_id = models.BigIntegerField()

    amount_applied = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "store_admin_vendor_payment_allocations"
        unique_together = ("payment_id", "bill_id")

class VendorCredits(models.Model):
    vendor_credit_id = models.BigAutoField(primary_key=True)

    vendor_id = models.IntegerField()

    source_type = models.CharField(
        max_length=30,
        help_text="OVERPAYMENT, CREDIT_NOTE"
    )

    source_id = models.BigIntegerField(blank=True, null=True)

    credit_amount = models.DecimalField(max_digits=12, decimal_places=2)
    used_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "store_admin_vendor_credits"

class VendorLedger(models.Model):
    vendor_ledger_id = models.BigAutoField(primary_key=True)

    vendor_id = models.IntegerField()

    reference_type = models.CharField(
        max_length=20,
        help_text="BILL, PAYMENT, CREDIT"
    )
    reference_id = models.BigIntegerField()

    entry_type = models.PositiveSmallIntegerField(
        help_text="1 = Debit, 2 = Credit"
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "store_admin_vendor_ledger"


