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
    VendorPaymentAllocations, VendorCredits, VendorLedger, POShippingStatus, PurchaseOrderPrimaryDetails
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
from store_admin.views.purchase_orders.purchase_orders_view import get_po_line_items
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
            "item_name": po_product.title,
            "sku": po_product.sku,
            "ordered": po_line_item.qty if po_line_item else 0,
            "received": po_order_item.received_qty,
            "in_transit": 0,
            "received_quantity": 0,  # po_order_item.received_qty,
        })
    vendors_detail = Vendor.objects.filter(id=po_receive.vendor_id).first()
    received_files = PurchaseReceiveFiles.objects.filter(po_receive_id=po_receive_id).all()

    po_line_items = get_po_line_items(po_order.po_id)
    vendor_po = PurchaseOrderVendor.objects.filter(po_id=po_order.po_id).first()

    tax_total = po_order.tax_total or 0
    surcharge = po_order.surcharge_total or 0
    shipping = po_order.shipping_charge or 0

    final_tax = tax_total + ((surcharge+shipping) * Decimal("0.10"))
    grand_total = po_order.sub_total+po_order.shipping_charge+po_order.surcharge_total+final_tax

    po_shipments = PurchaseOrderShipping.objects.filter(po_id=po_order.po_id).all()
    has_child_is_master = False
    if po_order.parent_po_id  in ("", None, 0 ):
        has_child_is_master = PurchaseOrder.objects.filter(parent_po_id=po_order.parent_po_id).exists()

    shipping_providers = ShippingProviders.objects.filter(status=1, is_archived=0).all()
    context = {
        'po_receive_id': po_receive_id,
        'can_complete':can_complete_po(po_order.po_id),
        'po': po_order,
        'shipping_providers': shipping_providers,
        'has_child_is_master': has_child_is_master,
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



#btn split receipt
#save_split_receive
def save_po_receive_split(request):
    # 1. Catch the raw JSON payload from the request body
    try:
        raw_data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    po_id = raw_data.get("po_id")

    # This matches the "lineItems" key in your provided JSON payload
    line_items_data = raw_data.get("lineItems", [])
    # 2. Fetch original records
    try:
        po = PurchaseOrder.objects.get(po_id=po_id)
        po_order_items = PurchaseOrderItem.objects.filter(po_id=po_id)
        parent_po = get_top_most_parent_po(po)
        print(parent_po)
        #return JsonResponse({})

    except PurchaseOrder.DoesNotExist:
        return JsonResponse({"error": "Purchase Order not found"}, status=404)

    original_receive = PurchaseReceives.objects.filter(po_id=po_id).first()
    #po_receive_items = PurchaseReceivedItems.objects.filter(po_receive_id=original_receive.po_receive_id)

    # 3. Create lookup for received quantities
    received_lookup = {
        item['row_item']['id']: item['received_qty']
        for item in line_items_data
    }

    # 1. Ensure the list isn't empty
    # 2. Check if all items are zero
    if not line_items_data or all(line_item.get('received_qty', 0) == 0 for line_item in line_items_data):
        return JsonResponse({
            "status": False,
            "message": "Error: At least one item must have a received quantity greater than zero."
        }, status=400)  # Changed from 404 to 400

    sub_po_vendor = PurchaseOrderVendor.objects.filter(po_id=po_id).first()

    with transaction.atomic():
        # --- STEP A: Create Sub PO (Backorder) ---

        sub_po = PurchaseOrder.objects.get(po_id=po_id)
        sub_po.pk = None
        base_po = po.po_number.split("-")[0]

        existing_sub_pos = (
            PurchaseOrder.objects
            .filter(po_number__startswith=f"{base_po}-")
            .values_list("po_number", flat=True)
        )

        max_no = 0
        for po_no in existing_sub_pos:
            try:
                suffix = int(po_no.split("-")[-1])
                max_no = max(max_no, suffix)
            except ValueError:
                pass

        next_no = max_no + 1
        sub_po.po_number = f"{base_po}-{next_no}"

        #sub_po.po_number = f"{po.po_number}-1"
        sub_po.status_id = POStatus.PLACED__PENDING
        sub_po.parent_po_id = parent_po.po_id
        sub_po.save()


        #create po vendor
        #sub_po_vendor.pk = None
        #sub_po_vendor.po_id = sub_po.po_id
        #sub_po_vendor.po_number = sub_po.po_number
        #sub_po_vendor.save()

        # --- 2. CLONE PURCHASE RECEIVE (The Receipt Record) ---
        new_receive = None
        if original_receive:
            new_receive = original_receive
            new_receive.pk = None
            new_receive.po_id = sub_po.po_id  # Link to the new Sub-PO
            new_receive.po_number = sub_po.po_number
            # New receipt number suffix
            new_receive.po_receive_number = f"{original_receive.po_receive_number}/1"
            new_receive.save()

        current_po_summary = Decimal('0')
        sub_po_summary = Decimal('0')

        sub_total = 0
        tax_total = 0
        # --- STEP B: Process Items ---
        for item in po_order_items:
            original_qty = Decimal(str(item.qty))
            # Get received qty from payload lookup
            received_qty = Decimal(str(received_lookup.get(item.product_id, 0)))
            remaining_qty = original_qty - received_qty

            price = Decimal(str(item.price))
            tax_pct = Decimal(str(item.tax_percentage))
            disc_pct = Decimal(str(item.discount_percentage))

            # 1. Update ORIGINAL ITEM (The Received portion)
            item.qty = received_qty
            item.ordered_qty = received_qty
            item.received_qty = received_qty
            item.pending_qty = 0

            # Recalculate financial fields
            item.subtotal = item.qty * price
            item.discount_amt = (item.subtotal * disc_pct) / Decimal('100')
            taxable = item.subtotal - item.discount_amt
            item.tax_amount = (taxable * tax_pct) / Decimal('100')
            item.line_total = taxable + item.tax_amount
            item.save()

            # UPDATE EXISTING PURCHASE RECEIVED ITEM
            if original_receive:
                pri, created = PurchaseReceivedItems.objects.get_or_create(
                    po_receive_id=original_receive.po_receive_id,
                    product_id=item.product_id,
                    defaults={
                        "item_id": item.item_id,
                        "received_qty": received_qty,
                        "status_id": 1
                    }
                )

                if not created:
                    pri.received_qty = received_qty  #  even if 0
                    pri.save(update_fields=["received_qty"])

            current_po_summary += item.line_total
            tax_total += item.tax_amount
            sub_total += item.subtotal
            # 2. Create SUB ITEM (The Back ordered portion)
            if remaining_qty >= 0:
                new_sub_item = PurchaseOrderItem.objects.get(item_id=item.item_id)
                new_sub_item.pk = None
                new_sub_item.po_id = sub_po.po_id
                new_sub_item.qty = remaining_qty
                new_sub_item.received_qty = 0
                new_sub_item.pending_qty = remaining_qty

                # Recalculate financial fields
                new_sub_item.subtotal = remaining_qty * price
                new_sub_item.discount_amt = (new_sub_item.subtotal * disc_pct) / Decimal('100')
                sub_taxable = new_sub_item.subtotal - new_sub_item.discount_amt
                new_sub_item.tax_amount = (sub_taxable * tax_pct) / Decimal('100')
                new_sub_item.line_total = sub_taxable + new_sub_item.tax_amount
                new_sub_item.save()
                sub_po_summary += new_sub_item.line_total

                # C. Create SUB RECEIVED ITEM (The record of remaining qty)
                if new_receive:
                    PurchaseReceivedItems.objects.create(
                        po_receive_id=new_receive.po_receive_id,
                        product_id=item.product_id,
                        item_id=new_sub_item.item_id,  # Linked to the new backorder item
                        received_qty=0,  # Not received yet in the sub-po
                        status_id=0
                    )

        # --- STEP C: Finalize Master Totals ---
        po.summary_total = current_po_summary
        po.sub_total = sub_total
        po.tax_total = tax_total
        po.updated_by = request.user.id
        po.updated_at = timezone.now()

        po.status_id = POStatus.DELIVERED__DELIVERED
        po.save()

        # Get the parent PO and set the status
        sub_po.summary_total = sub_po_summary
        sub_po.save()
        #clone po vendor details
        #create purchase receive
        primary_po = get_top_most_parent_po(po)
        if primary_po:
            po_primary_details = PurchaseOrderPrimaryDetails.objects.get(po_id=primary_po.po_id)
            if po_primary_details:
                po_primary_details.status_id = POStatus.PARTIALLY_DELIVERED__PARTIALLY_DELIVERED
                po_primary_details.save()


    return JsonResponse({"status": True, "message":"PO-Split created successfully", "new_po": sub_po.po_number})


def save_po_receive_full(request):
    try:
        raw_data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    po_id = raw_data.get("po_id")
    line_items_data = raw_data.get("lineItems", [])

    try:
        po = PurchaseOrder.objects.get(po_id=po_id)
        po_order_items = PurchaseOrderItem.objects.filter(po_id=po_id)
        parent_po = get_top_most_parent_po(po)

    except PurchaseOrder.DoesNotExist:
        return JsonResponse({"error": "Purchase Order not found"}, status=404)

    #  Purchase Receive MUST exist
    original_receive = PurchaseReceives.objects.filter(po_id=po_id).first()
    if not original_receive:
        return JsonResponse(
            {"error": "Purchase Receive record does not exist"},
            status=400
        )

    # product_id → received_qty
    received_lookup = {
        item["row_item"]["id"]: Decimal(str(item["received_qty"]))
        for item in line_items_data
    }

    with transaction.atomic():
        sub_total = Decimal("0")
        tax_total = Decimal("0")
        summary_total = Decimal("0")

        for item in po_order_items:
            original_qty = Decimal(str(item.qty))
            received_qty = received_lookup.get(item.product_id, Decimal("0"))

            #  FULL RECEIVE VALIDATION
            if received_qty != original_qty:
                return JsonResponse(
                    {"error": "Partial quantity detected. Use Split Receive."},
                    status=400
                )

            price = Decimal(str(item.price))
            tax_pct = Decimal(str(item.tax_percentage))
            disc_pct = Decimal(str(item.discount_percentage))

            # ---- Update PO Item ----
            item.qty = original_qty
            item.ordered_qty = original_qty
            item.received_qty = original_qty
            item.pending_qty = 0

            item.subtotal = original_qty * price
            item.discount_amt = (item.subtotal * disc_pct) / Decimal("100")
            taxable = item.subtotal - item.discount_amt
            item.tax_amount = (taxable * tax_pct) / Decimal("100")
            item.line_total = taxable + item.tax_amount
            item.save()

            # PurchaseReceivedItems MUST exist
            try:
                pri = PurchaseReceivedItems.objects.get(
                    po_receive_id=original_receive.po_receive_id,
                    product_id=item.product_id,
                    item_id=item.item_id
                )
            except PurchaseReceivedItems.DoesNotExist:
                raise ValueError(
                    f"Missing PurchaseReceivedItem for product {item.product_id}"
                )

            # Update even if qty = 0
            pri.received_qty = original_qty
            pri.status_id = 1
            pri.save(update_fields=["received_qty", "status_id"])

            sub_total += item.subtotal
            tax_total += item.tax_amount
            summary_total += item.line_total

        # ---- Finalize PO ----
        po.sub_total = sub_total
        po.tax_total = tax_total
        po.summary_total = summary_total
        po.updated_by = request.user.id
        po.updated_at = timezone.now()
        po.status_id = POStatus.DELIVERED__DELIVERED #received full
        po.save()

        #check all po has fully received
        if is_parent_po_fully_received(parent_po.po_id):
            parent_po.status_id = POStatus.DELIVERED__DELIVERED
            parent_po.save(update_fields=["status_id"])

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
