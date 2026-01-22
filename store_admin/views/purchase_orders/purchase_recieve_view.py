import os
from sys import get_int_max_str_digits
from xmlrpc.client import Boolean

from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseBadRequest

from store_admin.helpers import name_validator,getUserName, name_validator_none, reference_validator, date_validator, zip_validator, \
    get_prep_label, format_tax_percentage, parse_date_or_none, safe_int, to_int_or_none
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.address_model import Addresses
from django.db import transaction
from django.db.models import Value as V
from django.db.models.functions import Concat
from django.urls import reverse
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

from store_admin.models.po_models.po_models import PurchaseOrder, POStatus, PurchaseOrderItem, \
    PurchaseReceiveFiles, \
    PurchaseReceivedItems, PurchaseReceives, PurchaseOrderShipping, PurchaseOrderVendor, PurchaseBills, \
    PurchaseBillItems, PurchaseBillFiles, PurchasePayments, PurchasePaymentItems, PurchasePaymentFiles, VendorPayments, \
    VendorPaymentAllocations, VendorCredits, VendorLedger, POShippingStatus, PurchaseOrderPrimaryDetails, \
    PurchaseOrderInvoiceDetails
from store_admin.models.product_model import Product, ProductShippingDetails, ProductPriceDetails, \
    ProductStaticAttributes, ProductDynamicAttributes, ProductImages
from store_admin.models.setting_model import Category, Brand, Manufacturer, AttributeDefinition, UnitOfMeasurements, \
    ShippingProviders
from store_admin.models.vendor_models import Vendor, VendorBank, VendorContact, VendorAddress
from django.db.models import Min
from django.db import IntegrityError
from django.db.models import Subquery, OuterRef, Value, CharField, When, Case
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from store_admin.models import Country, State
from store_admin.models.warehouse_setting_model import Warehouse
from store_admin.models.warehouse_transaction_model import ProductWarehouse
from django.db.models import Subquery, OuterRef, IntegerField, TextField
from django.db.models.functions import Coalesce
from django.db.models import OuterRef, Subquery, Exists, BooleanField
from django.db.models import Sum, Value, Q
from django.db.models.functions import Coalesce
from rest_framework.decorators import api_view
from django.db.models.functions import Concat
from django.conf import settings
from django.templatetags.static import static
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import (
    Sum, Value, CharField, OuterRef, Subquery, Case, When, Q
)
from django.db.models.functions import Coalesce
import math
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Value, CharField, OuterRef, Subquery, Case, When, Q
from django.db.models.functions import Coalesce
from rest_framework.renderers import JSONRenderer
from rest_framework.decorators import api_view, renderer_classes, permission_classes

from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.template.loader import render_to_string
from django.http import HttpResponse
from rest_framework.views import APIView
from weasyprint import HTML
from django.db.models import OuterRef, Subquery, Value, TextField, DecimalField
from django.db.models.functions import Coalesce
from django.db.models.functions import Right, Concat
from django.db.models import F
import datetime
from decimal import Decimal, ROUND_HALF_UP

from store_admin.views.libs.common import clean_percent
from store_admin.views.purchase_orders.purchase_orders_view import get_po_line_items, get_po_line_received_items
from store_admin.views.serializers.product_serializers import ProductImageSerializer
from store_admin.views.serializers.purchase_serializer import PurchaseReceiveSerializer
import re
#Verified
#Add new Action - Save btn -
from django.utils import timezone
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def save_po_order_receive(request):
    try:
        data = request.data
        user_id = request.user.id

        po_id = data.get("po_id")
        po = PurchaseOrder.objects.filter(po_id=po_id).first()
        if not po:
            raise ValueError("Invalid PO number")

        #payment_terms - po order update
        payment_term_id = data.get("payment_terms")
        po.payment_term_id = int(payment_term_id) if payment_term_id and payment_term_id.isdigit() else None
        #po.updated_by = request.user.id
        #po.updated_at = timezone.now()
        po.save(update_fields=["payment_term_id"])
        #received_date - po receive update
        receive = PurchaseReceives.objects.filter(po_id=po_id).first()
        if receive:
            receive.received_date = parse_date_or_none(data.get("received_date"))
            receive.shipping_date = parse_date_or_none(data.get("shipping_date"))
            receive.save(update_fields=["received_date", "shipping_date"])
        #shipping_date - po receive update

        po_vendor = PurchaseOrderVendor.objects.filter(po_id=po_id).first()
        if po_vendor:
            po_vendor.po_number = data.get("vendor_po_no")
            po_vendor.order_date = parse_date_or_none(data.get("vendor_po_order_date"))
            po_vendor.invoice_status =to_int_or_none(data.get("vendor_po_payment_status"))
            po_vendor.order_number = data.get("vendor_po_order_number")
            po_vendor.invoice_ref_number = data.get("vendor_po_invoice_no")
            po_vendor.delivery_ref_number = data.get("vendor_po_delivery_ref_no")
            po_vendor.invoice_date = parse_date_or_none(data.get("vendor_po_invoice_date"))
            po_vendor.invoice_due_date = parse_date_or_none(data.get("vendor_po_invoice_due_date"))
            po_vendor.save()
        else:
            PurchaseOrderVendor.objects.create(
                po_id=po_id,
                po_number=data.get("vendor_po_no"),
                order_number=data.get("vendor_po_order_number"),
                order_date=parse_date_or_none(data.get("vendor_po_order_date")),
                invoice_ref_number=data.get("vendor_po_invoice_no"),
                delivery_ref_number=data.get("vendor_po_delivery_ref_no"),
                invoice_status=to_int_or_none(data.get("vendor_po_payment_status")),
                invoice_date=parse_date_or_none(data.get("vendor_po_invoice_date")),
                invoice_due_date=parse_date_or_none(data.get("vendor_po_invoice_due_date")),
                created_by=user_id
            )

        #insert all shipping
        shipping_details = data.get("shipping_details", [])
        #print(shipping_providers)
        with transaction.atomic():
            # 1. delete all existing records
            PurchaseOrderShipping.objects.filter(po_id=po_id).delete()
            # 2. prepare new records
            shipping_objs = [
                PurchaseOrderShipping(
                    po_id=po_id,
                    provider=item.get("provider"),
                    tracking_number=item.get("tracking_no"),
                    shipped_date=parse_date_or_none(item.get("shipped_date")),
                    received_date=parse_date_or_none(item.get("received_date")),
                    created_by=request.user.id
                )
                for item in shipping_details
                if item.get("provider")
            ]
            # 3. bulk insert
            PurchaseOrderShipping.objects.bulk_create(shipping_objs)

        # ---------- FILE VALIDATION ----------
        '''
        files = request.FILES.getlist("files[]")
        allowed_exts = {"pdf", "jpg", "jpeg", "png", "doc", "docx", "xls", "xlsx"}
        if len(files) > 5:
            raise ValueError("Maximum 5 files allowed")

        for file in files:
            ext = file.name.split(".")[-1].lower()
            if file.size > 5 * 1024 * 1024:
                raise ValueError(f"{file.name} exceeds 5MB")
            if ext not in allowed_exts:
                raise ValueError(f"Invalid file type: {file.name}")
        
        REQUIRED_FIELDS = ["product_id", "po_item_id", "received_qty"]
        line_items = {}

        # Pattern matches "items[0]", "items[1]", etc.
        indices = {re.search(r"items\[(\d+)\]", k).group(1)
                   for k in data.keys() if k.startswith("items[")}

        for idx in indices:
            # Check if all required keys exist for this specific index
            missing = [f for f in REQUIRED_FIELDS if f"items[{idx}][{f}]" not in data]

            if not missing:
                # If all exist, extract them safely
                line_items[idx] = {
                    "product_id": data[f"items[{idx}][product_id]"],
                    "po_item_id": data[f"items[{idx}][po_item_id]"],
                    "received_qty": int(data.get(f"items[{idx}][received_qty]", 0))
                }
            else:
                return JsonResponse({"status":False, "message": "Invalid Purchase Receive details"})

        # 4. Final Check
        if not line_items:
            return JsonResponse({"status":False, "message": "Invalid Purchase Receive details"})

        #return JsonResponse({"status": False, "message": "Invalid Purchase Receive details"})
        # ---------- BASIC DATA ----------
        serializer = PurchaseReceiveSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        vendor_id = serializer.validated_data["vendor_id"]
        po_number = serializer.validated_data["po_number"]
        po_receive_number = serializer.validated_data["po_receive_number"]
        received_date = serializer.validated_data["received_date"]
        shipping_date = serializer.validated_data["shipping_date"]
        comments = serializer.validated_data.get("comments", "")

        po = PurchaseOrder.objects.filter(po_number=po_number).first()
        if not po:
            raise ValueError("Invalid PO number")

        
        if PurchaseReceives.objects.filter(po_receive_number=po_receive_number).exists():
            raise ValueError("Purchase Receive# already exists")

        # ---------- CREATE RECEIVE ----------
        
        receive = PurchaseReceives.objects.create(
            po_id=po.po_id,
            vendor_id=vendor_id,
            po_number=po_number,
            po_receive_number=po_receive_number,
            received_date=received_date,
            shipping_date=shipping_date,
            internal_ref_notes=comments,
            created_by=user_id
        )

        # ---------- LINE ITEMS ----------
        
        items_created = 0
        received_qty = 0
        for key in data.keys():
            if not key.startswith("items[") or not key.endswith("][product_id]"):
                continue

            index = key.split("[")[1].split("]")[0]

            product_id = data.get(f"items[{index}][product_id]")
            po_item_id = data.get(f"items[{index}][po_item_id]")
            received_qty = int(data.get(f"items[{index}][received_qty]", 0))

            if received_qty <= 0:
                raise ValueError("Invalid received qty")

            po_item = PurchaseOrderItem.objects.filter(
                item_id=po_item_id,
                po_id=po.po_id
            ).select_for_update().first()

            if not po_item:
                raise ValueError("Invalid PO item")

            ordered_qty = po_item.ordered_qty if po_item.ordered_qty > 0 else po_item.qty
            current_pending = max(ordered_qty - po_item.received_qty, 0)

            if received_qty > current_pending:
                raise ValueError("Received qty exceeds pending qty")

            PurchaseReceivedItems.objects.create(
                po_receive_id=receive.po_receive_id,
                product_id=product_id,
                item_id=po_item_id,
                received_qty=received_qty,
                created_by=user_id,
                status_id=1
            )

            po_item.received_qty += received_qty
            po_item.pending_qty = max(ordered_qty - po_item.received_qty, 0)
            po_item.save(update_fields=["received_qty", "pending_qty"])

            items_created += 1

        if items_created == 0:
            raise ValueError("No valid received items")

        # ---------- FILE SAVE ----------
        for file in files:
            PurchaseReceiveFiles.objects.create(
                po_receive_id=receive.po_receive_id,
                image_path=file,
                created_by=user_id
            )
        '''

        return JsonResponse(
            {"status": True, "po_receive_id": receive.po_receive_id},
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        transaction.set_rollback(True)  #  CRITICAL FIX
        return JsonResponse(
            {"status": False, "message": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

#verified
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
        po_line_item = PurchaseOrderItem.objects.filter(item_id=po_order_item.item_id).first()
        line_items.append({
            "item_name":po_product.title,
            "sku":po_product.sku,
            "ordered": po_line_item.qty if po_line_item else 0,
            "received":po_order_item.received_qty,
            "in_transit":0,
            "received_quantity":0, #po_order_item.received_qty,
        })
    vendors_detail = Vendor.objects.filter(id=po.vendor_id).first()
    received_files = PurchaseReceiveFiles.objects.filter(po_receive_id=po_receive_id).all()
    context = {
        'po_receive_id': po_receive_id,
        'po': po,
        "created_by": getUserName(po.created_by),
        'line_items':line_items,
        'received_files':received_files,
        'vendors_detail':vendors_detail,
    }
    return render(request, 'sbadmin/pages/purchase_receive/view/view_po_receive.html', context)

#edit po receive
def edit_po_receive(request, po_receive_id):
    if po_receive_id is None:
        return HttpResponse("Invalid PO", status=404)

    po_order = None
    po_receive = PurchaseReceives.objects.filter(po_receive_id=po_receive_id).first()
    if not po_receive:
        return HttpResponse("Invalid PO Receive", status=404)

    po_order = PurchaseOrder.objects.filter(po_id=po_receive.po_id).first()
    po_order_items = PurchaseReceivedItems.objects.filter(po_receive_id=po_receive_id).all()

    line_items = []

    for po_order_item in po_order_items:

        po_product = Product.objects.filter(product_id=po_order_item.product_id).first()

        po_line_item = PurchaseOrderItem.objects.filter(item_id=po_order_item.item_id).first()


        line_items.append({
            "received_item_id": po_order_item.received_item_id,
            "item_name": po_product.title,
            "sku": po_product.sku,
            "ordered": po_line_item.qty if po_line_item else 0,
            "received": po_order_item.received_qty,
            "in_transit": 0,
            "received_quantity": po_order_item.received_qty,
        })

    vendors_detail = Vendor.objects.filter(id=po_receive.vendor_id).first()
    received_files = PurchaseReceiveFiles.objects.filter(po_receive_id=po_receive_id).all()

    #po_line_items = get_po_line_items(po_order.po_id)
    po_line_items = get_po_line_received_items(po_order.po_id, po_receive_id)

    vendor_po = PurchaseOrderVendor.objects.filter(po_id=po_order.po_id).first()

    tax_total = po_order.tax_total or 0
    surcharge = po_order.surcharge_total or 0
    shipping = po_order.shipping_charge or 0

    final_tax = tax_total + ((surcharge+shipping) * Decimal("0.10"))
    grand_total = po_order.sub_total+po_order.shipping_charge+po_order.surcharge_total+final_tax

    po_shipments = PurchaseOrderShipping.objects.filter(po_id=po_order.po_id).all()

    shipping_providers = ShippingProviders.objects.filter(status=1, is_archived=0).all()
    context = {
        'po_receive_id': po_receive_id,
        'can_complete':can_complete_po(po_order.po_id),
        'po': po_order,
        'shipping_providers': shipping_providers,
        'vendor_po': vendor_po,
        'po_shipments': po_shipments,
        'final_tax_total': final_tax,
        'grand_total': grand_total,
        'po_receive': po_receive,
        "created_by": getUserName(po_receive.created_by),
        'po_line_items': po_line_items.get("line_items"),
        'line_items': line_items,
        'received_files': received_files,
        'vendors_detail': vendors_detail,
    }
    return render(request, 'sbadmin/pages/purchase_receive/edit/edit_pox_form.html', context)
    # edit_po_receive_order


from django.db.models import Sum, Q

def can_complete_po(po_id):
    """
    Returns True if PO can be completed based on business rules
    """

    po = PurchaseOrder.objects.get(po_id=po_id)

    # 🔹 CASE 1: Sub PO → always allow
    if po.parent_po_id:
        return True

    # 🔹 CASE 2: Check if this PO has children
    has_children = PurchaseOrder.objects.filter(parent_po_id=po_id).exists()

    # 🔹 Standalone PO (no children) → allow
    if not has_children:
        return True

    # 🔹 CASE 3: Master PO → check ALL sub POs
    po_ids = list(
        PurchaseOrder.objects.filter(
            Q(po_id=po_id) | Q(parent_po_id=po_id)
        ).values_list("po_id", flat=True)
    )

    totals = PurchaseOrderItem.objects.filter(
        po_id__in=po_ids
    ).aggregate(
        ordered=Sum("ordered_qty"),
        received=Sum("received_qty")
    )

    ordered = totals["ordered"] or 0
    received = totals["received"] or 0

    return received >= ordered


def validate_purchase_order_model(po, line_items):
    rules = [
        ("vendor_id",       "Vendor is required"),
        ("vendor_name",     "Vendor Name is required"),
        ("po_number",       "PO Number is required."),
        ("currency_code",   "Currency Code is required"),
       # ("vendor_reference","Vendor Reference is required"),
        ("warehouse_id",    "Warehouse is required"),
        ("order_date",      "Order Date is required"),
        ("delivery_date",   "Delivery Date is required"),
        ("payment_term_id", "Payment Term is required"),
        ("delivery_name",   "Delivery Name is required"),
        ("address_line1",   "Address Line 1 is required"),
        ("state",           "State is required"),
        ("post_code",       "Postcode is required"),
        ("country_id",      "Country is required"),
        ("tax_percentage",  "Tax Percentage is required"),
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
        #name_validator_none(po.address_line2)
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
    #validate date now its not needed temporarily
    '''
    try:
        date_validator(po.delivery_date, 10)
        date_validator(po.order_date, 10)
    except ValueError as e:
        return False, str(e)
    '''

    return True, ""

@api_view(['POST'])
def place_po(request):
    po_id = request.data.get("po_id")
    if not po_id:
        return JsonResponse({"status":False, "message":"Invalid PO ID."}, status=400)

    po = PurchaseOrder.objects.filter(po_id=po_id).first()
    po.status_id = POStatus.PLACED__PENDING
    po.save(update_fields=["status_id"])

    return JsonResponse({"status":True, "message":"PO Placed"})

from django.db.models import Max
#Product Add New Form - Only GET
@login_required
def create_po_order_receive(request):
    vendors_list = Vendor.objects.all()
    po_next = (PurchaseReceives.objects.aggregate(max_id=Max("po_receive_id")).get("max_id") or 0)+1
    po_receive_number  = f"PR{po_next:04d}"
    context = {
        'vendors': vendors_list,
        'po_receive_number':po_receive_number,
        'po_received_date':datetime.date.today()   }
    
    return render(request, 'sbadmin/pages/purchase_receive/add/add_pox_form.html', context)


from decimal import Decimal, ROUND_HALF_UP


@api_view(["POST"]) 
def generate_po_pdf(request):
    po_id = request.data.get("po_id")
    po_details = PurchaseOrder.objects.filter(po_id=po_id).first()
    if not po_details:
        return HttpResponse("Invalid PO", status=404)

    vendor = Vendor.objects.filter(id=po_details.vendor_id).first()

    vaddress = VendorAddress.objects.filter(
        vendor_id=po_details.vendor_id,
        address_type="billing"
    ).first()

    vendor_billing_address = None
    if vaddress and vaddress.address_id:
        vendor_billing_address = Addresses.objects.filter(id=vaddress.address_id).first()

    # Vendor country fail-safe
    vendor_country = ""
    if vendor_billing_address and getattr(vendor_billing_address, "country_id", None):
        vc = Country.objects.filter(id=vendor_billing_address.country_id).first()
        vendor_country = vc.name if vc else ""

    # Delivery country fail-safe
    delivery_country = ""
    if po_details.country_id:
        dc = Country.objects.filter(id=po_details.country_id).first()
        delivery_country = dc.name if dc else ""

    line_items = PurchaseOrderItem.objects.filter(po_id=po_id).all()
    po_items = []
    for line_item in line_items:
        line_product = Product.objects.filter(product_id=line_item.product_id).first()
        tx_percntge = line_item.tax_percentage
        tx_percntge = format_tax_percentage(tx_percntge)

        disc_percntge = line_item.discount_percentage
        disc_percntge = format_tax_percentage(disc_percntge)

        po_items.append({"name": line_product.title,
                         "qty": line_item.qty,
                         "sku": line_product.sku,
                         "rate": line_item.price,
                         "line_total": line_item.line_total,
                         "tax_percentage": tx_percntge,
                         "disc_percentage": disc_percntge,
                         "amount":line_item.line_total
                         })

    po = {
        "number": po_details.po_number,
        "order_no": po_details.vendor_reference,
        "order_date": po_details.order_date.strftime("%d/%m/%Y"),
        "delivery_date": po_details.delivery_date.strftime("%d/%m/%Y"),
        "ref": po_details.vendor_reference,
        "invoice_number": po_details.po_number,
        "payment_term": PaymentTerm.objects.filter(id=po_details.payment_term_id).first().name if po_details.payment_term_id else "",
        "vendor": {
            "name": po_details.vendor_name,
            "address": f"{vendor_billing_address.street1}\n{vendor_billing_address.street2}\n{vendor_billing_address.city}"
            if vendor_billing_address else "Vendor Address",
            "address2": f"{vendor_billing_address.state} - {vendor_billing_address.zip}, {vendor_billing_address.country.name}"
            if vendor_billing_address else "Vendor Address"
        },
        "deliver_to": {
            "name": po_details.delivery_name,
            "address": f"{po_details.address_line1}\n{po_details.address_line2}\n{po_details.city}\n{po_details.state}\n{delivery_country}-{po_details.post_code}"
        },
        # items: list of dicts with name, qty, rate (numbers)
        "items": po_items
    }
    # ---------- CALCULATIONS ----------
    gst_percent = clean_percent(po_details.tax_percentage) # 10%
    # compute item amounts and totals with Decimal for precision
    subtotal = (po_details.sub_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    #Decimal("0.01"), rounding=ROUND_HALF_UP

    gst_amount = (po_details.tax_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    glbl_tax_percentage = po_details.tax_percentage

    total = (po_details.summary_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    shipping_details = PurchaseOrderShipping.objects.filter(po_id=po_details.po_id).first()

    shipping = (po_details.shipping_charge).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    surcharge = (po_details.surcharge_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    surcharge_total = shipping+surcharge
    

    surcharge_tax_amnt = surcharge_total * (glbl_tax_percentage / 100)
    gst_amount = gst_amount+surcharge_tax_amnt
    total =  gst_amount+surcharge_total+subtotal 
    # ---------- CONTEXT ----------
    context = {
        "po": po,
        "shipping_details": shipping_details,
        "company_name": "SHOPPERBEATS TECHNOLOGIES PTY LTD",
        "company_abn": "Company ID · ABN - 32637549770",
        "company_address": {
            "line": "2/31 Amherst Dr",
            "city": "TRUGANINA",
            "state": "Victoria",
            "postcode": "3029",
            "country": "Australia"
        },
        "company_phone": "0406 958 192",
        "company_fax": "",
        "company_email": "shopperdoornz@gmail.com",
        "company_website": "https://www.shopperbeats.au",
        "logo_url": "https://www.shopperbeats.com/cdn/shop/files/logo_260x_2x_600c8b6c-c0e8-4f59-82df-6a2d9bed69da_260x@2x.jpg",  # swap with your logo
        "subtotal": subtotal,
        "shipping": shipping,
        "surcharge": surcharge,
        "gst_percent": gst_percent,
        "gst_amount": gst_amount,
        "total": total,
    }

    # Render html
    html_string = render_to_string("po_pdftemplates/purchase_order_1.html", context)

    # Generate PDF
    html = HTML(string=html_string)
    #pdf = html.write_pdf(stylesheets=["https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&family=Roboto:ital,wght@0,100..900;1,100..900&display=swap"])
    pdf = html.write_pdf()

    # Return response
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = "inline;  filename=purchase_order.pdf" 
    #inline - inline browser view 
    #attachment - download attachement
    return response  

from decimal import Decimal, InvalidOperation


#PO receive listing
@login_required
def listing(request):
    # ---- Context ----
    context = {
        "user": request.user.id,
    }
    return render(request, 'sbadmin/pages/purchase_receive/all_po_receive_listing.html', context)

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

    size = min(size, 50)  #  max 50 cap

    total = qs.count()
    start = (page - 1) * size
    end = start + size

    data = list(qs.order_by("po_id")[start:end].values(
        "po_id","po_number", "vendor_id", "vendor_code", "vendor_name", "currency_code", "vendor_reference",
        "order_date", "delivery_date", "invoice_date", "delivery_name", "created_at", "status_id", "sub_total", "tax_total",
        "summary_total", "warehouse_name", "vendor_name_val","vendor_name", "subtotal_val", "tax_val", "total_val"
    ))

    last_page = math.ceil(total / size) if total else 1

    #  Return EXACT Tabulator compatible JSON
    return Response({
        "data": data,
        "last_page": last_page,
        "total": total, "row_count":200

    })

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def delete_po_receive(request, po_receive_id):
    try:
        return JsonResponse({"status": False, "message": "Implemented soon!"})
        '''Check PR is linked with the next level order else dont delete - 
        instead archieve dont show in any listing'''
        obj = PurchaseReceives.objects.filter(po_receive_id=po_receive_id).first()
        if not obj:
            return JsonResponse({"status": False, "message": "Details not found"})

        obj.delete()
        PurchaseReceivedItems.objects.filter(po_receive_id=po_receive_id).delete()
        PurchaseReceiveFiles.objects.filter(po_receive_id=po_receive_id).delete()

        return JsonResponse({"status": True, "message": "Contact deleted"})
    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)})

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def delete_po_bill(request, bill_id):
    try:
        return JsonResponse({"status": False, "message": "Implemented soon!"})
        '''Check PR is linked with the next level order else dont delete - 
                instead archieve dont show in any listing'''
        obj = PurchaseBills.objects.filter(id=bill_id).first()
        if not obj:
            return JsonResponse({"status": False, "message": "Details not found"})

        obj.delete()
        PurchaseBillItems.objects.filter(purchase_bill_id=bill_id).delete()
        PurchaseBillFiles.objects.filter(purchase_bill_id=bill_id).delete()

        return JsonResponse({"status": True, "message": " deleted"})
    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def delete_payment(request, payment_id):
    try:
        return JsonResponse({"status":False, "message": "Implemented soon!"})
        with transaction.atomic():

            payment = PurchasePayments.objects.select_for_update().filter(
                id=payment_id
            ).first()

            if not payment:
                return JsonResponse({
                    "status": False,
                    "message": "Payment not found"
                })

            # =====================================
            # CASE 1: DRAFT → HARD DELETE (SAFE)
            # =====================================
            if payment.payment_status == 0:
                PurchasePaymentItems.objects.filter(
                    purchase_payment_id=payment_id
                ).delete()

                PurchasePaymentFiles.objects.filter(
                    purchase_payment_id=payment_id
                ).delete()

                payment.delete()

                return JsonResponse({
                    "status": True,
                    "message": "Draft payment deleted"
                })

            # =====================================
            # CASE 2: COMPLETED → CANCEL (REVERSE)
            # =====================================
            if payment.payment_status == 1:

                vendor_payment = VendorPayments.objects.select_for_update().filter(
                    payment_no=payment.payment_no
                ).first()

                if not vendor_payment:
                    return JsonResponse({
                        "status": False,
                        "message": "Vendor payment not found"
                    })

                # ---------------------------------
                # Reverse bill allocations
                # ---------------------------------
                allocations = VendorPaymentAllocations.objects.filter(
                    payment_id=vendor_payment.vendor_payment_id
                )

                for alloc in allocations:
                    bill = PurchaseBills.objects.select_for_update().get(
                        bill_id=alloc.bill_id
                    )

                    bill.paid_amount -= alloc.amount_applied
                    if bill.paid_amount < 0:
                        bill.paid_amount = Decimal("0.00")

                    bill.pending_amount = bill.bill_amount - bill.paid_amount

                    bill.bill_status = (
                        0 if bill.paid_amount == 0 else 2
                    )

                    bill.save(update_fields=[
                        "paid_amount",
                        "pending_amount",
                        "bill_status"
                    ])

                allocations.delete()

                # ---------------------------------
                # Reverse vendor credits (if any)
                # ---------------------------------
                credits = VendorCredits.objects.filter(
                    source_type="OVERPAYMENT",
                    source_id=vendor_payment.vendor_payment_id
                )

                for credit in credits:
                    if credit.used_amount > 0:
                        return JsonResponse({
                            "status": False,
                            "message": "Payment credit already used. Cannot delete."
                        })
                    credit.delete()

                # ---------------------------------
                # Remove ledger entries
                # ---------------------------------
                VendorLedger.objects.filter(
                    reference_type__in=["PAYMENT", "CREDIT"],
                    reference_id=vendor_payment.vendor_payment_id
                ).delete()

                # ---------------------------------
                # Mark payment as cancelled
                # ---------------------------------
                payment.payment_status = 2  # Cancelled
                payment.save(update_fields=["payment_status"])

                # optional: archive instead of delete
                vendor_payment.delete()

                return JsonResponse({
                    "status": True,
                    "message": "Payment cancelled successfully"
                })

            # =====================================
            # CASE 3: ALREADY CANCELLED
            # =====================================
            return JsonResponse({
                "status": False,
                "message": "Payment already cancelled"
            })

    except Exception as e:
        return JsonResponse({
            "status": False,
            "message": str(e)
        }, status=400)


from django.db import transaction
from django.http import JsonResponse
from decimal import Decimal
import json
def get_top_most_parent_po(po):
    """
    In our DB:
    - Boss parent has parent_po_id = NULL
    - All children directly point to boss
    """
    if po.parent_po_id in (None, "", 0):
        return po

    return PurchaseOrder.objects.filter(
        po_id=po.parent_po_id
    ).first()

def is_parent_po_fully_received(parent_po_id):
    po_ids = (
        PurchaseOrder.objects
        .filter(
            Q(po_id=parent_po_id) |
            Q(parent_po_id=parent_po_id)
        )
        .values_list("po_id", flat=True)
    )

    if not po_ids:
        return False

    totals = PurchaseOrderItem.objects.filter(
        po_id__in=po_ids
    ).aggregate(
        total_ordered_qty=Sum("ordered_qty"),
        total_received_qty=Sum("received_qty")
    )

    ordered_qty = totals["total_ordered_qty"] or 0
    received_qty = totals["total_received_qty"] or 0

    return ordered_qty == received_qty




def save_po_receive_full(request):
    return JsonResponse(
        {"status": True, "message": "PO receive completed successfully"}
    )

#PO Complete - action btn
#split receive completed
def save_po_receive_split_complete(request):
    # 1. Catch the raw JSON payload from the request body
    try:
        raw_data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    po_id = raw_data.get("po_id")
    po_receive_id = raw_data.get("po_receive_id")
    # This matches the "lineItems" key in your provided JSON payload
    line_items_data = raw_data.get("lineItems", [])

    original_receive = PurchaseReceives.objects.filter(po_receive_id=po_receive_id).first()

    try:
        po = PurchaseOrder.objects.get(po_id=po_id)
        po_order_items = PurchaseOrderItem.objects.filter(po_id=po_id)
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({"error": "Purchase Order not found"}, status=404)

    for item in po_order_items:
        if item.ordered_qty != item.received_qty:
            return JsonResponse({"status":False, "error": "This has pending receive, Can not complete this order"}, status=404)
    # 3. Create lookup for received quantities
    received_lookup = {
        item['row_item']['id']: item['received_qty']
        for item in line_items_data
    }

    with transaction.atomic():
        # --- Complete received ---
        original_receive.updated_by = request.user.id
        original_receive.updated_at = timezone.now()
        original_receive.is_completed = 1

        po.status_id = POStatus.CLOSED_DELIVERED

        #get the parent  PO and change the order status
        #check order has pending qty all completed then set completed state else keep the prev state
        po.updated_at = timezone.now()
        po.updated_by = request.user.id
        po.save()

        # get the parent  PO and change the order status
        # check order has pending qty all completed then set completed state else keep the prev state
        top_parent_po = get_top_most_parent_po(po)

        # Update ONLY the top-most parent PO
        if top_parent_po:
            if is_parent_po_fully_received(top_parent_po.po_id):
                top_parent_po.status_id = POStatus.DELIVERED__DELIVERED
                top_parent_po.save(update_fields=["status_id"])

        original_receive.save(update_fields=['is_completed', 'updated_by', 'updated_at'])
        # --- STEP C: Finalize Master Totals ---

    return JsonResponse({"status": True, "message": "PO-Split received completed successfully"})


# btn split receipt
# save_split_receive
@csrf_exempt
@login_required
def save_po_receive(request):
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"status": False, "message": "Invalid JSON"}, status=400)

    po_id = payload.get("po_id")
    po_receive_id = payload.get("po_receive_id")
    comments = payload.get("comments")
    line_items = payload.get("lineItems", [])

    if not po_id or not po_receive_id:
        return JsonResponse({
            "status": False,
            "message": "PO ID and PO Receive ID are required"
        }, status=400)

    try:
        po = PurchaseOrder.objects.get(po_id=po_id)
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({"status": False, "message": "Purchase Order not found"}, status=404)

    po_items = PurchaseOrderItem.objects.filter(po_id=po_id)

    received_lookup = {
        i["row_item"]["id"]: Decimal(str(i.get("received_qty", 0)))
        for i in line_items
    }

    with transaction.atomic():

        # LOCK RECEIVE
        try:
            receive = PurchaseReceives.objects.select_for_update().get(
                po_receive_id=po_receive_id,
                po_id=po_id
            )
        except PurchaseReceives.DoesNotExist:
            return JsonResponse({
                "status": False,
                "message": "Purchase Receive not found"
            }, status=404)

        add_summary = Decimal("0")
        add_sub_total = Decimal("0")
        add_tax_total = Decimal("0")

        # ======================================================
        # PROCESS ITEMS (DELTA QTY ONLY)
        # ======================================================
        for item in po_items.select_for_update():
            entered_qty = received_lookup.get(item.product_id, Decimal("0"))

            if entered_qty <= 0:
                continue

            #  STRICT VALIDATION — ONLY PENDING QTY
            if entered_qty > item.qty:
                return JsonResponse({
                    "status": False,
                    "message": (
                        f"Cannot receive {entered_qty}. "
                        f"Only {item.pending_qty} pending for product {item.product_id}"
                    )
                }, status=400)

            # ---- Amount calculation (unchanged) ----
            price = Decimal(str(item.price))
            tax_pct = Decimal(str(item.tax_percentage))
            disc_pct = Decimal(str(item.discount_percentage))

            subtotal = entered_qty * price
            discount_amt = (subtotal * disc_pct) / Decimal("100")
            taxable = subtotal - discount_amt
            tax_amt = (taxable * tax_pct) / Decimal("100")
            line_total = taxable + tax_amt

            # ---- UPDATE EXISTING RECEIVE ITEM ONLY ----
            try:
                pri = PurchaseReceivedItems.objects.select_for_update().get(
                    po_receive_id=receive.po_receive_id,
                    product_id=item.product_id
                )
            except PurchaseReceivedItems.DoesNotExist:
                return JsonResponse({
                    "status": False,
                    "message": f"Receive item missing for product {item.product_id}"
                }, status=400)

            #  ADD DELTA
            pri.received_qty = entered_qty
            pri.save(update_fields=["received_qty"])

            #  UPDATE PO ITEM BALANCE (SOURCE OF TRUTH)
            item.received_qty = entered_qty
            item.pending_qty = item.qty - entered_qty
            item.save(update_fields=["received_qty", "pending_qty"])

            add_summary += line_total
            add_sub_total += subtotal
            add_tax_total += tax_amt

        # ======================================================
        # UPDATE RECEIVE TOTALS
        # ======================================================
        receive.summary_total = (receive.summary_total or Decimal("0")) + add_summary
        receive.sub_total = (receive.sub_total or Decimal("0")) + add_sub_total
        receive.tax_total = (receive.tax_total or Decimal("0")) + add_tax_total
        receive.internal_ref_notes = comments
        receive.updated_by = request.user.id
        receive.updated_at = timezone.now()

        receive.save(update_fields=[
            "summary_total",
            "sub_total",
            "tax_total",
            "internal_ref_notes",
            "updated_by",
            "updated_at"
        ])

        # ======================================================
        # SHIPPING / RECEIVE STATUS (CORRECT)
        # ======================================================
        receive_items = PurchaseReceivedItems.objects.filter(
            po_receive_id=po_receive_id
        )

        all_received = True
        for ri in receive_items:
            po_item = PurchaseOrderItem.objects.get(item_id=ri.item_id)
            if ri.received_qty < po_item.qty:
                all_received = False
                break

        receive.status_id = (
            POShippingStatus.ALL_RECEIVED
            if all_received
            else POShippingStatus.PARTIALLY_DELIVERED
        )
        receive.save(update_fields=["status_id"])

        # ======================================================
        # UPDATE PO STATUS (CORRECT)
        # ======================================================
        if not po_items.filter(pending_qty__gt=0).exists():
            po.status_id = POStatus.DELIVERED__DELIVERED
        else:
            po.status_id = POStatus.PARTIALLY_DELIVERED__PARTIALLY_DELIVERED

        po.comments = comments
        po.save(update_fields=["status_id", "comments"])

    return JsonResponse({
        "status": True,
        "message": "Receive updated successfully",
        "po_receive_id": receive.po_receive_id
    })

from django.db import connection
def get_shipping_details(request, po_id):
    po_receive = PurchaseReceives.objects.filter(po_id=po_id).first()
    if not po_receive:
        return JsonResponse({"data": []})

    sql = """SELECT
        shipd.tracking_number,
        shipd.provider,
        shipd.po_id,
        shipd.receive_id,
        MIN(shipd.shipped_date)  AS shipped_date,
        MAX(shipd.received_date) AS received_date,
    
        JSON_ARRAYAGG(
            JSON_OBJECT(
                'product_id', shipd.po_item_id,
                'received_qty', rcve.received_qty
            )
        ) AS items
    
    FROM store_admin_purchase_order_shipping_details AS shipd
    LEFT JOIN store_admin_purchase_received_items AS rcve
        ON rcve.po_receive_id = shipd.receive_id
       AND rcve.product_id   = shipd.po_item_id
    
    WHERE shipd.is_archived = 0
      AND shipd.receive_id = %s
    
    GROUP BY
        shipd.tracking_number,
        shipd.provider,
        shipd.po_id,
        shipd.receive_id
    
    ORDER BY shipped_date;"""
    data = []
    with connection.cursor() as cursor:
        cursor.execute(sql, [po_receive.po_receive_id])

        #  IMPORTANT SAFETY CHECK
        if cursor.description is None:
            return JsonResponse({"data": []})

        for row in cursor.fetchall():
            tracking_number = row[0]
            provider = row[1]
            po_id = row[2]
            receive_id = row[3]
            shipped_date = row[4]
            received_date = row[5]

            items = row[6] or []
            if isinstance(items, str):
                items = json.loads(items)
            provider_name = ""
            provider_link = None
            if provider:
                sh_provider = ShippingProviders.objects.filter(carrier_id=provider).first()
                provider_link = sh_provider.tracking_url
                provider_name = sh_provider.carrier_name
                provider_link = provider_link.replace("{0}", tracking_number)

            data_items = []
            for item in items:
                product_id = item["product_id"]
                if product_id:
                    po_product = Product.objects.filter(product_id=product_id).first()

                data_items.append({
                    "product_name": po_product.title,
                    "vendor_sku": po_product.sku,
                    "received_qty": item["received_qty"],
                })

            data.append({
                "tracking_number":  f"<a class='link' target='_blank' href='{provider_link}'>{tracking_number}</a>",
                "provider": provider_name,
                "po_id": po_id,
                "receive_id": receive_id,
                "shipped_date": shipped_date,
                "received_date": received_date,
                "line_items": data_items,
            })
        return JsonResponse({"status":True, "message":"", "data":data})


def get_po_invoice_details(request, po_id):
    po_receives = PurchaseReceives.objects.filter(po_id=po_id).first()
    if not po_receives:
        return JsonResponse({"data": []})

    po_received_items = PurchaseReceivedItems.objects.filter(po_receive_id=po_receives.po_receive_id).all()

    data = []
    for po_received_item in po_received_items:
        po_product = Product.objects.filter(product_id=po_received_item.product_id).first()
        data_items = []
        po_vendor_invoices = PurchaseOrderInvoiceDetails.objects.filter(
            receive_id=po_received_item.po_receive_id,
            po_item_id=po_received_item.product_id
        ).all()

        #print(po_received_item.product_id)
        for po_vendor_invoice in po_vendor_invoices:
            data_items.append({
                "po_invoice_id": po_vendor_invoice.po_invoice_id,
                "po_id": po_vendor_invoice.po_id,
                "product_id": po_vendor_invoice.product_id,
                "receive_id": po_vendor_invoice.receive_id,
                "invoice_number": po_vendor_invoice.invoice_number,
                "po_amount": po_vendor_invoice.po_amount,
                "received_qty": po_vendor_invoice.received_qty,
                "payment_status_id": po_vendor_invoice.payment_status_id,
                "order_date": po_vendor_invoice.order_date,
                "order_no": po_vendor_invoice.order_no,
                "vendor_ref_no": po_vendor_invoice.vendor_ref_no,
                "delivery_ref": po_vendor_invoice.delivery_ref,
                "payment_term_id": po_vendor_invoice.payment_term_id,
                "invoice_date": po_vendor_invoice.invoice_date,
                "due_date": po_vendor_invoice.due_date,
                "paid_date": po_vendor_invoice.paid_date,
            })

        if len(data_items) >= 1:
            data.append({
                "product_name": po_product.title,
                "sku": po_product.sku,
                "received_qty": po_received_item.received_qty,
                "received_status": po_received_item.status_id,
                "line_items": data_items,
            })

    return JsonResponse({"status": True, "message": "", "data": data})


@login_required
def intransit_listing(request):
    # ---- Context ----
    all_vendors = Vendor.objects.all()

    context = {
        "vendors":all_vendors,
        "user": request.user.id,
    }

    return render(request, 'sbadmin/pages/bills/all_po_intransit_listing.html', context)


@login_required
def intransit_po_listing_json(request):
    po_id = request.GET.get("po_id")
    po_order = request.GET.get("po_order")
    vendor_id = request.GET.get("vendor_id")
    tracking_no = request.GET.get("tracking_no")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    sql = """
        SELECT
            -- Purchase Order
            po.po_id,
            po.po_number,

            -- Vendor
            v.id AS vendor_id,
            v.display_name AS vendor_name,

            -- Purchase Receive (Header)
            pr.po_receive_id,
            pr.po_receive_number,
            pr.received_date,
            po.order_date,
            pr.shipping_date,
            pr.created_at AS receive_created_at,

            -- Purchase Receive Items
            pri.received_item_id,
            pri.product_id,
            pri.item_id,
            pri.received_qty,
            pri.status_id AS received_status,

            -- PO Item
            poi.ordered_qty,

            -- Product
            p.product_id,
            p.title AS product_name,
            p.sku AS product_sku

        FROM store_admin_purchase_receives pr

        JOIN store_admin_purchase_received_items pri
            ON pri.po_receive_id = pr.po_receive_id

        JOIN store_admin_purchase_orders po
            ON po.po_id = pr.po_id

        JOIN store_admin_purchase_order_items poi
            ON poi.po_id = pr.po_id
           AND poi.product_id = pri.product_id

        LEFT JOIN store_admin_vendor v
            ON v.id = pr.vendor_id

        LEFT JOIN store_admin_product p
            ON p.product_id = pri.product_id

        LEFT JOIN store_admin_purchase_order_shipping_details sh
            ON sh.po_id = pr.po_id
           AND sh.po_item_id = pri.item_id
           AND sh.receive_id = pr.po_receive_id

        WHERE po.status_id IN (1, 2, 3, 4)
          AND poi.ordered_qty <> pri.received_qty
    """

    params = []

    if po_id:
        sql += " AND pr.po_id = %s"
        params.append(po_id)

    if po_order:
        sql += " AND po.po_number LIKE  %s"
        params.append(f"%{po_order}%")

    if vendor_id:
        sql += " AND po.vendor_id = %s"
        params.append(vendor_id)

    if tracking_no:
        sql += """
            AND EXISTS (
                SELECT 1
                FROM store_admin_purchase_order_shipping_details sh
                WHERE sh.po_item_id = pri.product_id AND sh.po_id = pr.po_id 
                  AND sh.tracking_number LIKE %s
            )
        """
        params.append(f"%{tracking_no}%")

    if date_from:
        sql += """
            AND EXISTS (
                SELECT 1
                FROM store_admin_purchase_order_shipping_details sh
                WHERE sh.po_item_id = pri.product_id
                  AND sh.po_id = pr.po_id
                  AND sh.received_date >= %s
            )
        """
        params.append(date_from)

    if date_to:
        sql += """
            AND EXISTS (
                SELECT 1
                FROM store_admin_purchase_order_shipping_details sh
                WHERE sh.po_item_id = pri.product_id
                  AND sh.po_id = pr.po_id
                  AND sh.received_date <= %s
            )
        """
        params.append(date_to)

    sql += " ORDER BY pr.po_receive_id DESC"

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()

    data = [dict(zip(columns, row)) for row in rows]

    for detas in data:
        po_id = detas.get("po_id")
        product_id = detas.get("product_id")
        po_receive_id = detas.get("po_receive_id")
        print(po_receive_id)

    if tracking_no:
        print(tracking_no)

    return JsonResponse({
        "status": True,
        "data": data
    })

