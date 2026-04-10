from django.core.exceptions import ValidationError
from store_admin.helpers import name_validator, name_validator_none, reference_validator, date_validator, zip_validator, \
    get_prep_label, get_decimal
from store_admin.models.payment_terms_model import PaymentTerm
from django.shortcuts import render, redirect

from store_admin.models.po_models.po_models import (
    PurchaseBills,
    PurchaseBillItems,
    PurchaseBillFiles, VendorLedger, VendorCredits, VendorPaymentAllocations, VendorPayments
)

from store_admin.serializers.payment_serializers import (
    VendorPaymentLogSerializer,
    VendorPaymentLogItemSerializer
)

from store_admin.models.po_models.po_models import PurchaseOrder, PurchaseOrderItem, PurchaseReceiveFiles, \
    PurchaseReceivedItems, PurchaseReceives, PurchasePayments, PurchasePaymentItems, PurchasePaymentFiles
from store_admin.models.product_model import Product, ProductShippingDetails, ProductPriceDetails, \
    ProductStaticAttributes, ProductDynamicAttributes, ProductImages
from store_admin.models.setting_model import Category, Brand, Manufacturer, AttributeDefinition, UnitOfMeasurements
from store_admin.models.vendor_models import Vendor, VendorBank, VendorContact, VendorAddress
from store_admin.models.warehouse_setting_model import Warehouse
from django.contrib.auth.decorators import login_required
import math
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Value, CharField, OuterRef, Subquery, Case, When, Q
from django.db.models.functions import Coalesce
from rest_framework.renderers import JSONRenderer
from rest_framework.decorators import api_view, renderer_classes, permission_classes
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.decorators import api_view
from rest_framework.response import Response

from django.http import HttpResponse, JsonResponse

from django.db.models import OuterRef, Subquery, Value, TextField, DecimalField
from django.db.models.functions import Coalesce

import datetime


def validate_purchase_order_model(po, line_items):
    rules = [
        ("vendor_id", "Vendor is required"),
        ("vendor_name", "Vendor Name is required"),
        ("po_number", "PO Number is required."),
        ("currency_code", "Currency Code is required"),
        ("vendor_reference", "Vendor Reference is required"),
        ("warehouse_id", "Warehouse is required"),
        ("order_date", "Order Date is required"),
        ("delivery_date", "Delivery Date is required"),
        ("payment_term_id", "Payment Term is required"),
        ("delivery_name", "Delivery Name is required"),
        ("address_line1", "Address Line 1 is required"),
        ("state", "State is required"),
        ("post_code", "Postcode is required"),
        ("country_id", "Country is required"),
        ("tax_percentage", "Tax Percentage is required"),
    ]

    # Loop the model fields
    for field, err_msg in rules:
        value = getattr(po, field, None)
        if value is None or str(value).strip() == "":
            return False, err_msg

    # Line items check
    if not line_items or len(line_items) == 0:
        return False, "Please add at least one product line item"

    if PurchaseOrder.objects.filter(vendor_reference=po.vendor_reference).exclude(po_id=po.po_id).exists():
        return False, "Can not duplicate Vendor Reference#."

    if PurchaseOrder.objects.filter(po_number=po.po_number).exclude(po_id=po.po_id).exists():
        return False, "Can not duplicate Purchase Order Number."

    if len(po.vendor_reference) < 4:
        return False, "Invalid Vendor Reference."
    try:
        name_validator_none(po.vendor_name)
    except ValidationError as e:
        return False, "Invalid vendor name."

    try:
        name_validator_none(po.delivery_name)
    except ValidationError as e:
        return False, "Invalid delivery name."

    try:
        name_validator_none(po.address_line1)
        # name_validator_none(po.address_line2)
    except ValidationError as e:
        return False, "Invalid address line."

    try:
        name_validator_none(po.state)
    except ValueError:
        return False, "Invalid state name."

    try:
        zip_validator(po.post_code)
    except ValueError:
        return False, "Postcode must be numeric."

        # Reference format
    try:
        reference_validator(po.vendor_reference)
    except ValueError:
        return False, "Invalid Vendor Reference# format."

        # Delivery date >= today
    # validate date now its not needed temporarily
    '''
    try:
        date_validator(po.delivery_date, 10)
        date_validator(po.order_date, 10)
    except ValueError as e:
        return False, str(e)
    '''

    return True, ""


@login_required
def view_po_receive(request, po_receive_id):
    if po_receive_id is None:
        return HttpResponse("Invalid PO", status=404)

    po = PurchaseReceives.objects.filter(po_receive_id=po_receive_id).first()
    if not po:
        return HttpResponse("Invalid PO", status=404)

    po_order_items = PurchaseReceivedItems.objects.filter(po_receive_id=po_receive_id).all()

    line_items = []

    for po_order_item in po_order_items:
        po_product = Product.objects.filter(product_id=po_order_item.product_id).first()
        po_line_item = PurchaseOrderItem.objects.filter().first()

        line_items.append({
            "item_name": po_product.title,
            "sku": po_product.sku,
            "ordered": po_line_item.ordered_qty,
            "received": po_order_item.received_qty,
            "in_transit": 0,
            "received_quantity": po_order_item.received_qty,
        })
    vendors_detail = Vendor.objects.filter(id=po.vendor_id).first()
    received_files = PurchaseReceiveFiles.objects.filter(po_receive_id=po_receive_id).all()
    context = {
        'po_receive_id': po_receive_id,
        'po': po,
        'line_items': line_items,
        'received_files': received_files,
        'vendors_detail': vendors_detail,
    }
    return render(request, 'sbadmin/pages/purchase_receive/view/view_po_receive.html', context)


from django.db.models import Max
# Product Add Bill Entry - Only GET
@login_required
def create_new_bill(request):
    vendors_list = Vendor.objects.all()
    po_next = (PurchaseReceives.objects.aggregate(max_id=Max("po_receive_id")).get("max_id") or 0) + 1
    po_receive_number = f"PR{po_next:04d}"

    payment_terms = PaymentTerm.objects.all()
    context = {
        'vendors': vendors_list,
        'payment_terms': payment_terms,
        'po_receive_number': po_receive_number,
        'po_received_date': datetime.date.today()}

    return render(request, 'sbadmin/pages/payments/add/add_payment_form.html', context)

#list vendors Purchase receives by vendor id
def get_vendors_ps(request, vendor_id):
    ps_receives = PurchaseReceives.objects.filter(vendor_id=vendor_id).all()
    ps_receives_data = []
    for ps_receive in ps_receives:
        ps_receives_data.append({
            "po_receive_id":ps_receive.po_receive_id,
            "po_id":ps_receive.po_id,
            "vendor_id":ps_receive.vendor_id,
            "po_number":ps_receive.po_number,
            "po_receive_number":ps_receive.po_receive_number,
            "received_date":ps_receive.received_date,
            "status_id":ps_receive.status_id,
        })
    return JsonResponse({"status":True, "data":ps_receives_data})

# PO reieve listing
@login_required
def payments_listing(request):
    # ---- Context ----
    context = {
        "user": request.user.id,
    }
    return render(request, 'sbadmin/pages/payments/listing/listing.html', context)

@login_required
def bills_listing_json(request):
    vendor_id = request.GET.get("vendor_id")
    bill_no = request.GET.get("bill_no")

    qs = PurchaseBills.objects.all().order_by("-id")

    if vendor_id:
        qs = qs.filter(vendor_id=vendor_id)

    if bill_no:
        qs = qs.filter(bill_no__icontains=bill_no)

    data = []

    for bill in qs:
        items_count = PurchaseBillItems.objects.filter(
            purchase_bill_id=bill.id
        ).count()

        data.append({
            "bill_id": bill.id,
            "bill_no": bill.bill_no,
            "bill_order_number": bill.bill_order_number,
            "vendor_id": bill.vendor_id,
            "vendor_abn": bill.vendor_abn,
            "warehouse": bill.warehouse,
            "bill_date": bill.bill_date,
            "due_date": bill.due_date,
            "status": bill.bill_status,

            "sub_total": float(bill.sub_total),
            "tax_total": float(bill.tax_total),
            "grand_total": float(bill.grand_total),

            "shipping_charge": float(bill.shipping_charge),
            "surcharge_total": float(bill.surcharge_total),

            "items_count": items_count,
            "created_at": bill.created_at,
        })

    return JsonResponse({
        "status": True,
        "data": data
    })


@login_required
def view_purchase_payment(request, payment_id):
    payment = get_object_or_404(
        PurchasePayments,
        id=payment_id
    )
    vendor_info = Vendor.objects.filter(id=payment.vendor_id).first()
    items = PurchasePaymentItems.objects.filter(
        purchase_payment_id=payment.id
    )

    files = PurchasePaymentFiles.objects.filter(
        purchase_payment_id=payment.id
    )

    used_amount = items.aggregate(
        total=Sum("payment_amount")
    )["total"] or Decimal("0.00")

    refunded_amount = max(
        payment.payment_made_amount - used_amount,
        Decimal("0.00")
    )

    excess_amount = payment.payment_made_amount - used_amount

    bill_ids = items.values_list('purchase_bill_id', flat=True)

    # 3. Fetch those specific Bills (Replace 'PurchaseBill' with your actual Model name)
    # We create a dictionary { 'bill_id': bill_object }
    bills = PurchaseBills.objects.filter(bill_id__in=bill_ids)

    context = {
        "payment": payment,
        "vendor_info": vendor_info,
        "items": items,
        "bills": bills,
        "files": files,
        "summary": {
            "amount_paid": payment.payment_made_amount,
            "amount_used": used_amount,
            "amount_refunded": refunded_amount,
            "amount_excess": excess_amount,
            "bank_charges": payment.bank_charges,
        }
    }

    return render(
        request,
        "sbadmin/pages/payments/view/view_payment.html",
        context
    )


@login_required
def list_ps_receive_line_items(request, po_receive_id):
    ps_rx_items = PurchaseReceivedItems.objects.filter(po_receive_id=po_receive_id).all()
    ps_rx_items_data = []
    for ps_rx_item in ps_rx_items:
        product = Product.objects.filter(product_id=ps_rx_item.product_id).first()
        purchase_order_item = PurchaseOrderItem.objects.filter(item_id=ps_rx_item.item_id).first()
        ps_rx_items_data.append({
            "item_name":product.title,
            "item_sku":product.sku,
            "item_asin":product.asin,
            "item_fnsku":product.fnsku,
            "barcode_label_type":product.barcode_label_type,
            "po_item_item_po_rate":purchase_order_item.price,
            "po_item_ordered_qty": purchase_order_item.qty,
            "po_item_tax_percentage": purchase_order_item.tax_percentage,
            "po_item_tax_amount": purchase_order_item.tax_amount,
            "po_item_disc_percentage": purchase_order_item.discount_percentage,
            "po_item_subtotal": purchase_order_item.subtotal,
            "po_item_line_total": purchase_order_item.line_total,
            "po_item_order_ref": purchase_order_item.order_ref,
            "po_item_order_type": purchase_order_item.order_type,

            "received_item_id": ps_rx_item.received_item_id,
            "product_id": ps_rx_item.product_id,
            "po_receive_id": ps_rx_item.po_receive_id,
            "received_qty": ps_rx_item.received_qty,
            "item_id": ps_rx_item.item_id,
            #"item": ps_rx_item.status_id,
        })
    return JsonResponse({"status": True, "line_items": ps_rx_items_data})

from decimal import Decimal, ROUND_HALF_UP
from decimal import Decimal, InvalidOperation
#verified
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def all_purchase_payments(request):
    #warehouse_sub = Warehouse.objects.filter(
   #     warehouse_id=OuterRef("warehouse")
   # ).values("warehouse_name")[:1]

    # -----------------------------
    # Subquery for vendor name
    # -----------------------------
    vendor_sub = Vendor.objects.filter(
        id=OuterRef("vendor_id")
    ).values("display_name")[:1]

    qs = PurchasePayments.objects.annotate(
        # Vendor name
        vendor_name_val=Coalesce(
            Subquery(vendor_sub),
            Value(""),
            output_field=TextField()
        ),
        bank_charges_val=Coalesce(
            "bank_charges",
            Value(0),
            output_field=DecimalField()
        ),
    )
    # -----------------------------
    # Search
    # -----------------------------
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(payment_no__icontains=q) |
            Q(vendor_name_val__icontains=q) |
            Q(mode_of_payment__icontains=q)
        )

    # -----------------------------
    # Pagination
    # -----------------------------
    try:
        page = int(request.GET.get("page", 1))
    except:
        page = 1

    try:
        size = int(request.GET.get("size", 20))
    except:
        size = 20

    size = min(size, 50)

    total = qs.count()
    start = (page - 1) * size
    end = start + size

    # -----------------------------
    # Data
    # -----------------------------
    data = list(
        qs.order_by("-id")[start:end].values(
            "id", "payment_no", "reference_number", "vendor_id",
            "vendor_name_val",   # "warehouse",
            #"warehouse_name",
            "payment_date",  "mode_of_payment",
            "paid_through",  "payment_status",
            "payment_made_amount", "bank_charges",
            "bank_charges_val",  "created_at"
        )
    )
    for row in data:
        payment_item = PurchasePaymentItems.objects.filter(purchase_payment_id=row.get("id")).first()
        row["paid_amount_val"] = payment_item.payment_amount
        row["amount_due"] = payment_item.amount_due

    #"paid_amount_val",
    last_page = math.ceil(total / size) if total else 1

    # -----------------------------
    # Tabulator compatible response
    # -----------------------------
    return Response({
        "data": data,
        "last_page": last_page,
        "total": total,
        "row_count": 200
    })


from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import transaction
from decimal import Decimal
#verified
@api_view(["POST"])
def save_purchase_payment(request):
    data = request.data
    #return JsonResponse({"status":False, "message":"Hi"})
    payment_no = data.get("payment_no")
    reference_number = data.get("payment_receive_number")

    payment_made_amount = get_decimal(data, "payment_made_amount")
    bank_charges = get_decimal(data, "bank_charges")

    # -----------------------------
    # BASIC VALIDATION
    # -----------------------------
    if payment_made_amount is None or bank_charges is None:
        return JsonResponse({"status": False, "message": "Invalid Charges"})

    if payment_made_amount <= 0:
        return JsonResponse({"status": False, "message": "Invalid Payment Amount"})

    if bank_charges < 0:
        return JsonResponse({"status": False, "message": "Invalid Bank Charges"})

    # -----------------------------
    # DUPLICATE CHECK
    # -----------------------------
    qs = PurchasePayments.objects.filter(
        Q(payment_no=payment_no)
    )

    if qs.exists():
        msg = []
        if qs.filter(payment_no=payment_no).exists():
            msg.append("Payment number already exists")

        return JsonResponse({"status": False, "message": ", ".join(msg)})

    try:
        with transaction.atomic():

            # ==================================================
            # READ LINE ITEMS
            # ==================================================
            items = []
            total_applied = Decimal("0.00")
            index = 0

            while True:
                bill_id = data.get(f"items[{index}][bill_id]")
                if not bill_id:
                    break

                amount = Decimal(data.get(f"items[{index}][payment_amount]", 0))
                if amount <= 0:
                    index += 1
                    continue

                items.append({
                    "bill_id": int(bill_id),
                    "amount": amount,
                    "payment_created": data.get(
                        f"items[{index}][payment_created]"
                    )
                })

                total_applied += amount
                index += 1

            if not items:
                return JsonResponse({
                    "status": False,
                    "message": "No payment items provided"
                })

            if total_applied > payment_made_amount:
                return JsonResponse({
                    "status": False,
                    "message": "Applied amount exceeds payment amount"
                })

            # ==================================================
            # CREATE PURCHASE PAYMENT (EXISTING LOGIC)
            # ==================================================
            payment = PurchasePayments.objects.create(
                vendor_id=data.get("vendor_id"),
                location=data.get("location"),
                payment_no=payment_no,
                payment_date=data.get("payment_date"),
                mode_of_payment=data.get("mode_of_payment"),
                paid_through=data.get("paid_through"),
                payment_made_amount=payment_made_amount,
                bank_charges=bank_charges,
                card_number=data.get("card_number"),
                reference_number=reference_number,
                deduct_tds=bool(int(data.get("deduct_tds", 0))),
                notes=data.get("comments", ""),
                bill_id=items[0]["bill_id"],  # UI reference
                created_by=request.user.id,
                payment_status=1,
            )
            # -----------------------------
            # INSERT PAYMENT ITEMS (FIXED)
            # -----------------------------
            for item in items:
                bill = PurchaseBills.objects.select_for_update().get(
                    bill_id=item["bill_id"]
                )

                PurchasePaymentItems.objects.create(
                    purchase_payment_id=payment.id,
                    purchase_bill_id=bill.bill_id,

                    bill_amount=bill.bill_amount,
                    amount_due=bill.pending_amount,

                    payment_amount=item["amount"],
                    amount_withheld=Decimal("0.00"),  # or from form later

                    payment_created_date=item["payment_created"]
                )
            # ==================================================
            # VENDOR PAYMENT (NEW)
            # ==================================================
            vendor_payment = VendorPayments.objects.create(
                vendor_id=payment.vendor_id,
                payment_no=payment_no,
                payment_date=payment.payment_date,
                payment_mode=payment.mode_of_payment,
                paid_through=payment.paid_through,
                amount_paid=payment_made_amount,
                bank_charges=bank_charges,
                notes="Auto from purchase payment"
            )

            # ==================================================
            # APPLY PAYMENT TO BILLS
            # ==================================================
            for item in items:
                bill = PurchaseBills.objects.select_for_update().get(
                    bill_id=item["bill_id"]
                )

                VendorPaymentAllocations.objects.create(
                    payment_id=vendor_payment.vendor_payment_id,
                    bill_id=bill.bill_id,
                    amount_applied=item["amount"]
                )

                # update bill
                bill.paid_amount += item["amount"]
                bill.pending_amount = bill.bill_amount - bill.paid_amount

                if bill.pending_amount <= 0:
                    bill.bill_status = 1  # Paid
                    bill.pending_amount = Decimal("0.00")
                else:
                    bill.bill_status = 2  # Partially Paid

                bill.save(update_fields=[
                    "paid_amount", "pending_amount", "bill_status"
                ])

            # ==================================================
            # HANDLE EXCESS → VENDOR CREDIT
            # ==================================================
            excess = payment_made_amount - total_applied

            if excess > 0:
                credit = VendorCredits.objects.create(
                    vendor_id=payment.vendor_id,
                    source_type="OVERPAYMENT",
                    source_id=vendor_payment.vendor_payment_id,
                    credit_amount=excess,
                    used_amount=Decimal("0.00"),
                    balance_amount=excess
                )

                VendorLedger.objects.create(
                    vendor_id=payment.vendor_id,
                    reference_type="CREDIT",
                    reference_id=credit.vendor_credit_id,
                    entry_type=2,
                    amount=-excess,
                    balance_after=get_vendor_balance(payment.vendor_id)
                )

            # ==================================================
            # VENDOR LEDGER ENTRY (PAYMENT)
            # ==================================================
            VendorLedger.objects.create(
                vendor_id=payment.vendor_id,
                reference_type="PAYMENT",
                reference_id=vendor_payment.vendor_payment_id,
                entry_type=2,
                amount=-payment_made_amount,
                balance_after=get_vendor_balance(payment.vendor_id)
            )

            # ==================================================
            # FILE UPLOADS (UNCHANGED)
            # ==================================================
            for file in request.FILES.getlist("files[]"):
                PurchasePaymentFiles.objects.create(
                    purchase_payment_id=payment.id,
                    file=file
                )

            return JsonResponse({
                "status": True,
                "message": "Purchase payment saved successfully",
                "payment_id": payment.id
            })

    except Exception as e:
        return JsonResponse({
            "status": False,
            "message": str(e)
        }, status=400)


def get_vendor_balance(vendor_id):
    last = VendorLedger.objects.filter(
        vendor_id=vendor_id
    ).order_by("-vendor_ledger_id").first()

    return last.balance_after if last else Decimal("0.00")

from django.shortcuts import render, get_object_or_404
@api_view(["GET"])
def view_po_bill(request, bill_id):
    bill = get_object_or_404(PurchaseBills, id=bill_id)

    items = PurchaseBillItems.objects.filter(purchase_bill_id=bill.id)
    files = PurchaseBillFiles.objects.filter(purchase_bill_id=bill.id)

    context = {
        "bill": bill,
        "items": items,
        "files": files,
        "view_only": True,  #  flag for template
    }

    return render(request, "sbadmin/pages/bills/view/view_po_receive.html", context)