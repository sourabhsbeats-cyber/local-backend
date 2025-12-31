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

from store_admin.helpers import name_validator, name_validator_none, reference_validator, date_validator, zip_validator, \
    get_prep_label, format_tax_percentage, parse_date_or_none
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.address_model import Addresses
from django.db import transaction
from django.db.models import Value as V
from django.db.models.functions import Concat
from django.urls import reverse
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

from store_admin.models.po_models.po_models import PurchaseOrder, POReceiveStatus, PurchaseOrderItem, \
    PurchaseReceiveFiles, \
    PurchaseReceivedItems, PurchaseReceives, PurchaseOrderShipping, PurchaseOrderVendor, PurchaseBills, \
    PurchaseBillItems, PurchaseBillFiles, PurchasePayments, PurchasePaymentItems, PurchasePaymentFiles, VendorPayments, \
    VendorPaymentAllocations, VendorCredits, VendorLedger
from store_admin.models.product_model import Product, ProductShippingDetails, ProductPriceDetails, \
    ProductStaticAttributes, ProductDynamicAttributes, ProductImages
from store_admin.models.setting_model import Category, Brand, Manufacturer, AttributeDefinition, UnitOfMeasurements
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
from store_admin.views.purchase_orders.purchase_orders_view import getUserName, get_po_line_items
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
            po_vendor.invoice_ref_number = data.get("vendor_po_invoice_no")
            po_vendor.delivery_ref_number = data.get("vendor_po_delivery_ref_no")
            po_vendor.invoice_date = parse_date_or_none(data.get("vendor_po_invoice_date"))
            po_vendor.invoice_due_date = parse_date_or_none(data.get("vendor_po_invoice_due_date"))
            po_vendor.save()
        else:
            PurchaseOrderVendor.objects.create(
                po_id=po_id,
                po_number=data.get("vendor_po_no"),
                order_date=parse_date_or_none(data.get("vendor_po_order_date")),
                invoice_ref_number=data.get("vendor_po_invoice_no"),
                delivery_ref_number=data.get("vendor_po_delivery_ref_no"),
                invoice_date=parse_date_or_none(data.get("vendor_po_invoice_date")),
                invoice_due_date=parse_date_or_none(data.get("vendor_po_invoice_due_date")),
                created_by=user_id
            )

        #insert all shipping
        shipping_providers = data.get("shipping_provider", [])
        shipping_tracking_nos = data.get("shipping_tracking_no", [])
        print(shipping_providers)
        with transaction.atomic():
            # 1. delete all existing records
            PurchaseOrderShipping.objects.filter(po_id=po_id).delete()
            # 2. prepare new records
            shipping_objs = [
                PurchaseOrderShipping(
                    po_id=po_id,
                    provider=provider,
                    tracking_number=tracking,
                    created_by=request.user.id
                )
                for provider, tracking in zip(shipping_providers, shipping_tracking_nos)
                if provider and tracking
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
    print(line_items)

    po_line_items = get_po_line_items(po_order.po_id)
    vendor_po = PurchaseOrderVendor.objects.filter(po_id=po_order.po_id).first()

    tax_total = po_order.tax_total or 0
    surcharge = po_order.surcharge_total or 0
    shipping = po_order.shipping_charge or 0

    final_tax = tax_total + ((surcharge+shipping) * Decimal("0.10"))
    grand_total = po_order.sub_total+po_order.shipping_charge+po_order.surcharge_total+final_tax

    po_shipments = PurchaseOrderShipping.objects.filter(po_id=po_order.po_id).all()
    context = {
        'po_receive_id': po_receive_id,
        'po': po_order,
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


def validate_purchase_order_model(po, line_items):
    rules = [
        ("vendor_id",       "Vendor is required"),
        ("vendor_name",     "Vendor Name is required"),
        ("po_number",       "PO Number is required."),
        ("currency_code",   "Currency Code is required"),
        ("vendor_reference","Vendor Reference is required"),
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
