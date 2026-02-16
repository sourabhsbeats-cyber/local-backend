from django.core.exceptions import ValidationError
from django.utils import timezone

from store_admin.helpers import name_validator, name_validator_none, reference_validator, date_validator, zip_validator, \
    get_prep_label
from store_admin.models.payment_terms_model import PaymentTerm
from django.shortcuts import render, redirect

from store_admin.models.po_models.po_models import (
    PurchaseBills,
    PurchaseBillItems,
    PurchaseBillFiles, PurchasePayments, PurchaseOrderInvoiceDetails
)

from store_admin.models.po_models.po_models import PurchaseOrder, POBillingStatus, PurchaseOrderItem, PurchaseReceiveFiles, \
    PurchaseReceivedItems, PurchaseReceives, PurchaseOrderShipping, PurchaseOrderVendorDetails
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


#verified
#list vendors Purchase receives by vendor id
def get_vendors_ps(request, vendor_id):
    ps_receives = PurchaseReceives.objects.filter(vendor_id=vendor_id, is_billed=0).all()
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


#listing bills against vendor select
@login_required
def vendor_bills_listing_json(request):
    vendor_id = request.GET.get("vendor_id")
    #bill_no = request.GET.get("bill_no")
    qs = PurchaseBills.objects.filter(is_completed=0).all().order_by("-bill_id")
    if vendor_id:
        qs = qs.filter(vendor_id=vendor_id)

    data = []
    for bill in qs:
        items_count = PurchaseBillItems.objects.filter(
            purchase_bill_id=bill.bill_id
        ).count()

        data.append({
            "bill_id": bill.bill_id,
            "bill_no": bill.bill_no,
            "bill_order_number": bill.bill_order_number,
            "vendor_id": bill.vendor_id,
            "vendor_abn": bill.vendor_abn,
            "warehouse": bill.location,
            "bill_date": bill.bill_date,
            "due_date": bill.due_date,
            "status": bill.bill_status,

            "sub_total": float(bill.sub_total),
            "tax_total": float(bill.tax_total),
            "grand_total": float(bill.grand_total),

            "bill_amount": float(bill.bill_amount),
            "paid_amount": float(bill.paid_amount),
            "pending_amount": float(bill.pending_amount),

            "shipping_charge": 0, #float(bill.shipping_charge),
            "surcharge_total": 0, #float(bill.surcharge_total),

            "items_count": items_count,
            "created_at": bill.created_at,
        })

    return JsonResponse({
        "status": True,
        "data": data
    })
import re
def generate_next_payment_no():
    last_payment = (
        PurchasePayments.objects
        .order_by("-id")
        .values_list("payment_no", flat=True)
        .first()
    )

    if not last_payment:
        return "PAY-00001"

    match = re.search(r"(\d+)$", last_payment)
    if not match:
        return "PAY-00001"

    next_no = int(match.group(1)) + 1
    return f"PAY-{next_no:05d}"

#verified
#listing_bill_line_items
@login_required
def listing_bill_line_items(request):
    bill_id = request.GET.get("bill_id")
    po_bill = PurchaseBills.objects.filter(bill_id=bill_id, is_archived=0).first()
    if po_bill is None:
        raise Exception("Bill not found")
    po_bill_line_items = PurchaseBillItems.objects.filter(purchase_bill_id=po_bill.bill_id, is_archived=0).all()
    ps_rx_items_data = []

    #for po_bill_line_item in po_bill_line_items:
        #product = Product.objects.filter(product_id=ps_rx_item.product_id).first()
        #purchase_order_item = PurchaseOrderItem.objects.filter(item_id=ps_rx_item.item_id).first()

    if po_bill:
        warehouse_det = Warehouse.objects.filter(is_default=1).first()
        if not warehouse_det:
            warehouse_det = Warehouse.objects.filter(is_default=1).first()

        ps_rx_items_data.append({
            "payment_no":generate_next_payment_no(),
            "payment_ref_no":po_bill.bill_no,
            "payment_date_ref":timezone.now(),
            "bill_date":po_bill.bill_date,
            "due_date":po_bill.due_date,
            "bill_no": po_bill.bill_no, #bil po
            "bill_order_no": po_bill.bill_order_number, #PO Order Number
            "location": warehouse_det.warehouse_name,
            "bill_amount":po_bill.grand_total,
            "amount_due":po_bill.pending_amount, #for this bill pending due paid
            #"amount_withheld":0.0, #vendors credit amount
            "payment_created":datetime.date.today(), #vendors credit amount
            #"item": ps_rx_item.status_id,
        })
    return JsonResponse({"status": True, "line_items": ps_rx_items_data})

@api_view(["GET"])
def po_invoice_listing_json(request):
    po_id = request.GET.get("po_id")
    invoice_number = request.GET.get("invoice_number")

    qs = PurchaseOrderInvoiceDetails.objects.all().order_by("-po_invoice_id")

    if po_id:
        qs = qs.filter(po_id=po_id)

    if invoice_number:
        qs = qs.filter(invoice_number__icontains=invoice_number)

    # -------------------------------------------------
    # SUBQUERIES (because no FK relations)
    # -------------------------------------------------
    po_number_sq = PurchaseOrder.objects.filter(
        po_id=OuterRef("po_id")
    ).values("po_number")[:1]

    vendor_id_sq = PurchaseOrder.objects.filter(
        po_id=OuterRef("po_id")
    ).values("vendor_id")[:1]

    po_status_sq = PurchaseOrder.objects.filter(
        po_id=OuterRef("po_id")
    ).values("status_id")[:1]

    vendor_name_sq = Vendor.objects.filter(
        id=OuterRef("vendor_id")
    ).values("display_name")[:1]

    qs = qs.annotate(
        po_number=Subquery(po_number_sq),
        vendor_id=Subquery(vendor_id_sq),
        po_status_id=Subquery(po_status_sq),
        vendor_name=Subquery(vendor_name_sq),
    )

    data = []
    for inv in qs:
        data.append({
            "po_invoice_id": inv.po_invoice_id,
            "po_id": inv.po_id,
            "po_number": inv.po_number,
            "po_item_id": inv.product_id,
            "receive_id": inv.receive_id,
            "vendor_name": inv.vendor_name,
            "invoice_number": inv.invoice_number,
            "invoice_date": inv.invoice_date,
            "invoice_due_date": inv.due_date,
            "invoice_payment_term_id": inv.payment_term_id,
            "invoice_status_id": inv.payment_status_id,

            "po_amount": float(inv.po_amount or 0),

            "created_at": inv.created_at,
            "created_by": inv.created_by,
        })

    return JsonResponse({
        "status": True,
        "data": data
    })

#verified
@login_required
def list_ps_receive_line_items(request, po_receive_id):
    ps_rx_items = PurchaseReceivedItems.objects.filter(po_receive_id=po_receive_id).all()
    ps_rx_items_data = []
    for ps_rx_item in ps_rx_items:
        product = Product.objects.filter(product_id=ps_rx_item.product_id).first()

        purchase_order_item = PurchaseOrderItem.objects.filter(item_id=ps_rx_item.item_id).first()
      #  print(purchase_order_item)
       # return JsonResponse({}) asdasdasd
        #purchase_receives = PurchaseReceivedItems.objects.filter(po_receive_id=po_receive_id).first()

        # base cost
        line_cost = ps_rx_item.received_qty * purchase_order_item.price
        # discount
        disc_percentage = purchase_order_item.discount_percentage or Decimal("0")
        discount_amount = (line_cost * disc_percentage) / Decimal("100")
        net_cost = line_cost - discount_amount
        # tax (on discounted amount)
        tax_percentage = purchase_order_item.tax_percentage or Decimal("0")
        tax_amount = (net_cost * tax_percentage) / Decimal("100")
        print(tax_amount)
        # final line total
        final_line_cost = net_cost + tax_amount

        ps_rx_items_data.append({
            "item_name":product.title,
            "item_sku":product.sku,
            "item_asin":product.asin,
            "item_fnsku":product.fnsku,
            "barcode_label_type":product.barcode_label_type,
            "po_item_item_po_rate":purchase_order_item.price,
            #"po_item_ordered_qty": purchase_order_item.qty,
            "po_item_order_ref": purchase_order_item.order_ref,
            "po_item_order_type": purchase_order_item.order_type,
            #po_item_ordered_qty
            "received_item_id": ps_rx_item.received_item_id,
            "product_id": ps_rx_item.product_id,
            "po_receive_id": ps_rx_item.po_receive_id,

            "received_qty": ps_rx_item.received_qty,
            "item_id": ps_rx_item.item_id,

            "po_item_disc_percentage": disc_percentage,
            "po_item_tax_percentage": tax_percentage,
            "po_item_tax_amount": tax_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "po_item_subtotal": line_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),

            "po_item_line_total": final_line_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),  # purchase_order_item.line_total,
            #"item": ps_rx_item.status_id,
        })
    return JsonResponse({"status": True, "line_items": ps_rx_items_data})

from decimal import Decimal, ROUND_HALF_UP
from decimal import Decimal, InvalidOperation
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def all_purchases(request):
    # Subquery for warehouse name
    warehouse_sub = Warehouse.objects.filter(
        warehouse_id=OuterRef("warehouse_id")
    ).values("warehouse_name")[:1]

    # Subquery for vendor name
    vendor_sub = Vendor.objects.filter(
        id=OuterRef("vendor_id")
    ).values("display_name")[:1]

    qs = PurchaseOrder.objects.annotate(

        # Warehouse name
        warehouse_name=Coalesce(
            Subquery(warehouse_sub),
            Value(""),
            output_field=TextField()
        ),

        # Vendor Name
        vendor_name_val=Coalesce(
            Subquery(vendor_sub),
            Value(""),
            output_field=TextField()
        ),

        # Summary totals already stored in PO table
        subtotal_val=Coalesce("sub_total", Value(0), output_field=DecimalField()),
        tax_val=Coalesce("tax_total", Value(0), output_field=DecimalField()),
        total_val=Coalesce("summary_total", Value(0), output_field=DecimalField()),

    )
    for row in qs.values():
        print(row)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(sku__icontains=q) | Q(brand_name_val__icontains=q))

    try:
        page = int(request.GET.get("page", 1))
    except:
        page = 1

    try:
        size = int(request.GET.get("size", 20))
    except:
        size = 20

    size = min(size, 50)  # max 50 cap

    total = qs.count()
    start = (page - 1) * size
    end = start + size

    data = list(qs.order_by("po_id")[start:end].values(
        "po_id", "po_number", "vendor_id", "vendor_code", "vendor_name", "currency_code", "vendor_reference",
        "order_date", "delivery_date", "invoice_date", "delivery_name", "created_at", "status_id", "sub_total",
        "tax_total",
        "summary_total", "warehouse_name", "vendor_name_val", "vendor_name", "subtotal_val", "tax_val", "total_val"
    ))

    last_page = math.ceil(total / size) if total else 1

    #  Return EXACT Tabulator compatible JSON
    return Response({
        "data": data,
        "last_page": last_page,
        "total": total, "row_count": 200

    })


from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import transaction
from decimal import Decimal


#verified
@api_view(["POST"])
def save_po_bill(request):
    data = request.data
    try:
        with transaction.atomic():
            # -----------------------------
            # INSERT BILL (PRIMARY)
            # -----------------------------
            po_receive_id = data.get("items[0][po_receive_id]")

            grand_total = Decimal(data.get("grand_total", 0))

            bill = PurchaseBills.objects.create(
                vendor_id=data.get("vendor_id"),
                vendor_abn=data.get("vendor_abn"),
                location=data.get("warehouse"),
                bill_no=data.get("bill_no"),
                bill_order_number=data.get("bill_order_number"),
                bill_date=data.get("bill_date"),
                due_date=data.get("due_date"),
                payment_term_id=data.get("payment_term_id"),

                tax_percentage=Decimal("10.00"),  # or from payload
                billing_notes=data.get("billing_notes", ""),

                sub_total=Decimal(data.get("sub_total", 0)),
                tax_total=Decimal(data.get("tax_total", 0)),
                grand_total=grand_total,

                surcharge_amount=Decimal(data.get("surcharge_total", 0)),
                surcharge_tax_total=Decimal(data.get("surcharge_tax_total", 0)),
                discount_percentage=Decimal(data.get("discount_percentage", 0)),

                #  ACCOUNTING FIELDS (CRITICAL)
                bill_amount=grand_total,
                paid_amount=Decimal("0.00"),
                pending_amount=grand_total,
                bill_status=POBillingStatus.CREATED,

                po_receive_id=po_receive_id,
                created_by=request.user.id,
                updated_by=request.user.id,
                is_completed=0
            )

            # -----------------------------
            # INSERT LINE ITEMS
            # -----------------------------
            index = 0
            while True:
                prefix = f"items[{index}]"

                po_item_id = data.get(f"{prefix}[po_item_id]")
                if not po_item_id:
                    break

                received_qty = 0
                po_rcvd_item = PurchaseReceivedItems.objects.filter(received_item_id=data.get(f"{prefix}[received_item_id]")).first()
                if po_rcvd_item:
                    received_qty = po_rcvd_item.received_qty

                PurchaseBillItems.objects.create(
                    purchase_bill_id=bill.bill_id,
                    product_id=data.get(f"{prefix}[product_id]"),
                    po_item_id=po_item_id,
                    po_receive_id=data.get(f"{prefix}[po_receive_id]"),
                    received_item_id=data.get(f"{prefix}[received_item_id]"),
                    received_qty= received_qty, #int(data.get(f"{prefix}[received_qty]", 0)),
                    line_total=Decimal(data.get(f"{prefix}[line_total]", 0)),
                    line_total_updated=Decimal(
                        data.get(f"{prefix}[line_total_updated]", 0)
                    ),
                )

                index += 1

            # -----------------------------
            # INSERT FILES
            # -----------------------------
            for file in request.FILES.getlist("files[]"):
                PurchaseBillFiles.objects.create(
                    purchase_bill_id=bill.bill_id,
                    file=file
                )

            # -----------------------------
            # MARK PO RECEIVE AS BILLED
            # -----------------------------
            po_receive = PurchaseReceives.objects.filter(
                po_receive_id=po_receive_id
            ).first()

            if po_receive:
                po_receive.is_billed = 1
                po_receive.save(update_fields=["is_billed"])

            return Response({
                "status": True,
                "message": "Purchase Bill created successfully",
                "bill_id": bill.bill_id
            })

    except Exception as e:
        return Response({
            "status": False,
            "message": str(e)
        }, status=400)
