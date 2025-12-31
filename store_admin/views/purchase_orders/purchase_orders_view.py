import datetime
from time import timezone

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.expressions import d
from django.urls import reverse

from store_admin.helpers import name_validator_none, reference_validator, zip_validator, \
    get_prep_label, format_tax_percentage, validate_purchase_order_model, safe_df
from store_admin.models.organization_model import OrganizationInventoryLocation
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.address_model import Addresses
from django.db import transaction
from django.shortcuts import render, redirect
from store_admin.models.po_models.po_models import (PurchaseOrder, POApprovalStatus, PurchaseOrderItem,
                                                    PurchaseOrderShipping, \
                                                    PurchaseOrderVendor, PurchaseReceives, PurchaseReceivedItems,
                                                    PurchaseBills, PurchaseBillItems, PurchasePayments)
from store_admin.models.product_model import Product, ProductImages
from store_admin.models.setting_model import UnitOfMeasurements, ShippingProviders
from store_admin.models.vendor_models import Vendor, VendorAddress
from django.db.models import Min, Sum, F, Max
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
from django.db.models.functions import Coalesce
from decimal import ROUND_HALF_UP
from store_admin.views.libs.common import clean_percent
from store_admin.views.serializers.product_serializers import ProductImageSerializer
from decimal import Decimal, InvalidOperation


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
            status_id=POApprovalStatus.DRAFT  # Created / Draft
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

    shipping_details = PurchaseOrderShipping.objects.filter(po_id=po.po_id).first()
    vendor_po = PurchaseOrderVendor.objects.filter(po_id=po_id).first()
    shipping_providers = ShippingProviders.objects.filter(is_archived=0, status=1).all()
    #warehouse locations
    warehouse_locations = OrganizationInventoryLocation.objects.filter(organization_id=1).all()
    context = {
        'po_id': po_id,
        'po': po,
        'warehouse_locations': warehouse_locations,
        "vendor_po": vendor_po,
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



#UPDATE SAVE PO
#verified
@api_view(["POST"])
def save_po(request):
    data = request.data  # RAW JSON is captured here

    vendor_reference = data.get("vendor_reference")
    po_number = data.get("po_number")

    # Extract required fields
    vendor_id = data.get("vendor_id")
    po_id = data.get("po_id")
    vendor_name = data.get("vendor_name")
    currency_code = data.get("currency_code")
    vendor_reference = data.get("vendor_reference")
    invoice_date = data.get("invoice_date")
    warehouse = data.get("warehouse")
    order_date = data.get("order_date")
    delivery_date = data.get("delivery_date")
    payment_term_id = data.get("payment_term_id")
    delivery_name = data.get("delivery_name")
    address_line1 = data.get("address_line1")
    address_line2 = data.get("address_line2")
    suburb = data.get("suburb")
    state = data.get("state")
    city = data.get("city")
    comments = data.get("comments")
    post_code = data.get("post_code")
    surcharge_total = data.get("surcharge_total", "0.00")
    shipping_total = data.get("shipping_charge", "0.00")
    country = data.get("country")
    tax_percentage = data.get("tax_percentage")
    shipping_provider = data.get("shipping_provider")
    shipping_website = data.get("shipping_website")
    shipping_tracking_number = data.get("shipping_tracking_number")

    line_items = data.get("lineItems", [])
    # vendor PO details
    vendor_po_number = data.get("vendor_po_number")
    vendor_order_date = data.get("vendor_order_date")
    vendor_invoice_ref_number = data.get("vendor_invoice_ref_number")
    vendor_delivery_ref = data.get("vendor_delivery_ref")
    vendor_invoice_date = data.get("vendor_invoice_date")
    vendor_invoice_due_date = data.get("vendor_invoice_due_date")
    #po_status = data.get("po_status")

    # Simple validation
    if not vendor_id or not po_id:
        return Response({"error": "Invalid Operation"}, status=400)

    try:
        po = PurchaseOrder.objects.get(po_id=po_id)
    except PurchaseOrder.DoesNotExist:
        return Response({"error": "Invalid Operation"}, status=400)

    if len(line_items) == 0:
        return Response({"error": "At least one line item required"}, status=400)

    try:
        shipping_total = Decimal(str(shipping_total or "0"))
    except InvalidOperation:
        shipping_total = Decimal("0")

    po_vendor = Vendor.objects.get(id=vendor_id)

    with transaction.atomic():
        po.vendor_id = po_vendor.id
        po.vendor_code = po_vendor.vendor_code
        po.po_number = po_number
        po.vendor_name = vendor_name
        po.vendor_reference = vendor_reference
        po.currency_code = currency_code
        po.invoice_date = invoice_date
        po.warehouse_id = warehouse
        po.order_date = order_date
        po.payment_term_id = payment_term_id
        po.delivery_name = delivery_name
        po.address_line1 = address_line1
        po.address_line2 = address_line2
        po.suburb = suburb
        po.delivery_date = delivery_date
        po.state = state
        po.post_code = post_code
        po.country_id = country
        po.tax_percentage = tax_percentage
        po.city = city
        po.surcharge_total = surcharge_total
        po.shipping_charge = shipping_total

        po.comments = comments
        po.created_by = request.user.id
        if po.status_id != POApprovalStatus.APPROVED:
            po.status_id = POApprovalStatus.NEW #int(po_status)  # POStatus.CREATED

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
            print(item_tax_amount)
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

        '''
        for item in line_items:
            product_id = item["row_item"]["id"]
            tax_percentage = item["tax"]
            product = Product.objects.get(product_id=product_id)
            if product.is_taxable is True:
                tax_percentage = 0.0

            PurchaseOrderItem.objects.create(
                po_id=po.po_id,
                product_id=product_id,  # correct mapping
                qty=item["qty"],
                price=item["price"],
                tax_percentage=tax_percentage,  # percentage tax
                discount_percentage=item["discount"],
                order_ref=item["order_ref"],
                order_type=item["order_type"],
                created_by=request.user.id,
            )'''

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

        shipping_po = PurchaseOrderShipping.objects.filter(po_id=po.po_id).first()

        if shipping_po:
            shipping_po.delete()

        # CORRECTED CODE: Use unique keyword arguments (field names)
        PurchaseOrderShipping.objects.create(
            po_id=po.po_id,
            # Assuming these are the correct field names in your model:
            provider=shipping_provider,
            website=shipping_website,
            tracking_number=shipping_tracking_number,
            created_by=request.user.id
        )

        po_vendor_details = PurchaseOrderVendor.objects.filter(po_id=po.po_id).first()

        if po_vendor_details:
            po_vendor_details.delete()

        PurchaseOrderVendor.objects.create(
            po_id=po.po_id,
            po_number=vendor_po_number,
            order_date=vendor_order_date,  #
            invoice_ref_number=vendor_invoice_ref_number,  #
            delivery_ref_number=vendor_delivery_ref,  #
            invoice_date=vendor_invoice_date,  #
            invoice_due_date=vendor_invoice_due_date,  #
            created_by=request.user.id
        )

    return Response({"status": True, "message": "PO updated successfully"})

from django.utils.html import escape
from django.utils.dateformat import format as df
@login_required
@transaction.atomic
def approve_and_create_receive(request, po_id):
    #create PO Receive and approve
    try:
        po_detail = PurchaseOrder.objects.filter(po_id=po_id).first()
        if not po_detail:
            return JsonResponse({"status":False, "message": "Invalid PO Details",
                             "redirect_url":""})
        else:
            po_detail.status_id = POApprovalStatus.APPROVED
            po_detail.save(update_fields=["status_id"])

            po_next = (PurchaseReceives.objects.aggregate(max_id=Max("po_receive_id")).get("max_id") or 0) + 1
            po_receive_number = f"PR{po_next:04d}"

            receive = PurchaseReceives.objects.create(
                po_id=po_detail.po_id,
                vendor_id=po_detail.vendor_id,
                po_number=po_detail.po_number, #generate
                po_receive_number= po_receive_number,
                received_date= datetime.date.today(),
                shipping_date= datetime.date.today(),
                created_by= request.user.id,
            )
            po_items = PurchaseOrderItem.objects.filter(po_id=po_detail.po_id).all()
            # ---------- LINE ITEMS ----------
            items_created = 0
            received_qty = 0
            for po_item in po_items:
                product_id = po_item.product_id
                po_item_id = po_item.item_id
                #received_qty = po_item.pending_qty

                #po_item = PurchaseOrderItem.objects.filter(
              #      item_id=po_item.item_id,
              #      po_id=po_id
               # ).select_for_update().first()

                ordered_qty = po_item.ordered_qty
                current_pending = 0

                PurchaseReceivedItems.objects.create(
                    po_receive_id=receive.po_receive_id,
                    product_id=product_id,
                    item_id=po_item_id,
                    received_qty=received_qty,
                    created_by=request.user.id,
                    status_id=1
                )

                po_item.received_qty += received_qty
                po_item.pending_qty = max(ordered_qty - po_item.received_qty, 0)
                po_item.save(update_fields=["received_qty", "pending_qty"])

                items_created += 1

            return JsonResponse({"status": True, "message": "PO Receive created successfully",
                                 "redirect_url": reverse(
                "edit_po_receive_order",
                kwargs={"po_receive_id": receive.po_receive_id}
            )})
    except Exception as e:
        #  Any error → full rollback
        transaction.set_rollback(True)
        return JsonResponse({
            "status": False,
            "message": str(e),
            "redirect_url": ""
        })

#Approve PO Order
@login_required
def approve_po_order(request, po_id):
    from django.utils import timezone
    if po_id is None:
        return HttpResponse("Invalid PO", status=404)
    po = PurchaseOrder.objects.filter(po_id=po_id, is_archived=0, status_id=0).first()
    if not po:
        return JsonResponse({"status": True, "message": "Invalid PO Details"})
    else:
        po.status_id = POApprovalStatus.APPROVED
        po.updated_by = request.user.id
        po.updated_at = timezone.now()
        po.save(update_fields=["status_id","updated_by","updated_at"])

    return JsonResponse({"status":True, "message": "PO approved successfully"})

#View PO ORDER
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
    '''
    # 1. Calculate the total bill subtotal (EXCLUDING GST) first
    # This is necessary to determine the ratio each item contributes to the bill
    bill_subtotal_after_discount = 0
    for item in po_order_items:
        # Applying the 10% discount logic to get the true subtotal
        unit_base = float(item.price) * (1 - (float(item.discount_percentage) / 100.00))
        bill_subtotal_after_discount += unit_base * int(item.qty)

    # 2. Total additional fees to distribute
    addntl_totl = float(po.shipping_charge + po.surcharge_total)  # $350.00 in your example

    for po_order_item in po_order_items:
        # 3. Get the Discounted Unit Price
        base_price = float(po_order_item.price)
        discount_multiplier = 1 - (float(po_order_item.discount_percentage) / 100.00)
        discounted_price = base_price * discount_multiplier  # Result: e.g., $9.00

        line_subtotal = discounted_price * int(po_order_item.qty)

        # 4. FIXED: Value-Based Allocation
        # This replaces addntl_per_totl to ensure the total matches exactly
        # Logic: (This Line's Subtotal / Total Bill Subtotal) * Total Fees
        line_fee_share = (line_subtotal / bill_subtotal_after_discount) * addntl_totl

        # 5. Calculate Individual Landed Cost
        # Formula: (Product Cost + Fee Share) / Quantity
        rate_totl = (line_subtotal + line_fee_share) / int(po_order_item.qty)

        # Database and Image lookups
        po_product = Product.objects.filter(product_id=po_order_item.product_id).first()
        po_images = ProductImages.objects.filter(product_id=po_order_item.product_id).order_by(
            "product_image_id").first()

        line_items.append({
            "row_item": {
                "id": po_product.product_id,
                "title": po_product.title,
                "image": po_images.cdn_url if po_images else NO_IMAGE,
                "stock_qty": 0,
                "sku": po_product.sku,
                "asin": po_product.asin, "fnsku": po_product.fnsku, "ean": po_product.ean,
                "prep_type": get_prep_label(po_product.prep_type),
                "price": float(po_order_item.price),
                "order_type": po_order_item.order_type,
                "order_ref": po_order_item.order_ref,
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
            "cost_per_item": round(float(rate_totl), 2),  # Rounded for accuracy
        })'''

    tot_qty = 0
    for po_order_item in po_order_items:
        tot_qty += int(po_order_item.qty)
    
    addntl_totl = float(po.shipping_charge+po.surcharge_total) #landed cost calculation
    addntl_per_totl = float(addntl_totl / tot_qty) #landed cost calculation

    for po_order_item in po_order_items:
        # Calculate the Discounted Unit Price
        # Example: $50.00 * (1 - 0.10) = $45.00
        base_price = float(po_order_item.price) #landed cost calculation
        discount_multiplier = 1 - (float(po_order_item.discount_percentage) / 100.00) #landed cost calculation
        discounted_price = base_price * discount_multiplier #landed cost calculation

        po_product = Product.objects.filter(product_id=po_order_item.product_id).first()
        po_images = ProductImages.objects.filter(product_id=po_order_item.product_id).order_by("product_image_id").first()

        #landed cost calculation
        unit_total = addntl_per_totl*int(po_order_item.qty)
        rate_totl = (float(discounted_price)*int(po_order_item.qty))+unit_total
        rate_totl = rate_totl/int(po_order_item.qty) #individual landed cost
        #cost_per_item = cost_per_item+float(float(po_order_item.price)*int(po_order_item.qty))
        #rate_totl = rate_totl
        # EOF landed cost calculation

        line_items.append({
            "row_item": {
                "id": po_product.product_id,
                "title": po_product.title,
                "image": po_images.cdn_url if po_images else NO_IMAGE,
                "stock_qty": 0,  # if you have stock, replace 0
                "sku": po_product.sku,
                "asin":po_product.asin, "fnsku":po_product.fnsku, "ean":po_product.ean,
                "prep_type":get_prep_label(po_product.prep_type),
                "price": float(po_order_item.price),     # send as number for JS
                "order_type": po_order_item.order_type,  # send as number for JS
                "order_ref": po_order_item.order_ref,    # send as number for JS
                "is_taxfree":True if po_product.is_taxable else False,
            },
            "barcode_label_type":po_product.barcode_label_type,
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

    shipping_details = PurchaseOrderShipping.objects.filter(po_id=po.po_id).first()
    shipping_providers = ShippingProviders.objects.filter(is_archived=0, status=1).all()


    ################# PO LOGS #######################
    po_receives = PurchaseReceives.objects.filter(po_id=po.po_id).all()
    log_html = ""
    is_all_received = False
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

                if (po_item.ordered_qty - item.received_qty) != 0:
                    is_all_received = False
                else:
                    is_all_received = True

                log_html += (
                    "<tr>"
                    f"<td title='{escape(product.title) if product else ''}'>"
                    f"{escape(product.sku) if product else '-'}</td>"
                    f"<td class='text-right'>{po_item.ordered_qty if po_item else 0}</td>"
                    f"<td class='text-right'>{item.received_qty}</td>"
                    "</tr>"
                )

            log_html += "</tbody></table></div>"

            # ---------- PO BILLS ----------
            po_bills = PurchaseBills.objects.filter(
                po_receive_id=po_receive.po_receive_id
            )

            if po_bills.exists():
                log_html += (
                    "<div class='mb-3 pb-3 border-bottom'>"
                    "<div class='d-flex align-items-center mb-2'>"
                    "<i class='fa fa-file-invoice text-secondary mr-2'></i>"
                    "<span class='font-weight-bold'>PO Bills</span>"
                    "</div>"
                )

                for po_bill in po_bills:
                    log_html += (
                        f"<small><strong>Bill No:</strong> "
                        f"<a href=''>{escape(po_bill.bill_no)}</a><br>"
                        f"<strong>Bill Date:</strong> {safe_df(po_bill.bill_date, 'd M Y')}<br>"
                        f"<strong>Due Date:</strong> {safe_df(po_bill.due_date, 'd M Y')}<br>"
                        f"<strong>Created on:</strong> {safe_df(po_bill.created_at, 'd M Y H:i')} "
                        f"<strong>by</strong> {escape(str(StoreUser.objects.get(id=po_bill.created_by).name))}</small>"
                        f"<div><strong>Total:</strong> {po_bill.grand_total}</div><hr>"
                    )

                    # ---------- PO PAYMENTS (per bill) ----------
                    po_payments = PurchasePayments.objects.filter(
                        bill_id=po_bill.bill_id
                    )

                    if po_payments.exists():
                        log_html += (
                            "<div class='mt-2'>"
                            "<strong>Payments</strong><br>"
                        )

                        for po_payment in po_payments:
                            log_html += (
                                f"<small><strong>Payment #:</strong> "
                                f"<a href=''>{escape(po_payment.payment_no)}</a><br>"
                                f"<strong>Payment Date:</strong> "
                                f"{df(po_payment.payment_date, 'd M Y')}<br>"
                                f"<strong>Paid Amount:</strong> "
                                f"{po_payment.payment_made_amount}<br>"
                                f"<strong>Created on:</strong> "
                                f"{df(po_payment.created_at, 'd M Y H:i')} "
                                f"<strong>by</strong> "
                                f"{escape(str(StoreUser.objects.get(id=po_payment.created_by).name))}</small><br>"
                            )

                        log_html += "</div>"

                log_html += "</div>"
    else:
        log_html = "<div class='text-center text-muted'>--No transactions --</div> "
    #####################################################
    created_by = getUserName(po.created_by)
    po_receive = PurchaseReceives.objects.filter(po_id=po_id).first()
    context = {
        'po_id': po_id,
        'po_receive': po_receive,
        'po': po,
        'is_all_received': is_all_received,
        "shipping_providers": shipping_providers,
        "po_logs": log_html,
        'shipping':shipping_details,
        'can_pdf_generate':can_pdf_generate,
        'po_order_items':po_order_items,
        'user': request.user.id,
        'created_by':created_by,
        'payment_terms': payment_terms,
        'unit_of_measures': unit_of_measures,
        'line_items':line_items,
        'warehouses': warehouses,
        'country_list': countries_list,
        'currency_list': currency_list,
        'vendor':vendor_detail
    }
    return render(request, 'sbadmin/pages/purchase_order/view/view_po.html', context)


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
        rate_totl = rate_totl / int(po_order_item.qty)  # individual landed cost
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


def getUserName(user_id):
    return StoreUser.objects.get(id=user_id).name

#PDF GEnerate function
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

#delete PO Orders
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def delete_po(request, po_id):
    try:
        return JsonResponse({"status": False, "message": "Implemented soon!"})
        updated = PurchaseOrder.objects.filter(
            po_id=po_id,
            is_archived=0
        ).update(is_archived=1)
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


def d(v):
    return Decimal(str(v or 0))

@api_view(["GET"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def all_purchases(request):
    # 1. Setup Subqueries for Annotations
    warehouse_sub = Warehouse.objects.filter(
        warehouse_id=OuterRef("warehouse_id")
    ).values("warehouse_name")[:1]

    vendor_sub = Vendor.objects.filter(
        id=OuterRef("vendor_id")
    ).values("display_name")[:1]

    po_vendor_sub = PurchaseOrderVendor.objects.filter(
        po_id=OuterRef("po_id")
    ).values("po_number")[:1]

    # 2. Base QuerySet (Define this FIRST)
    qs = PurchaseOrder.objects.filter(
        is_archived=0,
        vendor_id__isnull=False,
        vendor_code__isnull=False
    ).annotate(
        warehouse_name=Coalesce(Subquery(warehouse_sub), Value(""), output_field=TextField()),
        vendor_name_val=Coalesce(Subquery(vendor_sub), Value(""), output_field=TextField()),
        po_vendor_ref=Coalesce(Subquery(po_vendor_sub), Value(""), output_field=TextField()),
        subtotal_val=Coalesce("sub_total", Value(0, DecimalField())),
        tax_val=Coalesce("tax_total", Value(0, DecimalField())),
        total_val=Coalesce("summary_total", Value(0, DecimalField())),
    ).order_by("-created_at")

    # 3. Apply Filters (Get params from request)
    status = request.GET.get("status")
    if status and status != "All" and status != "":
        # Map string status to your integer ID if necessary
        # Example: if "Open" is stored as 0 in DB
        status_map = {"Open": 0, "Approved": 1, "Delivered": 4} # Adjust to your logic
        actual_status = status_map.get(status, status)
        qs = qs.filter(status_id=actual_status)

    order_no = request.GET.get("order_no")
    if order_no:
        qs = qs.filter(po_number__icontains=order_no)

    vendor_id = request.GET.get("vendor_id")
    if vendor_id:
        qs = qs.filter(vendor_id=vendor_id)

    vendor_ref = request.GET.get("vendor_ref")
    if vendor_ref:
        qs = qs.filter(vendor_reference__icontains=vendor_ref)

    warehouse = request.GET.get("warehouse")
    if warehouse:
        # Filtering on the annotated 'warehouse_name'
        qs = qs.filter(warehouse_name__icontains=warehouse)

    supplier_ref = request.GET.get("supplier_ref")
    if supplier_ref:
        # Filtering on the annotated 'po_vendor_ref'
        qs = qs.filter(po_vendor_ref__icontains=supplier_ref)

    # 4. Global Search (q)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(po_number__icontains=q) |
            Q(vendor_name_val__icontains=q) |
            Q(vendor_reference__icontains=q)
        )

    # 5. Pagination (Optional but recommended for Tabulator)
    # total_count = qs.count()
    # ... apply slicing ...

    # 6. Return Data
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
        "po_id","po_number", "vendor_id", "vendor_code", "vendor_name", "currency_code", "vendor_reference",
        "order_date", "delivery_date", "invoice_date", "delivery_name", "created_at", "status_id", "sub_total",
        "summary_total", "shipping_charge", "surcharge_total","tax_total",
        "warehouse_name", "po_vendor_ref", "vendor_name_val","vendor_name", "subtotal_val",
        "tax_val", "total_val"
    ))
    '''select po recent status detail'''
    for po_data in data:
        '''select purchase receive - get how many qty received 
        how many qty '''
        po_vendor_detail = PurchaseOrderVendor.objects.filter(po_id=po_data.get("po_id")).first()
        if po_vendor_detail:
            po_data["po_vendor_po_number"] = po_vendor_detail.po_number
            po_data["po_vendor_order_date"] = po_vendor_detail.order_date
            po_data["po_vendor_invoice_date"] = po_vendor_detail.invoice_date
            po_data["po_vendor_invoice_due_date"] = po_vendor_detail.invoice_due_date
            po_data["po_vendor_invoice_ref_number"] = po_vendor_detail.invoice_ref_number
            po_data["po_vendor_delivery_ref_number"] = po_vendor_detail.delivery_ref_number
        else:
            po_data["po_vendor_po_number"] = ""
            po_data["po_vendor_order_date"] = ""
            po_data["po_vendor_invoice_date"] = ""
            po_data["po_vendor_invoice_due_date"] = ""
            po_data["po_vendor_invoice_ref_number"] = ""
            po_data["po_vendor_delivery_ref_number"] = ""

        vendor_shipping_det = PurchaseOrderShipping.objects.filter(
            po_id=po_data.get("po_id")
        ).first()

        if po_vendor_detail:
            shipping_provider = None

            if vendor_shipping_det and vendor_shipping_det.provider:
                shipping_provider = ShippingProviders.objects.filter(
                    carrier_id=vendor_shipping_det.provider
                ).first()

            po_data["vendor_shipping_company"] = (
                shipping_provider.carrier_name if shipping_provider else ""
            )

            po_data["vendor_shipping_tracking_no"] = (
                vendor_shipping_det.tracking_number if vendor_shipping_det else ""
            )

            po_data["vendor_shipping_tracking_link"] = (
                shipping_provider.tracking_url.replace(
                    "{0}", vendor_shipping_det.tracking_number
                )
                if shipping_provider
                   and vendor_shipping_det
                   and vendor_shipping_det.tracking_number
                   and shipping_provider.tracking_url
                else ""
            )
            po_shipping_date = None
            po_received_date = None
            po_receives = PurchaseReceives.objects.filter(po_id=po_data.get("po_id")).last()

            if po_receives:
                po_received_date = po_receives.received_date
                po_shipping_date = po_receives.shipping_date

            po_data["vendor_shipping_date"] = po_shipping_date  # porecive shipping date
            po_data["vendor_delivery_date"] = po_received_date #porecive recvd date

        else:
            po_data.update({
                "vendor_shipping_company": "",
                "vendor_shipping_tracking_no": "",
                "vendor_shipping_tracking_link": "",
                "vendor_shipping_date": "",
                "vendor_delivery_date": "",
            })

        po_order_items = PurchaseOrderItem.objects.filter(po_id=po_data.get("po_id")).all()
        po_data["total_order_qty"] = po_order_items.aggregate(total_qty=Sum("ordered_qty"))["total_qty"] or 0
        po_data["total_received_qty"] = po_order_items.aggregate(received_qty=Sum("received_qty"))["received_qty"] or 0
        #687.50 +100+250+62.50



        tax_rate = d(po_data.get("tax_total")) / d(po_data.get("sub_total") or 1)

        shipping_surcharge = (
                d(po_data.get("shipping_charge")) +
                d(po_data.get("surcharge_total"))
        )

        shipping_tax = (shipping_surcharge * tax_rate).quantize(
            Decimal("0.00"), rounding=ROUND_HALF_UP
        )

        grand_total = (
                d(po_data.get("summary_total")) +
                shipping_surcharge +
                shipping_tax
        ).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        po_data["grand_total"] =  format(grand_total, ".2f")

        status_id = d(po_data.get("status_id"))
        if status_id >= 1:
            # 1. Check Shipping Details
            # If a tracking number exists, the initial status becomes "Shipped"
            shipping_exists = PurchaseOrderShipping.objects.filter(po_id=po_data.get("po_id")).first()
            if shipping_exists and shipping_exists.tracking_number:
                po_data["status_id"] = 2  # Shipped

            # 2. Calculate Totals for Items
            po_items = PurchaseOrderItem.objects.filter(po_id=po_data.get("po_id"))
            totals = po_items.aggregate(
                total_ordered=Sum('ordered_qty'),
                total_received=Sum('received_qty')
            )

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
        #po_data["status_detail"] = "New"
        #po_data["pending_amount"] = "New"

    last_page = math.ceil(total / size) if total else 1

    #  Return EXACT Tabulator compatible JSON
    return Response({
        "data": data,
        "last_page": last_page,
        "total": total, "row_count":200

    })


@api_view(["GET"])
def list_product_images(request, product_id):
    q = ProductImages.objects.filter(product_id=request.GET.get("product_id")) if request.GET.get("product_id") else ProductImages.objects.all()
    return JsonResponse(ProductImageSerializer(q, many=True).data)


