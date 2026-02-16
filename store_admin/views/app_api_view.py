import datetime
from time import timezone

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.expressions import d
from django.urls import reverse

from store_admin.helpers import name_validator_none,getUserName, reference_validator, zip_validator, \
    get_prep_label, format_tax_percentage, validate_purchase_order_model, safe_df
from store_admin.models.organization_model import OrganizationInventoryLocation
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.address_model import Addresses
from django.db import transaction
from django.shortcuts import render, redirect
from store_admin.models.po_models.po_models import (PurchaseOrder, PurchaseOrderItem,
                                                    PurchaseOrderShipping, \
                                                    PurchaseOrderVendorDetails, PurchaseReceives, PurchaseReceivedItems,
                                                    PurchaseBills, PurchaseBillItems, PurchasePayments, POStatus,
                                                    PurchaseOrderFiles, POShippingStatus, PurchaseOrderPrimaryDetails,
                                                    PurchaseOrderInvoiceDetails, po_status_list)
from store_admin.models.product_model import Product, ProductImages
from store_admin.models.setting_model import UnitOfMeasurements, ShippingProviders
from store_admin.models.vendor_models import Vendor, VendorAddress
from django.db.models import Min, Sum, F, Max, IntegerField, Exists, CharField, Aggregate, Func
from store_admin.models import Country, StoreUser
from store_admin.models.warehouse_setting_model import Warehouse
from django.templatetags.static import static
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import math
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from rest_framework.renderers import JSONRenderer
from rest_framework.decorators import renderer_classes
from rest_framework.decorators import permission_classes
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.template.loader import render_to_string
from django.http import HttpResponse
from weasyprint import HTML
from django.db.models import OuterRef, Subquery, Value, TextField, DecimalField
from django.db.models.functions import Coalesce, Concat
from decimal import ROUND_HALF_UP
from store_admin.views.libs.common import clean_percent
from store_admin.views.serializers.product_serializers import ProductImageSerializer
from decimal import Decimal, InvalidOperation


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
@login_required
def api_all_shipping_providers(request):
    shipping_providers = ShippingProviders.objects.values(
        "carrier_name",
        "carrier_id",
        "carrier_code",
        "class_code",
        "tracking_url",
        "status",
        "is_archived",
    )
    return JsonResponse({
        "status": True,
        "data": list(shipping_providers),
        "message": ""
    })


@api_view(["GET"])
def api_all_payment_terms(request):
    payment_terms = PaymentTerm.objects.filter(status=1).values(
        "name",
        "frequency",
        "id",
    )
    return JsonResponse({"status":True, "data":list(payment_terms), "message":""})

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
@login_required
def create_po_api_order(request):
    po = PurchaseOrder.objects.create(
        vendor_code="",
        vendor_name="",
        created_by=request.user.id,
        tax_percentage=10.0,
        status_id=POStatus.DRAFT__PENDING  # Created / Draft
    )
    po_number = f"PO{po.po_id:04d}"

    #  Update the record with PO number
    po.po_number = po_number
    po.save()
    return JsonResponse({"status":True, "data":{"po_id":po.po_id}, "message":"PO Created"})


def get_po_details(request, po_id):
    po = PurchaseOrder.objects.filter(po_id=po_id, is_archived=0).first()
    if not po:
        return JsonResponse({"status":False, "message":"Invalid PO" })

    # category = Category.objects.filter(status=1).all()
    #warehouses = Warehouse.objects.all()
    # unit_of_measures = UnitOfMeasurements.objects.all()
    # vendors = Vendor.objects.filter(status=1).all()
    # countries_list = Country.objects.values('name', 'id', 'currency')
    # currency_list = Country.objects.values('currency').annotate(
    #     id=Min('id'),  # pick country with smallest ID per currency
    #     currency_name=Min('currency_name')
    # )
    po_order_items = PurchaseOrderItem.objects.filter(po_id=po_id).all()

    line_items = []

    NO_IMAGE = static("no_product_image.png")
    # Build Response

    for po_order_item in po_order_items:
        po_product = Product.objects.filter(product_id=po_order_item.product_id).first()
        po_images = ProductImages.objects.filter(product_id=po_order_item.product_id).order_by(
            "product_image_id").first()
        line_items.append({
            "row_item": {
                "id": po_product.product_id,
                "title": po_product.title,
                "image": po_images.cdn_url if po_images else NO_IMAGE,
                "stock_qty": 0,  # if you have stock, replace 0
                "sku": po_product.sku,
                "asin": po_product.asin, "fnsku": po_product.fnsku, "ean": po_product.ean,
                "prep_type": get_prep_label(po_product.prep_type),
                "product_order_type": po_order_item.order_type,  # send as number for JS
                "product_order_ref": po_order_item.order_ref,  # send as number for JS
                "is_taxfree": True if po_product.is_taxable else False,
            },
            "barcode_label_type": po_product.barcode_label_type,
            "qty": int(po_order_item.qty),
            "price": float(po_order_item.price),
            "discount": float(po_order_item.discount_percentage),
            "tax": float(po_order_item.tax_percentage),
            "tax_amount": float(po_order_item.tax_amount),
            "sub_total": float(po_order_item.subtotal),
            "line_total": float(po_order_item.line_total),
        })

    can_pdf_generate, err_msg = validate_purchase_order_model(po, line_items)
    #payment_terms = PaymentTerm.objects.all()

    #shipping_details = PurchaseOrderShipping.objects.filter(po_id=po.po_id).all()
    po_vendor_details = PurchaseOrderVendorDetails.objects.filter(po_id=po_id).all()
    #shipping_providers = ShippingProviders.objects.filter(is_archived=0, status=1).all()
    #warehouse locations
    #warehouse_locations = OrganizationInventoryLocation.objects.filter(organization_id=1).all()
    context = {
        "po_id": po_id,
        "can_pdf_generate":can_pdf_generate,
        "po": {
            "created_by_name" : getUserName(po.created_by),
            "created_at": po.created_at.strftime("%b %d, %Y, %I:%M %p"),
            "currency_code":"AUD",
            "po_id": po.po_id,
            "po_number": po.po_number,
            "sbpo_order_date": po.order_date,
            "warehouse_id": po.warehouse_id,
            "po_delivery_name": po.delivery_name,
            "po_address_line1": po.address_line1,
            "po_address_line2": po.address_line2,
            "po_city": po.city,
            "po_state": po.state,
            "po_zip": po.post_code,
            "po_country":Country.objects.filter(id=po.country_id).first().name if po.country_id else None,
            "vendor_code": po.vendor_code,
            "vendor_name": po.vendor_name,
            "status_id": po.status_id,
            "tax_percentage": float(po.tax_percentage),
            "comments": po.comments,
            "shipping_charge": po.shipping_charge,
            "surcharge_total": po.surcharge_total,
            "summary_total": po.summary_total,
            "tax_total": po.tax_total,
            "sub_total": po.sub_total,
        },
        "po_vendor_details": list(
            po_vendor_details.values(
                "po_vendor_id",
                "vendor_po_number",
                "order_number",
                "order_date"
            )
        ),
        "line_items": line_items,
    }

    return JsonResponse({"status":True, "message":"success", "data":context})



# Product Add New Form - Only GET
# Render CREATE PO ORDER FORM
@login_required
def create_order(request, po_id=None):
    if po_id is None:
        po = PurchaseOrder.objects.create(
            vendor_code="",
            vendor_name="",
            created_by=request.user.id,
            tax_percentage=10.0,
            status_id=POStatus.DRAFT__PENDING  # Created / Draft
        )
        po_number = f"PO{po.po_id:04d}"

        #  Update the record with PO number
        po.po_number = po_number
        po.save()
        return redirect('create_order', po_id=po.po_id)

    po = PurchaseOrder.objects.filter(po_id=po_id, is_archived=0).first()
    if not po:
        return HttpResponse("Invalid PO", status=404)

    # category = Category.objects.filter(status=1).all()
    warehouses = Warehouse.objects.all()
    unit_of_measures = UnitOfMeasurements.objects.all()
    vendors = Vendor.objects.filter(status=1).all()
    countries_list = Country.objects.values('name', 'id', 'currency')
    currency_list = Country.objects.values('currency').annotate(
        id=Min('id'),  # pick country with smallest ID per currency
        currency_name=Min('currency_name')
    )
    po_order_items = PurchaseOrderItem.objects.filter(po_id=po_id).all()

    line_items = []

    NO_IMAGE = static("no_product_image.png")
    # Build Response

    for po_order_item in po_order_items:
        po_product = Product.objects.filter(product_id=po_order_item.product_id).first()
        po_images = ProductImages.objects.filter(product_id=po_order_item.product_id).order_by(
            "product_image_id").first()
        line_items.append({
            "row_item": {
                "id": po_product.product_id,
                "title": po_product.title,
                "image": po_images.cdn_url if po_images else NO_IMAGE,
                "stock_qty": 0,  # if you have stock, replace 0
                "sku": po_product.sku,
                "asin": po_product.asin, "fnsku": po_product.fnsku, "ean": po_product.ean,
                "prep_type": get_prep_label(po_product.prep_type),
                "product_order_type": po_order_item.order_type,  # send as number for JS
                "product_order_ref": po_order_item.order_ref,  # send as number for JS
                "is_taxfree": True if po_product.is_taxable else False,
            },
            "barcode_label_type": po_product.barcode_label_type,
            "qty": int(po_order_item.qty),
            "price": float(po_order_item.price),
            "discount": float(po_order_item.discount_percentage),
            "tax": float(po_order_item.tax_percentage),
            "tax_amount": float(po_order_item.tax_amount),
            "sub_total": float(po_order_item.subtotal),
            "line_total": float(po_order_item.line_total),
        })

    can_pdf_generate, err_msg = validate_purchase_order_model(po, line_items)
    payment_terms = PaymentTerm.objects.all()

    shipping_details = PurchaseOrderShipping.objects.filter(po_id=po.po_id).all()
    po_vendor_details = PurchaseOrderVendorDetails.objects.filter(po_id=po_id).all()
    shipping_providers = ShippingProviders.objects.filter(is_archived=0, status=1).all()
    #warehouse locations
    #warehouse_locations = OrganizationInventoryLocation.objects.filter(organization_id=1).all()
    context = {
        'po_id': po_id,
        'po': po,
       # 'warehouse_locations': warehouse_locations,
        "po_vendor_details": po_vendor_details,
        "shipping_providers": shipping_providers,
        'shipping': shipping_details,
        'can_pdf_generate': can_pdf_generate,
        'po_order_items': po_order_items,
        'user': request.user.id,
        'payment_terms': payment_terms,
        'unit_of_measures': unit_of_measures,
        'line_items': line_items,
        'warehouses': warehouses,
        'country_list': countries_list,
        'currency_list': currency_list,
        'vendors': vendors
    }

    return render(request, 'sbadmin/pages/purchase_order/add/addnew_form.html', context)


def d2(v):
    Q = Decimal("0.01")
    return v.quantize(Q, rounding=ROUND_HALF_UP)

from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 28  # global precision
Q2 = Decimal("0.01")
Q4 = Decimal("0.0001")

def r2(v):
    return v.quantize(Q2, rounding=ROUND_HALF_UP)

def r4(v):
    return v.quantize(Q4, rounding=ROUND_HALF_UP)


from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.http import JsonResponse

@api_view(['POST'])
def save_po_details(request):
    data = request.data  # Assuming DRF or similar JSON parser

    # 1. Capture IDs
    po_id = data.get("po_id")
    vendor_id = data.get("vendor_id")
    warehouse_id = data.get("warehouse_id")

    # 2. Capture Lists (Matched to React Keys)
    line_items = data.get("line_items", [])
    vendor_orders = data.get("vendor_orders", [])  # Matched to 'vendor_orders'
    delivery_details = data.get("delivery_details", {})
    summary = data.get("summary", {})

    if not vendor_id or not po_id:
        return JsonResponse({"status": False, "error": "Invalid Operation: Missing IDs"}, status=400)

    try:
        po = PurchaseOrder.objects.get(po_id=po_id)
        po_vendor = Vendor.objects.get(id=vendor_id)
    except (PurchaseOrder.DoesNotExist, Vendor.DoesNotExist):
        return JsonResponse({"status": False, "error": "PO or Vendor not found"}, status=400)

    # 1. Capture the SB PO Number from the payload
    sb_po_number = data.get("sb_po_number")
    po_id = data.get("po_id")

    # 2. Check for duplicates (Excluding the current PO being edited)
    duplicate_exists = PurchaseOrder.objects.filter(
        po_number=sb_po_number
    ).exclude(po_id=po_id).exists()

    if duplicate_exists:
        return JsonResponse({
            "status": False,
            "message": f"The SB PO Number '{sb_po_number}' is already in use by another order."
        }, status=400)

    # 3. Financials (Safe casting)
    try:
        shipping_total = Decimal(str(summary.get("freight") or "0"))
        surcharge_total = Decimal(str(summary.get("surcharge") or "0"))
    except (InvalidOperation, ValueError):
        shipping_total = Decimal("0.00")
        surcharge_total = Decimal("0.00")

    with transaction.atomic():
        # Update Main PO Info
        po.vendor_id = po_vendor.id
        po.vendor_code = po_vendor.vendor_code
        po.po_number = data.get("sb_po_number")
        po.warehouse_id = warehouse_id
        po.order_date = data.get("sb_po_date")

        # Delivery Details (Flattened from React Object)
        po.delivery_name = delivery_details.get("delivery_name")
        po.address_line1 = delivery_details.get("address_line1")
        po.address_line2 = delivery_details.get("address_line2")
        po.city = delivery_details.get("city")
        po.state = delivery_details.get("state")
        po.post_code = delivery_details.get("zip")  # React sends 'zip'
        country_val = delivery_details.get("country")

        if country_val:
            # Check if the value is already an ID (integer or numeric string)
            if str(country_val).isdigit():
                po.country_id = int(country_val)
            else:
                # It's a name, so look up the Country object to get its ID
                country_obj = Country.objects.filter(name=country_val).first()
                if country_obj:
                    po.country_id = country_obj.id
                else:
                    # Handle case where the country name isn't found
                    po.country_id = None

        po.shipping_charge = shipping_total
        po.surcharge_total = surcharge_total
        po.comments = data.get("comments")
        po.created_by = request.user.id

        # --- PROCESS LINE ITEMS ---
        incoming_product_ids = []
        for item in line_items:
            # Matched to React's flat structure: { product_id, price, quantity, etc }
            p_id = item.get("product_id")
            incoming_product_ids.append(p_id)

            qty = Decimal(str(item.get("quantity", 0)))
            price = Decimal(str(item.get("price", 0)))
            tax_pct = Decimal(str(item.get("gst_percent", 10)))
            discount_pct = Decimal(str(item.get("discount", 0)))

            # Calculations
            base = qty * price
            discount_amt = (base * discount_pct) / Decimal("100")
            subtotal = base - discount_amt
            tax_amount = (subtotal * tax_pct) / Decimal("100")
            line_total = subtotal + tax_amount

            # Update or Create
            PurchaseOrderItem.objects.update_or_create(
                po_id=po.po_id,
                product_id=p_id,
                defaults={
                    "qty": qty,
                    "price": price,
                    "tax_percentage": tax_pct,
                    "tax_amount": tax_amount,
                    "discount_percentage": discount_pct,
                    "discount_amt": discount_amt,
                    "line_total": line_total,
                    "created_by": request.user.id
                }
            )

        # Delete removed items
        PurchaseOrderItem.objects.filter(po_id=po.po_id).exclude(product_id__in=incoming_product_ids).delete()

        # --- PROCESS VENDOR ORDERS ---
        incoming_v_order_ids = []
        for v_order in vendor_orders:
            v_po_id = v_order.get("po_vendor_id")

            obj, created = PurchaseOrderVendorDetails.objects.update_or_create(
                po_vendor_id=v_po_id if v_po_id else None,
                po_id=po.po_id,
                defaults={
                    "vendor_po_number": v_order.get("vendor_po_number"),
                    "order_number": v_order.get("order_number"),
                    "order_date": v_order.get("order_date") or None,
                }
            )
            incoming_v_order_ids.append(obj.po_vendor_id)

        # Delete removed vendor rows
        PurchaseOrderVendorDetails.objects.filter(po_id=po.po_id).exclude(
            po_vendor_id__in=incoming_v_order_ids).delete()

        # Final Totals Update (Calculated from saved items)
        agg = PurchaseOrderItem.objects.filter(po_id=po.po_id).aggregate(
            st=Sum('subtotal'),
            tt=Sum('tax_amount'),
            gt=Sum('line_total')
        )

        # Apply values with a fallback to Decimal("0.00") if the result is None
        po.sub_total = agg['st'] or Decimal("0.00")
        po.tax_total = agg['tt'] or Decimal("0.00")
        po.summary_total = (agg['gt'] or Decimal("0.00")) + po.shipping_charge + po.surcharge_total

        po.save()

    return JsonResponse({"status": True, "message": "PO updated successfully"})


#UPDATE SAVE PO
#verified
@api_view(["POST"])
def save_po(request):

    data = request.data  # RAW JSON is captured here
    # Basic Info
    po_id = data.get("po_id")
    po_number = data.get("po_number")
    vendor_id = data.get("vendor_id")
    #vendor_name = data.get("vendor_name")
    vendor_reference = data.get("vendor_reference")

    # Dates & Logistics
    order_date = data.get("order_date")
    #delivery_date = data.get("delivery_date")
    warehouse = data.get("warehouse")
    currency_code = data.get("currency_code")
   # payment_term_id = data.get("payment_term_id")

    # Address Info
    delivery_name = data.get("delivery_name")
    address_line1 = data.get("address_line1")
    address_line2 = data.get("address_line2")
    city = data.get("city")
    state = data.get("state")
    post_code = data.get("post_code")
    country = data.get("country")

    # Financials
    tax_percentage = data.get("tax_percentage","10.00")
    surcharge_total = data.get("surcharge_total", "0.00")
    shipping_total = data.get("shipping_charge", "0.00")  # Payload-ல் shipping_charge என உள்ளது
    comments = data.get("comments")

    # Lists (Nested Data)
    line_items = data.get("lineItems", [])
    vendor_po_details = data.get("vendor_po_details", [])  # இது ஒரு list ஆக வரும்

    # Simple validation
    if not vendor_id or not po_id:
        return JsonResponse({"error": "Invalid Operation"}, status=400)

    try:
        po = PurchaseOrder.objects.get(po_id=po_id)
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({"error": "Invalid Operation"}, status=400)

    if len(line_items) == 0:
        return JsonResponse({"error": "At least one line item required"}, status=400)

    try:
        shipping_total = Decimal(str(shipping_total or "0"))
    except InvalidOperation:
        shipping_total = Decimal("0")

    po_vendor = Vendor.objects.get(id=vendor_id)

    prepaid_vendor = PaymentTerm.objects.filter(type=1, id=po_vendor.payment_term.id).first()

    vendor_name = po_vendor.display_name
    payment_term_id = prepaid_vendor.id

    with transaction.atomic():
        po.vendor_id = po_vendor.id
        po.vendor_code = po_vendor.vendor_code
        po.po_number = po_number
        po.vendor_name = vendor_name
        po.vendor_reference = vendor_reference
        po.currency_code = currency_code
        #po.invoice_date = invoice_date
        po.warehouse_id = warehouse
        po.order_date = order_date
        po.payment_term_id = payment_term_id
        po.delivery_name = delivery_name
        po.address_line1 = address_line1
        po.address_line2 = address_line2
       # po.suburb = suburb
        #po.delivery_date = delivery_date
        po.state = state
        po.post_code = post_code
        po.country_id = country
        po.tax_percentage = tax_percentage
        po.city = city
        po.surcharge_total = surcharge_total
        po.shipping_charge = shipping_total

        po.comments = comments
        po.created_by = request.user.id
        if po.status_id == POStatus.DRAFT__PENDING:
            po.status_id = POStatus.PARKED__PENDING #int(po_status)  # POStatus.CREATED

        '''sub_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # qty*price
        tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # subtital 's tax amount
        summary_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # subtotal + taxamount
        '''

        can_pdf_generate, err_msg = validate_purchase_order_model(po, line_items)
        if not can_pdf_generate:
            return JsonResponse({"status": False, "message": err_msg})

        #PurchaseOrderItem.objects.filter(po_id=po.po_id).delete()
        existing_items = {
            i.product_id: i
            for i in PurchaseOrderItem.objects.filter(po_id=po.po_id)
        }
        incoming_product_ids = set()

        for item in line_items:
            product_id = item["row_item"]["id"]
            incoming_product_ids.add(product_id)

            #product = Product.objects.get(product_id=product_id)
            tax_pct = Decimal(str(item["tax"]))
            qty = Decimal(str(item["qty"]))
            price = Decimal(str(item["price"]))
            discount_pct = Decimal(str(item["discount"]))

            base = qty * price

            # Discount (keep 4 decimals)
            discount_amt = r4((base * discount_pct) / Decimal("100"))

            # Subtotal (4 decimals)
            subtotal_4 = r4(base - discount_amt)

            # Tax (4 decimals)
            tax_amt_4 = r4((subtotal_4 * tax_pct) / Decimal("100"))

            # FINAL VALUES (2 decimals ONLY HERE)
            subtotal = r2(subtotal_4)
            tax_amount = r2(tax_amt_4)
            line_total = r2(subtotal + tax_amount)

            item_tax_amount = tax_amount
            #print(item_tax_amount)
            #item_tax_amount = 0  # calculate
            #discount_amt = 0  # calculate

            if product_id in existing_items:
                # UPDATE
                po_item = existing_items[product_id]
                po_item.qty = qty
                po_item.price = price
                po_item.tax_percentage = tax_pct
                po_item.tax_amount = item_tax_amount
                po_item.discount_percentage = discount_pct
                po_item.discount_amt = discount_amt
                po_item.order_ref = item["order_ref"]
                po_item.order_type = item["order_type"]
                po_item.line_total = line_total
                po_item.save(update_fields=[
                    "qty",
                    "price",
                    "tax_percentage",
                    "tax_amount",
                    "line_total",
                    "discount_percentage",
                    "discount_amt",
                    "order_ref",
                    "order_type"
                ])
            else:
                # CREATE
                PurchaseOrderItem.objects.create(
                    po_id=po.po_id,
                    product_id=product_id,
                    qty=qty,
                    price=price,
                    tax_percentage=tax_pct,
                    tax_amount=item_tax_amount,
                    discount_percentage=discount_pct,
                    line_total=line_total,
                    discount_amt=discount_amt,
                    order_ref=item["order_ref"],
                    order_type=item["order_type"],
                    created_by=request.user.id,
                )
        PurchaseOrderItem.objects.filter(
            po_id=po.po_id
        ).exclude(product_id__in=incoming_product_ids).delete()

        items = PurchaseOrderItem.objects.filter(po_id=po.po_id)

        subtotal_total = sum(
            (i.subtotal for i in items),
            Decimal("0.00")
        )
        discount_total = sum(
            (i.discount_amt for i in items),
            Decimal("0.00")
        )
        tax_total = sum(
            (i.tax_amount for i in items),
            Decimal("0.00")
        )

        line_total_total = sum(
            (i.line_total for i in items),
            Decimal("0.00")
        )

        po.sub_total = subtotal_total
        po.discount_total = discount_total
        po.tax_total = tax_total
        po.summary_total = line_total_total

        po.save()

       # shipping_po = PurchaseOrderShipping.objects.filter(po_id=po.po_id).first()

       # if shipping_po:
       #     shipping_po.delete()

        # 1. delete all existing records
        #PurchaseOrderShipping.objects.filter(po_id=po_id).delete()
        # 2. prepare new records
        '''
        shipping_objs = [
            PurchaseOrderShipping(
                po_id=po_id,
                provider=item.get('provider'),
                tracking_number=item.get('tracking_no'),
                shipped_date=item.get('shipped_date') or None,
                received_date=item.get('received_date') or None,
                created_by=request.user.id
            )
            for item  in shipping
            if item.get('provider')
        ]'''

        # 3. bulk insert
       # PurchaseOrderShipping.objects.bulk_create(shipping_objs)
        incoming_po_vendor_ids = []
        for vendor_po_detail in vendor_po_details:
            vendor_po_number = vendor_po_detail["vendor_po_number"]
            order_number = vendor_po_detail["order_number"]
            order_date = vendor_po_detail["order_date"]
            po_vendor_id = vendor_po_detail["po_vendor_id"]

            if po_vendor_id:
                incoming_po_vendor_ids.append(po_vendor_id)
                ex_po = PurchaseOrderVendorDetails.objects.filter(po_vendor_id=po_vendor_id, po_id=po_id).first()
                ex_po.vendor_po_number = vendor_po_number
                ex_po.order_number = order_number
                ex_po.order_date = order_date
                ex_po.save(update_fields=["order_number", "vendor_po_number", "order_date"])
            else:
                PurchaseOrderVendorDetails.objects.create(
                    po_id=po_id,
                    vendor_po_number=vendor_po_number,
                    order_number=order_number,
                    order_date=order_date,
                    created_by=request.user.id
                )
        #return JsonResponse({"error": "Invalid Operation"}, status=400)
        if incoming_po_vendor_ids:
            PurchaseOrderVendorDetails.objects.filter(po_id=po_id).exclude(po_vendor_id__in=incoming_po_vendor_ids).delete()

    return Response({"status": True, "message": "PO updated successfully"})

from django.utils import timezone
from django.utils.html import escape
from django.utils.dateformat import format as df

def approve_and_create_receive11(request, po_id):
    try:
        po_detail = PurchaseOrder.objects.filter(po_id=po_id).first()
        if not po_detail:
            return JsonResponse({
                "status": False,
                "message": "Invalid PO Details",
                "redirect_url": ""
            })

        #  CHECK EXISTING RECEIVE FIRST
        existing_receive = PurchaseReceives.objects.filter(
            po_id=po_detail.po_id
        ).order_by("-po_receive_id").first()

        if existing_receive:
            return JsonResponse({
                "status": True,
                "message": "Opening receive details",
                "redirect_url": reverse(
                    "edit_po_receive_order",
                    kwargs={"po_receive_id": existing_receive.po_receive_id}
                )
            })

        # -------------------------------------------------
        # CREATE NEW RECEIVE (ONLY IF NONE EXISTS)
        # -------------------------------------------------
        po_detail.updated_by = request.user.id
        po_detail.updated_at = timezone.now()
        po_detail.save(update_fields=["updated_by", "updated_at"])

        po_next = (
            PurchaseReceives.objects.aggregate(
                max_id=Max("po_receive_id")
            ).get("max_id") or 0
        ) + 1

        po_receive_number = f"PR{po_next:04d}"

        receive = PurchaseReceives.objects.create(
            po_id=po_detail.po_id,
            vendor_id=po_detail.vendor_id,
            po_number=po_detail.po_number,
            po_receive_number=po_receive_number,
            received_date=datetime.date.today(),
            shipping_date=datetime.date.today(),
            created_by=request.user.id,
        )

        # CREATE RECEIVE ITEMS (0 QTY)
        po_items = PurchaseOrderItem.objects.filter(po_id=po_detail.po_id)
        for po_item in po_items:
            PurchaseReceivedItems.objects.create(
                po_receive_id=receive.po_receive_id,
                product_id=po_item.product_id,
                item_id=po_item.item_id,
                received_qty=0,
                created_by=request.user.id,
                status_id=1
            )

        return JsonResponse({
            "status": True,
            "message": "PO Receive created successfully",
           "po_receive_id": receive.po_receive_id
        })

    except Exception as e:
        transaction.set_rollback(True)
        return JsonResponse({
            "status": False,
            "message": str(e),
            "redirect_url": ""
        })



#Approve PO Order Not used
@login_required
def approve_po_order(request, po_id):
    return JsonResponse({"status": True, "message": "PO approved successfully"})
    from django.utils import timezone
    if po_id is None:
        return HttpResponse("Invalid PO", status=404)
    po = PurchaseOrder.objects.filter(po_id=po_id, is_archived=0, status_id=0).first()
    if not po:
        return JsonResponse({"status": True, "message": "Invalid PO Details"})
    else:
       # po.status_id = POStatus.PLACED
        po.updated_by = request.user.id
        po.updated_at = timezone.now()
        po.save(update_fields=["status_id","updated_by","updated_at"])

    return JsonResponse({"status":True, "message": "PO approved successfully"})

def get_po_line_received_items(po_id, po_received_id):
    if po_id is None:
        return HttpResponse("Invalid PO", status=404)

    po = PurchaseOrder.objects.filter(po_id=po_id, is_archived=0).first()
    if not po:
        return HttpResponse("Invalid PO", status=404)

    # category = Category.objects.filter(status=1).all()
    warehouses = Warehouse.objects.all()
    unit_of_measures = UnitOfMeasurements.objects.all()
    vendor_detail = Vendor.objects.filter(vendor_code=po.vendor_code).first()
    countries_list = Country.objects.values('name', 'id', 'currency')
    currency_list = Country.objects.values('currency').annotate(
        id=Min('id'),  # pick country with smallest ID per currency
        currency_name=Min('currency_name')
    )
    po_order_items = PurchaseOrderItem.objects.filter(po_id=po_id).all()

    if not vendor_detail or len(po_order_items) == 0:
        return redirect("create_order", po_id=po_id)

    line_items = []

    NO_IMAGE = static("no_product_image.png")
    # Build Response

    tot_qty = 0
    for po_order_item in po_order_items:
        tot_qty += int(po_order_item.qty)

    addntl_totl = float(po.shipping_charge + po.surcharge_total)  # landed cost calculation
    addntl_per_totl = float(addntl_totl / tot_qty)  # landed cost calculation

    for po_order_item in po_order_items:
        # Calculate the Discounted Unit Price
        # Example: $50.00 * (1 - 0.10) = $45.00
        base_price = float(po_order_item.price)  # landed cost calculation
        discount_multiplier = 1 - (float(po_order_item.discount_percentage) / 100.00)  # landed cost calculation
        discounted_price = base_price * discount_multiplier  # landed cost calculation

        po_product = Product.objects.filter(product_id=po_order_item.product_id).first()
        po_images = ProductImages.objects.filter(product_id=po_order_item.product_id).order_by(
            "product_image_id").first()

        # landed cost calculation
        unit_total = addntl_per_totl * int(po_order_item.qty)
        rate_totl = (float(discounted_price) * int(po_order_item.qty)) + unit_total
        rate_totl = 0 if po_order_item.qty == 0 else rate_totl / int(po_order_item.qty)  # individual landed cost
        # cost_per_item = cost_per_item+float(float(po_order_item.price)*int(po_order_item.qty))
        # rate_totl = rate_totl
        # EOF landed cost calculation
        po_received_item = PurchaseReceivedItems.objects.filter(po_receive_id=po_received_id,
                                                                product_id=po_product.product_id).first()

        line_items.append({
            "row_item": {
                "id": po_product.product_id,
                "title": po_product.title,
                "image": po_images.cdn_url if po_images else NO_IMAGE,
                "stock_qty": 0,  # if you have stock, replace 0
                "sku": po_product.sku,
                "asin": po_product.asin, "fnsku": po_product.fnsku, "ean": po_product.ean,
                "prep_type": get_prep_label(po_product.prep_type),
                "price": float(po_order_item.price),  # send as number for JS
                "order_type": po_order_item.order_type,  # send as number for JS
                "order_ref": po_order_item.order_ref,  # send as number for JS
                "is_taxfree": True if po_product.is_taxable else False,
            },
            "qty": int(po_order_item.qty),
            "pending_qty": int(po_order_item.pending_qty),
            "received_qty": int(po_received_item.received_qty),
            "price": float(po_order_item.price),
            "discount": float(po_order_item.discount_percentage),
            "tax": float(po_order_item.tax_percentage),
            "tax_amount": float(po_order_item.tax_amount),
            "sub_total": float(po_order_item.subtotal),
            "line_total": float(po_order_item.line_total),
            "cost_per_item": float(rate_totl),  # send as number for JS
        })

    can_pdf_generate, err_msg = validate_purchase_order_model(po, line_items)
    payment_terms = PaymentTerm.objects.all()

    shipping_details = PurchaseOrderShipping.objects.filter(po_id=po.po_id).first()
    shipping_providers = ShippingProviders.objects.filter(is_archived=0, status=1).all()

    ################# PO LOGS #######################
    po_receives = PurchaseReceives.objects.filter(po_id=po.po_id).all()

    #####################################################
    created_by = getUserName(po.created_by)

    context = {
        'po_id': po_id,
        'po': po,
        "shipping_providers": shipping_providers,
        "po_logs": "",
        'shipping': shipping_details,
        'can_pdf_generate': can_pdf_generate,
        'po_order_items': po_order_items,
        'created_by': created_by,
        'payment_terms': payment_terms,
        'unit_of_measures': unit_of_measures,
        'line_items': line_items,
        'warehouses': warehouses,
        'country_list': countries_list,
        'currency_list': currency_list,
        'vendor': vendor_detail
    }
    return context



def get_po_line_items(po_id):
    if po_id is None:
        return HttpResponse("Invalid PO", status=404)

    po = PurchaseOrder.objects.filter(po_id=po_id, is_archived=0).first()
    if not po:
        return HttpResponse("Invalid PO", status=404)

    # category = Category.objects.filter(status=1).all()
    warehouses = Warehouse.objects.all()
    unit_of_measures = UnitOfMeasurements.objects.all()
    vendor_detail = Vendor.objects.filter(vendor_code=po.vendor_code).first()
    countries_list = Country.objects.values('name', 'id', 'currency')
    currency_list = Country.objects.values('currency').annotate(
        id=Min('id'),  # pick country with smallest ID per currency
        currency_name=Min('currency_name')
    )
    po_order_items = PurchaseOrderItem.objects.filter(po_id=po_id).all()

    if not vendor_detail or len(po_order_items) == 0:
        return redirect("create_order", po_id=po_id)

    line_items = []

    NO_IMAGE = static("no_product_image.png")
    # Build Response

    tot_qty = 0
    for po_order_item in po_order_items:
        tot_qty += int(po_order_item.qty)

    addntl_totl = float(po.shipping_charge + po.surcharge_total)  # landed cost calculation
    addntl_per_totl = float(addntl_totl / tot_qty)  # landed cost calculation

    for po_order_item in po_order_items:
        # Calculate the Discounted Unit Price
        # Example: $50.00 * (1 - 0.10) = $45.00
        base_price = float(po_order_item.price)  # landed cost calculation
        discount_multiplier = 1 - (float(po_order_item.discount_percentage) / 100.00)  # landed cost calculation
        discounted_price = base_price * discount_multiplier  # landed cost calculation

        po_product = Product.objects.filter(product_id=po_order_item.product_id).first()
        po_images = ProductImages.objects.filter(product_id=po_order_item.product_id).order_by(
            "product_image_id").first()

        # landed cost calculation
        unit_total = addntl_per_totl * int(po_order_item.qty)
        rate_totl = (float(discounted_price) * int(po_order_item.qty)) + unit_total
        rate_totl = 0 if po_order_item.qty == 0 else rate_totl / int(po_order_item.qty)  # individual landed cost
        # cost_per_item = cost_per_item+float(float(po_order_item.price)*int(po_order_item.qty))
        # rate_totl = rate_totl
        # EOF landed cost calculation

        line_items.append({
            "row_item": {
                "id": po_product.product_id,
                "title": po_product.title,
                "image": po_images.cdn_url if po_images else NO_IMAGE,
                "stock_qty": 0,  # if you have stock, replace 0
                "sku": po_product.sku,
                "asin": po_product.asin, "fnsku": po_product.fnsku, "ean": po_product.ean,
                "prep_type": get_prep_label(po_product.prep_type),
                "price": float(po_order_item.price),  # send as number for JS
                "order_type": po_order_item.order_type,  # send as number for JS
                "order_ref": po_order_item.order_ref,  # send as number for JS
                "is_taxfree": True if po_product.is_taxable else False,
            },
            "barcode_label_type": po_product.barcode_label_type,
            "qty": int(po_order_item.qty),
            "pending_qty": int(po_order_item.pending_qty),
            "received_qty": int(po_order_item.received_qty),
            "price": float(po_order_item.price),
            "discount": float(po_order_item.discount_percentage),
            "tax": float(po_order_item.tax_percentage),
            "tax_amount": float(po_order_item.tax_amount),
            "sub_total": float(po_order_item.subtotal),
            "line_total": float(po_order_item.line_total),
            "cost_per_item": float(rate_totl),  # send as number for JS
        })

    can_pdf_generate, err_msg = validate_purchase_order_model(po, line_items)
    payment_terms = PaymentTerm.objects.all()

    shipping_details = PurchaseOrderShipping.objects.filter(po_id=po.po_id).first()
    shipping_providers = ShippingProviders.objects.filter(is_archived=0, status=1).all()

    ################# PO LOGS #######################
    po_receives = PurchaseReceives.objects.filter(po_id=po.po_id).all()

    #####################################################
    created_by = getUserName(po.created_by)

    context = {
        'po_id': po_id,
        'po': po,
        "shipping_providers": shipping_providers,
        "po_logs": "",
        'shipping': shipping_details,
        'can_pdf_generate': can_pdf_generate,
        'po_order_items': po_order_items,
        'created_by': created_by,
        'payment_terms': payment_terms,
        'unit_of_measures': unit_of_measures,
        'line_items': line_items,
        'warehouses': warehouses,
        'country_list': countries_list,
        'currency_list': currency_list,
        'vendor': vendor_detail
    }
    return context




#PDF GEnerate function
@api_view(["POST"])
def generate_po_pdf(request):
    po_id = request.data.get("po_id")
    po_details = PurchaseOrder.objects.filter(po_id=po_id).first()
    if not po_details:
        return HttpResponse("Invalid PO", status=404)

    #vendor = Vendor.objects.filter(id=po_details.vendor_id).first()

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
        #vendor_country = vc.name if vc else ""

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
                         "amount": line_item.line_total
                         })

    po = {
        "number": po_details.po_number,
        "order_no": po_details.vendor_reference,
        "order_date": po_details.order_date.strftime("%d/%m/%Y"),
        "delivery_date": po_details.delivery_date.strftime("%d/%m/%Y"),
        "ref": po_details.vendor_reference,
        "invoice_number": po_details.po_number,
        "payment_term": PaymentTerm.objects.filter(
            id=po_details.payment_term_id).first().name if po_details.payment_term_id else "",
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
    gst_percent = clean_percent(po_details.tax_percentage)  # 10%
    # compute item amounts and totals with Decimal for precision
    subtotal = (po_details.sub_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    # Decimal("0.01"), rounding=ROUND_HALF_UP

    gst_amount = (po_details.tax_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    glbl_tax_percentage = po_details.tax_percentage

    total = (po_details.summary_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    shipping_details = PurchaseOrderShipping.objects.filter(po_id=po_details.po_id).first()

    shipping = (po_details.shipping_charge).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    surcharge = (po_details.surcharge_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    surcharge_total = shipping + surcharge

    surcharge_tax_amnt = surcharge_total * (glbl_tax_percentage / 100)
    gst_amount = gst_amount + surcharge_tax_amnt
    total = gst_amount + surcharge_total + subtotal
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
        "logo_url": "https://www.shopperbeats.com/cdn/shop/files/logo_260x_2x_600c8b6c-c0e8-4f59-82df-6a2d9bed69da_260x@2x.jpg",
        # swap with your logo
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
    # pdf = html.write_pdf(stylesheets=["https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&family=Roboto:ital,wght@0,100..900;1,100..900&display=swap"])
    pdf = html.write_pdf()

    # Return response
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = "inline;  filename=purchase_order.pdf"
    # inline - inline browser view
    # attachment - download attachement
    return response

#Get PO List by Vendor ID
@api_view(["GET"])
def get_vendors_po(request):
    vendor_id = request.GET.get("vendor_id")
    if(not vendor_id):
        return JsonResponse({})

    vendors_po = PurchaseOrder.objects.filter(vendor_id=vendor_id, is_archived=0, status_id=1).all()
    data = []
    for vendor_po in vendors_po:
        data.append({
            "po_number":vendor_po.po_number,
            "order_date":df(vendor_po.order_date,"d-m-Y"),
            "status":vendor_po.status_id
        })

    return JsonResponse({"data":data})

#GET PO Line Items by PO ID JSON
@api_view(["GET"])
# Items & Description	Ordered	Received	In Transit	Quantity to Receive
def list_po_line_items(request):
    po_id = request.GET.get("po_id")

    if not po_id:
        return JsonResponse({})

    po_details = PurchaseOrder.objects.get(po_number=po_id)
    po_items = PurchaseOrderItem.objects.filter(po_id=po_details.po_id).all()

    data = []
    for po_item in po_items:
        product = Product.objects.get(product_id=po_item.product_id)
        po_item = PurchaseOrderItem.objects.filter(po_id=po_item.po_id, product_id=product.product_id).first()
        pending_qty = 0
        if po_item:
            pending_qty = po_item.pending_qty
        data.append({
            "item_name": product.title,
            "item_id": po_item.item_id,
            "product_id": product.product_id,
            "item_sku": product.sku,
            "item_unit": po_item.unit,
            "ordered": po_item.qty,
            "po_item_pending": pending_qty,
            "received": 0.0,
            "in_transit": 0.0
        })

    return JsonResponse({"data": {"products": data}})

#PO Listing - JSON Function
@login_required
def listing(request):
    # ---- Context ----
    vendors = Vendor.objects.all()
    context = {
        "user": request.user.id,
        "vendors": vendors,
    }
    return render(request, 'sbadmin/pages/purchase_order/all_po_listing.html', context)


#Get PO Receives only JSON API calls - verified
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def all_purchase_receives(request):
    vendor_name_sub = Vendor.objects.filter(
        id=OuterRef("vendor_id")
    ).values("display_name")[:1]
    vendor_companyname_sub = Vendor.objects.filter(
        id=OuterRef("vendor_id")
    ).values("company_name")[:1]
    received_qty_sub = PurchaseReceivedItems.objects.filter(
        po_receive_id=OuterRef("po_receive_id")
    ).values("po_receive_id").annotate(
        total_qty=Sum("received_qty")
    ).values("total_qty")[:1]

    qs = PurchaseReceives.objects.annotate(
        vendor_name=Subquery(vendor_name_sub),
        company_name=Subquery(vendor_companyname_sub),
        total_received_qty=Subquery(received_qty_sub),
    ).order_by("-created_at").all()
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(po_number__icontains=q) | Q(po_receive_number__icontains=q))

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

    data = list(qs[start:end].values(
        "po_receive_id","po_id", "is_billed",  "total_received_qty", "company_name", "vendor_name", "vendor_id", "po_number", "po_receive_number", "received_date",
        "status_id"
    ))

    for po_data in data:
        # 1. Check Shipping Details
        # If a tracking number exists, the initial status becomes "Shipped"
        po_id = int(po_data.get("po_id"))
        shipping_exists = PurchaseOrderShipping.objects.filter(po_id=po_id).first()
        if shipping_exists and shipping_exists.tracking_number:
            po_data["status_id"] = 2  # Shipped

        # 2. Calculate Totals for Items
        po_items = PurchaseOrderItem.objects.filter(po_id=po_id)
        totals = po_items.aggregate(
            total_ordered=Sum('ordered_qty'),
            total_received=Sum('received_qty')
        )
        print(totals)

        total_qty = totals['total_ordered'] or 0
        received_qty = totals['total_received'] or 0

        # 3. Determine Delivery Status
        if received_qty > 0:
            if received_qty >= total_qty:
                po_data["status_id"] = 4  # Delivered
            else:
                # received_qty is > 0 but < total_qty
                po_data["status_id"] = 3  # Partially Delivered

        '''
        const statusMap = {
                0: "New",
                1: "Approved",
                2: "Shipped",
                3: "Partially Delivered",
                4: "Delivered",
                5: "Cancelled",
                6: "Archived"
              };
              '''
    last_page = math.ceil(total / size) if total else 1

    #  Return EXACT Tabulator compatible JSON
    return JsonResponse({
        "data": data,
        "last_page": last_page,
        "total": total, "row_count":200
    })


import json


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_shipping_details(request):
    try:
        # 1. Access the pre-parsed data instead of request.body
        data = request.data  # This replaces json.loads(request.body)

        po_id = data.get('po_id')
        po_item_id = data.get('po_item_id') #product_id
        receive_id = data.get('receive_id')  # po_receive_id
        shipments = data.get('shipments', [])
        user_id = request.user.id if request.user.is_authenticated else None

        po_receive = PurchaseReceives.objects.filter(po_id=po_id).first()
        if not po_receive:
            return JsonResponse({"status":False, "message":"Invalid Receive ID."}, status=400)

        receive_id = po_receive.po_receive_id

        created_count = 0
        for ship in shipments:
            exists = PurchaseOrderShipping.objects.filter(
                po_id=po_id,
                receive_id=receive_id,
                po_item_id=po_item_id,
                provider=ship.get('provider'),
                tracking_number=ship.get('tracking_number')
            ).exists()

            if exists:
                return JsonResponse({
                    "status": False,
                    "message": f"Tracking number '{ship.get('tracking_number')}' already exists for this product."
                }, status=200)


            PurchaseOrderShipping.objects.create(
                po_id=po_id,
                po_item_id=po_item_id,
                receive_id=receive_id,
                provider=ship.get('provider'),
                tracking_number=ship.get('tracking_number'),
                shipped_date=ship.get('shipped_date') or None,
                received_date=ship.get('received_date') or None,
                created_by=user_id
            )
            created_count += 1

        po_receive_item = PurchaseReceivedItems.objects.filter(product_id=po_item_id,
                                                               po_receive_id=receive_id).first()
        print("Updating shipping status")
        if po_receive_item:
            po_receive_item.status_id = POShippingStatus.SHIPPED
            print("Updated shipping status")
            po_receive_item.save(update_fields=["status_id"])

        po_details = PurchaseOrder.objects.filter(po_id=po_id).first()
        if po_details.status_id == POStatus.PLACED__PENDING:
            po_details.status_id = POStatus.PLACED__SHIPPED
            po_details.save(update_fields=["status_id"])

        return JsonResponse({
            "status": "success",
            "message": f"{created_count} shipping record(s) saved successfully."
        })

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def all_po_invoices(request, po_id, product_id, receive_id):
    payment_term_sub = PaymentTerm.objects.filter(
        id=OuterRef("invoice_payment_term_id")
    ).values("name")[:1]

    # Filter by po_id from your model
    qs = PurchaseOrderInvoiceDetails.objects.filter(po_id=po_id, po_item_id=product_id, receive_id= receive_id).annotate(
        payment_term_name=Subquery(payment_term_sub)
    ).order_by("-created_at")

    # Static Status Mapping based on your provided <select> IDs
    status_map = {
        1: "Paid",
        2: "Not paid",
        3: "Cancelled",
        4: "On Hold"
    }

    # Pagination logic
    try:
        page = int(request.GET.get("page", 1))
        size = min(int(request.GET.get("size", 20)), 50)
    except (ValueError, TypeError):
        page, size = 1, 20

    total = qs.count()
    start = (page - 1) * size
    end = start + size

    # Use .values() to get dictionary format for JsonResponse
    data_list = list(qs[start:end].values(
        "po_invoice_id",           # ID for the Action column (+1)
        "invoice_number",          # Column 1
        "order_no",                # Column 2
        "invoice_date",            # Column 3
        "received_qty",            # Column 4
        "po_amount",               # Column 5
        "payment_term_name",       # Column 6 (Annotated above)
        "invoice_due_date",        # Column 7
        "paid_date",               # Column 8
        "order_date",              # Column 9
        "vendor_po_no",            # Column 10
        "po_reference_no",         # Column 11
        "invoice_status_id",       # Column 12 (Used for status badges)
    ))

    # Add the readable status label to each record
    for item in data_list:
        status_id = item.get('invoice_status_id')
        item['status_display'] = status_map.get(status_id, "Unknown")

    last_page = math.ceil(total / size) if total else 1

    return JsonResponse({
        "data": data_list,
        "last_page": last_page,
        "total": total
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def all_po_shipments(request, po_id, product_id, receive_id  ):
    # Subquery to fetch the carrier name from ShippingProviders
    provider_name_sub = ShippingProviders.objects.filter(
        carrier_id=OuterRef("provider")
    ).values("carrier_name")[:1]
    provider_tracking_url_sub = ShippingProviders.objects.filter(
        carrier_id=OuterRef("provider")
    ).values("tracking_url")[:1]


    if not PurchaseReceives.objects.filter(po_receive_id=receive_id).exists():
        po_receive = PurchaseReceives.objects.filter(po_id=po_id).first()
        receive_id = po_receive.po_receive_id


    # Filter shipments by po_id and the specific line item (po_item_id)
    qs = PurchaseOrderShipping.objects.filter(
        po_id=po_id,
        po_item_id=product_id,
        receive_id=receive_id
    ).annotate(
        provider_name=Subquery(provider_name_sub),
        provider_tracking_url=Subquery(provider_tracking_url_sub)
    ).order_by("-created_at")

    # Pagination
    try:
        page = int(request.GET.get("page", 1))
        size = min(int(request.GET.get("size", 20)), 50)
    except (ValueError, TypeError):
        page, size = 1, 20

    total = qs.count()
    start = (page - 1) * size
    end = start + size

    # Fetch values for JSON output
    data_list = list(qs[start:end].values(
        "po_shipping_id",
        "po_id",
        "po_item_id",
        "provider", # This is the carrier_id
        "provider_name", # From Subquery
        "provider_tracking_url",
        "tracking_number",
        "shipped_date",
        "received_date"
    ))
    for item in data_list:
        tracking_no = item.get("tracking_number")
        tracking_url = item.get("provider_tracking_url")

        if tracking_url and tracking_no:
            item["provider_tracking_url"] = tracking_url.replace("{0}", tracking_no)

    # Optional: Format dates for better JS compatibility
    for item in data_list:
        if item['shipped_date']:
            item['shipped_date'] = item['shipped_date'].strftime('%Y-%m-%d')
        if item['received_date']:
            item['received_date'] = item['received_date'].strftime('%Y-%m-%d')

    last_page = math.ceil(total / size) if total else 1

    return JsonResponse({
        "data": data_list,
        "last_page": last_page,
        "total": total
    })

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def delete_po_shipment(request):
    shipping_id = request.POST.get("po_shipping_id")
    try:
        shipment = PurchaseOrderShipping.objects.get(po_shipping_id=shipping_id)
        # Optional: Add ownership check here
        shipment.delete()
        return JsonResponse({"status": "success", "message": "Shipment deleted successfully."})
    except PurchaseOrderShipping.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Record not found."}, status=404)

def clean_date(date_str):
    if date_str is None or str(date_str).strip() == "":
        return None
    return date_str


def clean_input(val):
    if val is None or str(val).strip() in ['', 'null', 'undefined', 'None']:
        return None
    return val

def save_purchase_invoice(request):
    if request.method != "POST":
        return JsonResponse(
            {"status": False, "message": "Invalid method"},
            status=405
        )

    try:
        data = json.loads(request.body)

        # -------------------------------------------------
        # REQUIRED FIELDS
        # -------------------------------------------------
        po_id = data.get("po_id")
        product_id = data.get("product_id")
        receive_id = data.get("receive_id")

        invoice_number = data.get("invoice_number")
        payment_status_id = data.get("payment_status_id")
        delivery_ref = data.get("delivery_ref")

        if not invoice_number:
            return JsonResponse(
                {"status": False, "message": "Invoice number is required"},
                status=400
            )

        if payment_status_id in [None, ""]:
            return JsonResponse(
                {"status": False, "message": "Invoice status is required"},
                status=400
            )

        # -------------------------------------------------
        # CLEAN INPUT HELPER
        # -------------------------------------------------
        def clean_val(val):
            if val in ["", None, "None", "null", "undefined"]:
                return None
            return val

        # -------------------------------------------------
        # DUPLICATE CHECK (CREATE ONLY)
        # -------------------------------------------------
        if PurchaseOrderInvoiceDetails.objects.filter(
            invoice_number=invoice_number, product_id=product_id, po_id=po_id
        ).exists():
            return JsonResponse(
                {"status": False, "message": "Invoice number already exists"},
                status=400
            )

        # -------------------------------------------------
        # CREATE INVOICE (NO UPDATE LOGIC)
        # -------------------------------------------------
        invoice = PurchaseOrderInvoiceDetails.objects.create(
            po_id=po_id,
            product_id=product_id,
            receive_id=receive_id,

            invoice_number=invoice_number,
            po_amount=Decimal(data.get("po_amount") or 0),
            received_qty=clean_val(data.get("received_qty")),
            payment_status_id=payment_status_id,

            order_date=clean_val(data.get("order_date")),
            order_no=clean_val(data.get("order_no")),
            vendor_ref_no=clean_val(data.get("vendor_ref_no")),
            delivery_ref=clean_val(delivery_ref),

            invoice_date=clean_val(data.get("invoice_date")),
            payment_term_id=clean_val(
                data.get("payment_term_id")
            ),
            due_date=clean_val(data.get("due_date")),
            paid_date=clean_val(data.get("paid_date")),

            created_by=request.user.id,
            created_at=timezone.now()
        )

        return JsonResponse({
            "status": True,
            "message": "Invoice created successfully",
            "po_invoice_id": invoice.po_invoice_id
        })

    except Exception as e:
        return JsonResponse(
            {"status": False, "message": str(e)},
            status=500
        )


def delete_invoice(request):
    po_invoice_id = request.POST.get("po_invoice_id")
    po_inv = PurchaseOrderInvoiceDetails.objects.get(po_invoice_id=po_invoice_id).delete()
    return JsonResponse({"status":True, "message":"Deletion successful"})


#delete PO Orders
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def delete_po(request, po_id):
    try:
        po_details = PurchaseOrder.objects.get(po_id=po_id)
        if po_details.status_id in [POStatus.DRAFT__PENDING, POStatus.PARKED__PENDING]:
            PurchaseOrder.objects.filter(po_id=po_id).delete()
            PurchaseOrderVendorDetails.objects.filter(po_id=po_id).delete()
            PurchaseOrderShipping.objects.filter(po_id=po_id).delete()
            PurchaseOrderItem.objects.filter(po_id=po_id).delete()
            PurchaseOrderFiles.objects.filter(po_id=po_id).delete()
            return JsonResponse({"status": True, "message": "Removed!"})
        else:
            return JsonResponse({"status": False, "message": "Can not remove this PO"})
       # updated = PurchaseOrder.objects.filter(
        #    po_id=po_id,
       #     is_archived=0
       # ).update(is_archived=1)
        return JsonResponse({"status": False, "message": "Removed!"})
        return JsonResponse({"status": False, "message": "Implemented soon!"})

        if not updated:
            return JsonResponse({
                "status": False,
                "message": "PO not found "
            })
        return JsonResponse({
            "status": True,
            "message": "Purchase Order archived successfully"
        })

    except Exception as e:
        return JsonResponse({
            "status": False,
            "message": str(e)
        })

#verified
''' TABLES LISTING TABLE '''



from django.db.models import Q, Subquery, OuterRef, Value, TextField, DecimalField
from django.db.models.functions import Coalesce
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

class GroupConcat(Aggregate):
    function = "GROUP_CONCAT"
    template = "%(function)s(%(expressions)s SEPARATOR ', ')"
    output_field = CharField()

def d(v):
    return Decimal(str(v or 0))

@api_view(["GET"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def all_purchases(request):
    from django.db.models import (
        OuterRef, Subquery, Value, TextField, DecimalField,
        Q, Sum
    )
    from django.db.models.functions import Coalesce
    from decimal import Decimal
    import math

    # -------------------------------
    # SUBQUERIES
    # -------------------------------
    warehouse_sub = Warehouse.objects.filter(
        warehouse_id=OuterRef("warehouse_id")
    ).values("warehouse_name")[:1]

    vendor_sub = Vendor.objects.filter(
        id=OuterRef("vendor_id")
    ).values("display_name")[:1]

    po_vendor_sub = (
        PurchaseOrderInvoiceDetails.objects
        .filter(po_id=OuterRef("po_id"))
        .order_by("-po_invoice_id")  # or -created_at
        .values("vendor_ref_no")[:1]
    )

    po_master_vendor_sub = (
        PurchaseOrderVendorDetails.objects
        .filter(po_id=OuterRef("po_id"))
        .values("po_id")
        .annotate(
            order_numbers=GroupConcat("order_number"),
            order_dates=GroupConcat("order_date"),
        )
    )

    po_shipping_details_sub = (
        PurchaseOrderShipping.objects
        .filter(po_id=OuterRef("po_id"))
        .values("po_id")
        .annotate(
            received_dates=GroupConcat("received_date")
        )
    )

    # -------------------------------
    # BASE QUERY
    # -------------------------------
    base_qs = PurchaseOrder.objects.filter(
        is_archived=0,
        vendor_id__isnull=False,
        vendor_code__isnull=False
    ).annotate(
        master_invoice_order_numbers=Coalesce(
            Subquery(po_master_vendor_sub.values("order_numbers")),
            Value(""),
            output_field=TextField()
        ),
        master_invoice_order_dates=Coalesce(
            Subquery(po_master_vendor_sub.values("order_dates")),
            Value(""),
            output_field=TextField()
        ),
        shipping_delivery_dates =Coalesce(
            Subquery(po_shipping_details_sub.values("received_dates")),
            Value(""),
            output_field=TextField()
        ),
        warehouse_name=Coalesce(Subquery(warehouse_sub), Value(""), output_field=TextField()),
        vendor_name_val=Coalesce(Subquery(vendor_sub), Value(""), output_field=TextField()),
        po_vendor_ref=Coalesce(Subquery(po_vendor_sub), Value(""), output_field=TextField()),
        subtotal_val=Coalesce("sub_total", Value(0, DecimalField())),
        tax_val=Coalesce("tax_total", Value(0, DecimalField())),
        total_val=Coalesce("summary_total", Value(0, DecimalField())),
    ).order_by("-created_at")

    filtered_qs = base_qs

    # -------------------------------
    # STATUS FILTER (CORRECTED)
    # -------------------------------
    status_param = request.GET.get("status", "").strip()

    if status_param not in ["", "None", "undefined"]:
        try:
            status = int(status_param)
            if status == 1:  # Placed (frontend)
                filtered_qs = filtered_qs.filter(status_id__in=[1, 2, 3])
            else:
                filtered_qs = filtered_qs.filter(status_id=status)
        except ValueError:
            pass

    # -------------------------------
    # OTHER FILTERS
    # -------------------------------
    order_no = request.GET.get("order_no")
    if order_no:
        filtered_qs = filtered_qs.filter(
            Q(po_number__icontains=order_no)
            |
            Exists(
                PurchaseOrderInvoiceDetails.objects.filter(
                    po_id=OuterRef("po_id"),
                    vendor_ref_no__icontains=order_no
                )
            )
            |
            Exists(
                PurchaseOrderVendorDetails.objects.filter(
                    po_id=OuterRef("po_id"),
                    order_number__icontains=order_no
                )
            )
        )

    vendor_payment_status = request.GET.get("vendor_payment_status")

    if vendor_payment_status not in ["", None]:
        filtered_qs = filtered_qs.filter(
            Exists(
                PurchaseOrderInvoiceDetails.objects.filter(
                    po_id=OuterRef("po_id"),
                    payment_status_id=int(vendor_payment_status)
                )
            )
        )

    vendor_id = request.GET.get("vendor_id")
    if vendor_id:
        filtered_qs = filtered_qs.filter(vendor_id=vendor_id)

    delivery_ref = request.GET.get("delivery_ref")
    if delivery_ref:
        filtered_qs = filtered_qs.filter(
            Exists(
                PurchaseOrderInvoiceDetails.objects.filter(
                    po_id=OuterRef("po_id"),
                    delivery_ref__icontains=delivery_ref
                )
            )
        )

    warehouse = request.GET.get("warehouse")
    if warehouse:
        filtered_qs = filtered_qs.filter(warehouse_id=warehouse)

    supplier_ref = request.GET.get("supplier_ref")
    if supplier_ref:
        filtered_qs = filtered_qs.filter(
            po_vendor_ref__icontains=supplier_ref
        )

    q = request.GET.get("q", "").strip()
    if q:
        filtered_qs = filtered_qs.filter(
            Q(po_number__icontains=q) |
            Q(vendor_name_val__icontains=q) |
            Q(vendor_reference__icontains=q)
        )

    # -------------------------------
    # FETCH DATA
    # -------------------------------
    data = list(filtered_qs.values(
        "po_id",
        "parent_po_id",
        "po_number",
        "vendor_id",
        "vendor_code",
        "vendor_name",
        "currency_code",
        "master_invoice_order_numbers",
        "master_invoice_order_dates",
        "vendor_reference",
        "order_date",
        "shipping_delivery_dates",
        "delivery_date",
        "invoice_date",
        "delivery_name",
        "created_at",
        "status_id",
        "sub_total",
        "summary_total",
        "shipping_charge",
        "surcharge_total",
        "tax_total",
        "warehouse_name",
        "po_vendor_ref",
        "vendor_name_val",
        "subtotal_val",
        "tax_val",
        "total_val",
    ))

    # -------------------------------
    # RELATED MAPS
    # -------------------------------
    po_ids = [x["po_id"] for x in data]

    vendor_map = {
        v.po_id: v
        for v in PurchaseOrderVendorDetails.objects.filter(po_id__in=po_ids)
    }

    shipping_map = {
        s.po_id: s
        for s in PurchaseOrderShipping.objects.filter(po_id__in=po_ids)
    }

    provider_map = {
        p.carrier_id: p
        for p in ShippingProviders.objects.all()
    }

    qty_map = {
        x["po_id"]: x
        for x in (
            PurchaseOrderItem.objects
            .filter(po_id__in=po_ids)
            .values("po_id")
            .annotate(
                total_order_qty=Sum("ordered_qty"),
                total_received_qty=Sum("received_qty")
            )
        )
    }

    # -------------------------------
    # MERGE DATA
    # -------------------------------
    for po in data:
        po_id = po["po_id"]

        vendor = vendor_map.get(po_id)
        shipping = shipping_map.get(po_id)
        qty = qty_map.get(po_id, {})

        po["po_vendor_order_date"] = vendor.order_date if vendor else ""

        provider = provider_map.get(shipping.provider) if shipping else None

        po["vendor_shipping_company"] = provider.carrier_name if provider else ""
        po["vendor_shipping_tracking_no"] = shipping.tracking_number if shipping else ""
        po["vendor_shipping_tracking_link"] = (
            provider.tracking_url.replace("{0}", shipping.tracking_number)
            if provider and shipping and shipping.tracking_number
            else ""
        )

        po["total_order_qty"] = qty.get("total_order_qty", 0) or 0
        po["total_received_qty"] = qty.get("total_received_qty", 0) or 0

    # -------------------------------
    # SHIPPING STATUS LABEL
    # -------------------------------
    for row in data:
        status_id = row.get("status_id")
        tracking_status = "Unknown"
        for s in po_status_list:
            if s["id"] == status_id:
                tracking_status = s["tracking_status"]
                break


        row["shipping_status"] = tracking_status

    # -------------------------------
    # PAGINATION
    # -------------------------------
    page = int(request.GET.get("page", 1) or 1)
    size = min(int(request.GET.get("size", 20) or 20), 50)

    total = len(data)
    start = (page - 1) * size
    end = start + size

    paged_data = data[start:end]
    last_page = math.ceil(total / size) if total else 1

    return JsonResponse({
        "data": paged_data,
        "last_page": last_page,
        "total": total,
        "row_count": total
    })


@api_view(["GET"])
def list_product_images(request, product_id):
    q = ProductImages.objects.filter(product_id=request.GET.get("product_id")) if request.GET.get("product_id") else ProductImages.objects.all()
    return JsonResponse(ProductImageSerializer(q, many=True).data)


# View PO ORDER
@login_required
def view_po_order(request, po_id):
    if po_id is None:
        return HttpResponse("Invalid PO", status=404)

    po = PurchaseOrder.objects.filter(po_id=po_id, is_archived=0).first()
    if not po:
        return HttpResponse("Invalid PO", status=404)

    # category = Category.objects.filter(status=1).all()
    warehouses = Warehouse.objects.all()
    unit_of_measures = UnitOfMeasurements.objects.all()
    vendor_detail = Vendor.objects.filter(vendor_code=po.vendor_code).first()
    countries_list = Country.objects.values('name', 'id', 'currency')
    currency_list = Country.objects.values('currency').annotate(
        id=Min('id'),  # pick country with smallest ID per currency
        currency_name=Min('currency_name')
    )
    po_order_items = PurchaseOrderItem.objects.filter(po_id=po_id).all()

    if not vendor_detail or len(po_order_items) == 0:
        return redirect("create_order", po_id=po_id)

    line_items = []

    NO_IMAGE = static("no_product_image.png")
    # Build Response

    tot_qty = 0
    for po_order_item in po_order_items:
        tot_qty += int(po_order_item.qty)

    addntl_totl = float(po.shipping_charge + po.surcharge_total)  # landed cost calculation
    addntl_per_totl = float(addntl_totl / tot_qty)  # landed cost calculation

    for po_order_item in po_order_items:
        # Calculate the Discounted Unit Price
        # Example: $50.00 * (1 - 0.10) = $45.00
        base_price = float(po_order_item.price)  # landed cost calculation
        discount_multiplier = 1 - (float(po_order_item.discount_percentage) / 100.00)  # landed cost calculation
        discounted_price = base_price * discount_multiplier  # landed cost calculation

        po_product = Product.objects.filter(product_id=po_order_item.product_id).first()
        po_images = ProductImages.objects.filter(product_id=po_order_item.product_id).order_by(
            "product_image_id").first()

        # landed cost calculation
        unit_total = addntl_per_totl * int(po_order_item.qty)
        rate_totl = (float(discounted_price) * int(po_order_item.qty)) + unit_total
        rate_totl = 0 if po_order_item.qty == 0 else rate_totl / int(po_order_item.qty)  # individual landed cost
        # cost_per_item = cost_per_item+float(float(po_order_item.price)*int(po_order_item.qty))
        # rate_totl = rate_totl
        # EOF landed cost calculation

        line_items.append({
            "row_item": {
                "id": po_product.product_id,
                "title": po_product.title,
                "image": po_images.cdn_url if po_images else NO_IMAGE,
                "stock_qty": 0,  # if you have stock, replace 0
                "sku": po_product.sku,
                "asin": po_product.asin, "fnsku": po_product.fnsku, "ean": po_product.ean,
                "prep_type": get_prep_label(po_product.prep_type),
                "price": float(po_order_item.price),  # send as number for JS
                "order_type": po_order_item.order_type,  # send as number for JS
                "order_ref": po_order_item.order_ref,  # send as number for JS
                "is_taxfree": True if po_product.is_taxable else False,
            },
            "barcode_label_type": po_product.barcode_label_type,
            "qty": int(po_order_item.qty),
            "price": float(po_order_item.price),
            "discount": float(po_order_item.discount_percentage),
            "tax": float(po_order_item.tax_percentage),
            "tax_amount": float(po_order_item.tax_amount),
            "sub_total": float(po_order_item.subtotal),
            "line_total": float(po_order_item.line_total),
            "cost_per_item": float(rate_totl),  # send as number for JS
        })

    can_pdf_generate, err_msg = validate_purchase_order_model(po, line_items)
    payment_terms = PaymentTerm.objects.all()

    shipping_details = PurchaseOrderShipping.objects.filter(
        po_id=po.po_id
    )

    shipping_providers = ShippingProviders.objects.filter(
        is_archived=0,
        status=1
    )

    # Build provider lookup (FAST)
    provider_map = {
        int(p.carrier_id): p
        for p in shipping_providers
    }

    # Final joined array
    shipping_joined = []

    for ship in shipping_details:
        try:
            provider = provider_map.get(int(ship.provider))
        except (TypeError, ValueError):
            provider = None

        shipping_joined.append({
            "tracking_number": ship.tracking_number,
            "provider_id": ship.provider,
            "shipped_date": ship.shipped_date,
            "received_date": ship.received_date,
            "provider_name": provider.carrier_name if provider else None,
            "tracking_link": (
                provider.tracking_url.replace("{0}", "") + ship.tracking_number
                if provider and ship.tracking_number else None
            )
        })

    po_receives = PurchaseReceives.objects.filter(po_id=po.po_id).all()
    log_html = ""
    is_all_received = not PurchaseOrderItem.objects.filter(
        po_id=po.po_id,
        pending_qty__gt=0
    ).exists()

    ################# PO LOGS #######################
    if po_receives:
        for po_receive in po_receives:
            pr_items = PurchaseReceivedItems.objects.filter(
                po_receive_id=po_receive.po_receive_id
            ).all()

            # ---------- PO RECEIVES ----------
            log_html += (
                "<div class='mb-3 pb-3 border-bottom'>"
                "<div class='d-flex align-items-center mb-2'>"
                "<i class='fa fa-file-invoice text-secondary mr-2'></i>"
                "<span class='font-weight-bold'>PO Receives</span>"
                "</div>"
                f"<a href=''>{escape(po_receive.po_receive_number)}</a> "
                f"<small>Received on {safe_df(po_receive.received_date, 'd M Y')}<br>"
                f"Created on {safe_df(po_receive.created_at, 'd M Y H:i')} "
                f"by {escape(str(StoreUser.objects.get(id=po_receive.created_by).name))}</small>"
            )

            log_html += """
                <table class="table table-sm table-bordered mt-2">
                    <thead>
                        <tr>
                            <th>Item details</th>
                            <th class="text-right">Ordered</th>
                            <th class="text-right">Received</th>
                        </tr>
                    </thead>
                    <tbody>
            """

            for item in pr_items:
                product = Product.objects.filter(product_id=item.product_id).first()
                po_item = PurchaseOrderItem.objects.filter(item_id=item.item_id).first()

                log_html += (
                    "<tr>"
                    f"<td title='{escape(product.title) if product else ''}'>"
                    f"{escape(product.sku) if product else '-'}</td>"
                    f"<td class='text-right'>{po_item.ordered_qty if po_item else 0}</td>"
                    f"<td class='text-right'>{item.received_qty}</td>"
                    "</tr>"
                )

            log_html += "</tbody></table></div>"
    else:
        log_html = "<div class='text-center text-muted'>--No transactions --</div> "
    #####################################################
    # print(shipping_joined)
    created_by = getUserName(po.created_by)
    po_receive = PurchaseReceives.objects.filter(po_id=po_id).first()
    vendor_po = PurchaseOrderVendorDetails.objects.filter(po_id=po_id).all()

    has_child_is_master = False
    if po.parent_po_id in ("", None, 0):
        has_child_is_master = PurchaseOrder.objects.filter(parent_po_id=po.parent_po_id).exists()

    context = {
        'po_id': po_id,
        'po_receive': po_receive,
        'vendor_po': vendor_po,
        'po': po,
        'has_child_is_master': has_child_is_master,
        'is_all_received': is_all_received,
        "shipping_providers": shipping_providers,
        "po_logs": log_html,
        'shipping_joined': shipping_joined,
        'can_pdf_generate': can_pdf_generate,
        'po_order_items': po_order_items,
        'user': request.user.id,
        'created_by': created_by,
        'payment_terms': payment_terms,
        'unit_of_measures': unit_of_measures,
        'line_items': line_items,
        'warehouses': warehouses,
        'country_list': countries_list,
        'currency_list': currency_list,
        'vendor': vendor_detail
    }
    return render(request, 'sbadmin/pages/purchase_order/view/view_po.html', context)


from decimal import Decimal
from django.http import JsonResponse

def get_shipping_rows(request, po_id):

    po_items = (
        PurchaseOrderItem.objects
        .filter(po_id=po_id)
        .select_related()
    )

    data = []

    for item in po_items:
        product = Product.objects.filter(
            product_id=item.product_id
        ).first()
        po_receive =  PurchaseReceives.objects.filter(po_id=item.po_id).first()
        if not po_receive:
            return JsonResponse({"data": []}, safe=False)

        po_recieved_item = PurchaseReceivedItems.objects.filter(product_id=product.product_id, po_receive_id=po_receive.po_receive_id).first()
        ordered_qty = Decimal(item.qty or 0)
        price = Decimal(item.price or 0)
        line_total = ordered_qty * price

        # Fetch shipping rows (may be EMPTY)
        shipping_qs = PurchaseOrderShipping.objects.filter(
            po_id=po_id,
            po_item_id=item.product_id
        )

        shipping_details = []
        for sh in shipping_qs:
            provider_name = ""
            provider_link = ""
            if sh.provider:
                shippingProvider =  ShippingProviders.objects.filter(carrier_id=sh.provider).first()
                provider_name = shippingProvider.carrier_name
                provider_link = shippingProvider.tracking_url.replace("{0}", sh.tracking_number)
                provider_link = f"<a class='text-primary link' target='_blank' href='{provider_link}'>{sh.tracking_number}</a>"

            shipping_details.append({
                "shipping_id": sh.po_shipping_id,
                "tracking_number": sh.tracking_number,
                "tracking_link": provider_link,
                "carrier_name": provider_name,
                "shipping_date": sh.shipped_date,
                "received_date": sh.received_date,
            })

        # Always append product (even if no shipping)
        data.append({
            "product_id": item.product_id,
            "product_name": product.title if product else "",
            "sku": product.sku if product else "",
            "ordered_qty": ordered_qty,
            "receive_item_id": po_recieved_item.received_item_id,
            "price": price,
            "line_total": line_total,
            "shipping_details": shipping_details  # EMPTY LIST OK
        })

    return JsonResponse({"data": data}, safe=False)


from decimal import Decimal
from django.http import JsonResponse
def get_invoice_rows(request, po_id):

    po_items = PurchaseOrderItem.objects.filter(po_id=po_id)

    data = []

    for item in po_items:
        product = Product.objects.filter(
            product_id=item.product_id
        ).only("title", "sku", "product_id").first()
        po_receive = PurchaseReceives.objects.filter(po_id=item.po_id).first()
        if not po_receive:
            return JsonResponse({"data": []}, safe=False)
        po_recieved_item = PurchaseReceivedItems.objects.filter(product_id=product.product_id,
                                                                po_receive_id=po_receive.po_receive_id).first()


        ordered_qty = Decimal(item.qty or 0)
        price = Decimal(item.price or 0)
        line_total = ordered_qty * price

        # Fetch invoice rows
        invoice_qs = PurchaseOrderInvoiceDetails.objects.filter(
            po_id=po_id,
            product_id=item.product_id
        )

        invoice_details = []
        for inv in invoice_qs:
            payment_term_name = ""
            if inv.payment_term_id:
                paymentTerm = PaymentTerm.objects.filter(id=inv.payment_term_id).first()
                if paymentTerm:
                    payment_term_name = paymentTerm.name

            invoice_details.append({
                "po_invoice_id": inv.po_invoice_id,
                "po_id": inv.po_id,
                "product_id": inv.product_id,
                "receive_id": inv.receive_id,
                "invoice_number": inv.invoice_number,
                "po_amount": inv.po_amount,
                "received_qty": inv.received_qty,
                "payment_status_id": inv.payment_status_id,
                "order_date": inv.order_date,
                "order_no": inv.order_no,
                "vendor_ref_no": inv.vendor_ref_no,
                "delivery_ref": inv.delivery_ref,
                "invoice_date": inv.invoice_date,
                "due_date": inv.due_date,
                "paid_date": inv.paid_date,
                "payment_term_id": inv.payment_term_id,
                "payment_term_name": payment_term_name,
            })

        # Always append product row
        data.append({
            "product_id": item.product_id,
            "receive_id": po_recieved_item.po_receive_id,
            "product_name": product.title if product else "",
            "sku": product.sku if product else "",
            "ordered_qty": ordered_qty,
            "price": price,
            "line_total": line_total,
            "invoice_details": invoice_details  # EMPTY LIST OK
        })

    return JsonResponse({"data": data})




