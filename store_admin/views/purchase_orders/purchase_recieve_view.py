from django.core.exceptions import ValidationError

from store_admin.helpers import getUserName, name_validator_none, reference_validator,  \
    zip_validator, \
     format_tax_percentage, getPaymentTermName
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.address_model import Addresses
from django.shortcuts import render
from django.db import connection
from store_admin.models.po_models.po_models import PurchaseOrder, POStatus, PurchaseOrderItem, \
    PurchaseReceiveFiles, \
    PurchaseReceivedItems, PurchaseReceives, PurchaseOrderShipping, PurchaseOrderInvoiceDetails, \
    PurchaseOrderVendorDetails, POReceiveStatus
from store_admin.models.po_models.po_receipt_model import PurchaseReceiptItem, PurchaseReceipt
from store_admin.models.product_model import Product, ProductImages
from store_admin.models.setting_model import ShippingProviders
from store_admin.models.vendor_models import Vendor, VendorAddress
from store_admin.models import Country, State
from store_admin.models.warehouse_setting_model import Warehouse
from django.templatetags.static import static
from django.contrib.auth.decorators import login_required
import math
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Q
from rest_framework.renderers import JSONRenderer
from rest_framework.decorators import renderer_classes, permission_classes

from rest_framework.decorators import  permission_classes
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.template.loader import render_to_string
from django.http import HttpResponse
from weasyprint import HTML
from django.db.models import OuterRef, Subquery, Value, TextField, DecimalField
from django.db.models.functions import Coalesce
from store_admin.views.libs.common import clean_percent
from store_admin.views.purchase_orders.purchase_orders_view import calculate_product_landed_cost, get_po_invoice_totals, \
    approve_and_create_receive, approve_and_create_receive_internal
import re
from django.views.decorators.http import require_GET
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.http import JsonResponse
from decimal import Decimal
import json
from decimal import Decimal, InvalidOperation
from copy import copy

@require_GET
def get_api_po_receive(request):
    po_receive_id = request.GET.get("po_receive_id")

    if not po_receive_id:
        return JsonResponse(
            {"status": False, "message": "Invalid PO Receive ID"},
            status=400
        )

    po = PurchaseReceives.objects.filter(po_receive_id=po_receive_id).first()
    if not po:
        return JsonResponse(
            {"status": False, "message": "Invalid PO"},
            status=404
        )

    # Fetch received items
    po_order_items = PurchaseReceivedItems.objects.filter(
        po_receive_id=po_receive_id
    )

    # Prefetch related data to avoid N+1
    product_map = {
        p.product_id: p
        for p in Product.objects.filter(
            product_id__in=po_order_items.values_list("product_id", flat=True)
        )
    }

    order_item_map = {
        i.item_id: i
        for i in PurchaseOrderItem.objects.filter(
            item_id__in=po_order_items.values_list("item_id", flat=True)
        )
    }

    line_items = []
    for item in po_order_items:
        product = product_map.get(item.product_id)
        order_item = order_item_map.get(item.item_id)

        line_items.append({
            "product_id": order_item.product_id,
            "item_name": product.title if product else "",
            "sku": product.sku if product else "",
            "ordered_qty": order_item.qty if order_item else 0,
            "received_qty": item.received_qty,
            "status_id": item.status_id,

        })


    received_files = list(
        PurchaseReceiveFiles.objects.filter(
            po_receive_id=po_receive_id
        ).values(
            "po_order_receive_file_id",
            "image_path",
            "uploaded_at"
        )
    )

    context = {
        "po_receive_id": po_receive_id,
        "po": {
            "po_id": po.po_id,
            "vendor_id": po.vendor_id,
            "status_id": po.status_id,
            "created_at": po.created_at,
        },
        "created_by": getUserName(po.created_by),
        "line_items": line_items,
        "received_files": received_files,
    }
    return JsonResponse({"status": True, "data": context})

def validate_purchase_order_model(po, line_items):
    rules = [
        ("vendor_id",       "Vendor is required"),
        ("po_number",       "PO Number is required."),
        ("currency_code",   "Currency Code is required"),
        ("warehouse_id",    "Warehouse is required"),
        ("order_date",      "Order Date is required"),
        ("payment_term_id", "Payment Term is required"),
        ("delivery_name",   "Delivery Name is required"),
        ("address_line1",   "Address Line 1 is required"),
        ("state",           "State is required"),
        ("post_code",       "Postcode is required"),
        ("country_id",      "Country is required"),
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
    po.status_id = POStatus.PLACED
    po.save(update_fields=["status_id"])

    return JsonResponse({"status":True, "message":"PO Placed"})

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

def get_shipping_details(request, po_id):
    po_receive = PurchaseReceives.objects.filter(po_id=po_id).first()
    if not po_receive:
        return JsonResponse({"data": []})

    sql = """SELECT shipd.tracking_number, \
                    shipd.provider, \
                    shipd.po_id, \
                    shipd.receive_id, \
                    MIN(shipd.shipped_date)  AS shipped_date, \
                    MAX(shipd.received_date) AS received_date, \

                    JSON_ARRAYAGG( \
                            JSON_OBJECT( \
                                    'product_id', shipd.po_item_id, \
                                    'received_qty', rcve.received_qty \
                            ) \
                    )                        AS items

             FROM store_admin_purchase_order_shipping_details AS shipd
                      LEFT JOIN store_admin_purchase_received_items AS rcve
                                ON rcve.po_receive_id = shipd.receive_id
                                    AND rcve.product_id = shipd.po_item_id

             WHERE shipd.is_archived = 0
               AND shipd.receive_id = %s

             GROUP BY shipd.tracking_number, \
                      shipd.provider, \
                      shipd.po_id, \
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
                "tracking_number": f"<a class='link' target='_blank' href='{provider_link}'>{tracking_number}</a>",
                "provider": provider_name,
                "po_id": po_id,
                "receive_id": receive_id,
                "shipped_date": shipped_date,
                "received_date": received_date,
                "line_items": data_items,
            })
        return JsonResponse({"status": True, "message": "", "data": data})

def save_po_receive_full(request):
    return JsonResponse(
        {"status": True, "message": "PO receive completed successfully"}
    )


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

@api_view(["GET"])
def intransit_listing(request):
    # ---- Context ----
    all_vendors = Vendor.objects.all()

    context = {
        "vendors":all_vendors,
        "user": request.user.id,
    }

    return render(request, 'sbadmin/pages/bills/all_po_intransit_listing.html', context)

def po_tracking_listing(request):
    # ---- Context ----
    all_vendors = Vendor.objects.all()

    context = {
        "vendors":all_vendors,
        "user": request.user.id,
    }

    return render(request, 'sbadmin/pages/bills/all_po_tracking_listing.html', context)

@api_view(["GET"])
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

    #if tracking_no:
    #    print(tracking_no)

    return JsonResponse({
        "status": True,
        "data": data
    })

@api_view(["GET"])
def get_po_receive_details(request, po_receive_id):
    po_receive = PurchaseReceives.objects.filter(po_receive_id=po_receive_id).first()
    if not po_receive:
        return JsonResponse({"status": False, "message": "Invalid PO Receive "+po_receive_id}, status=404)

    po_id = po_receive.po_id

    po = PurchaseOrder.objects.filter(po_id=po_id, is_archived=0).first()
    if not po:
        return JsonResponse({"status": False, "message": "Invalid PO"}, status=404)

    po = PurchaseOrder.objects.filter(po_id=po_id, is_archived=0).first()
    if not po:
        return JsonResponse({"status":False, "message":"Invalid PO" }, status=404)

    inv_payment_details = get_po_invoice_totals(po_id)
    total_raised = total_paid = total_pending = Decimal(0.0)
    if inv_payment_details is not None:
        total_raised, total_paid, total_pending = inv_payment_details

    po_order_items = PurchaseOrderItem.objects.filter(po_id=po_id).all()

    line_items = []

    NO_IMAGE = request.build_absolute_uri(
        static("sbadmin/dist/img/no_product_image.png")
    )

    # Build Response
    total_po_landed_cost = Decimal("0.00")
    landed_cost_total = 0.0
    for po_order_item in po_order_items:
        po_product = Product.objects.filter(product_id=po_order_item.product_id).first()
        po_images = ProductImages.objects.filter(product_id=po_order_item.product_id).order_by(
            "product_image_id").first()

        result = calculate_product_landed_cost(po_id, po_order_item.product_id)
        cost_exc_gst = cost_inc_gst = 0.0

        po_receive_item = PurchaseReceivedItems.objects.filter(po_receive_id=po_receive_id, product_id=po_product.product_id).first()
        if result is not None:
            cost_exc_gst, cost_inc_gst = result  # already Decimal

            qty = Decimal(po_order_item.qty or 0)

            landed_cost_total = cost_inc_gst * qty
            total_po_landed_cost += landed_cost_total

        line_items.append({
            "row_item": {
                "id": po_product.product_id,
                "title": po_product.title,
                "image": po_images.cdn_url if po_images else NO_IMAGE,
                "stock_qty": 0,  # if you have stock, replace 0
                "sku": po_product.sku,
                "asin": po_product.asin, "fnsku": po_product.fnsku, "ean": po_product.ean,
                "prep_type": "", # get_prep_label(po_product.prep_type),
                "product_order_type": "", #po_product.order_type,  # send as number for JS
                "product_order_ref": "", #po_product.order_ref,  # send as number for JS
                "is_taxable": True if po_product.is_taxable else False,
            },
            "barcode_label_type": po_product.barcode_label_type,
            "qty": int(po_order_item.qty),
            "price": float(po_order_item.price),
            "landed_cost_ex_gst": cost_exc_gst, #calculate
            "landed_cost_inc_gst": cost_inc_gst, #calculate
            "discount": float(po_order_item.discount_percentage),
            "comment": po_order_item.comment,
            "delivery_date": po_order_item.delivery_date,
            "tax": float(po_order_item.tax_percentage),
            "tax_amount": float(po_order_item.tax_amount),
            "sub_total": float(po_order_item.subtotal),
            "receive_item_details": {
                "received_item_id": po_receive_item.received_item_id if po_receive_item else None,
                "po_receive_id": po_receive_item.po_receive_id  if po_receive_item else None,
                "product_id": po_receive_item.product_id if po_receive_item else None,
                "received_qty": po_receive_item.received_qty if po_receive_item else None,
                "status_id": po_receive_item.status_id  if po_receive_item else None
            },
            "line_total": float(po_order_item.line_total),
        })

    can_pdf_generate, err_msg = validate_purchase_order_model(po, line_items)
    receive_generated = False
    all_received = False

    if PurchaseReceives.objects.filter(po_id=po_id).exists():
        receive_generated = True
        po_receive_id = PurchaseReceives.objects.filter(po_id=po_id).first().po_receive_id

        for po_order_item in po_order_items:
            if po_order_item.pending_qty == 0:
                all_received = True

    #payment_terms = PaymentTerm.objects.all()
    #shipping_details = PurchaseOrderShipping.objects.filter(po_id=po.po_id).all()
    po_vendor_details = PurchaseOrderVendorDetails.objects.filter(po_id=po_id).all()
    vendor_dets = Vendor.objects.filter(id=po.vendor_id).first()
    #shipping_providers = ShippingProviders.objects.filter(is_archived=0, status=1).all()
    #warehouse locations
    #warehouse_locations = OrganizationInventoryLocation.objects.filter(organization_id=1).all()'po)state_id
    po_state_id = None
    if po.state and str(po.state).isdigit():
        if State.objects.filter(id=po.state).exists():
            po_state_id = State.objects.filter(id=po.state).first().id

    po_state_name = None
    po_country_name = None

    try:
        po_state_name = State.objects.get(id=int(po.state)).name
    except (State.DoesNotExist, ValueError, TypeError):
        pass

    try:
        po_country_name = Country.objects.get(id=int(po.country_id)).name
    except (Country.DoesNotExist, ValueError, TypeError):
        pass

    purchase_invoices = PurchaseOrderInvoiceDetails.objects.filter(po_id=po_id).all()
    po_invoices = []
    for purchase_invoices in purchase_invoices:
        po_invoices.append({
            "po_invoice_id": purchase_invoices.po_invoice_id,
            "invoice_number": purchase_invoices.invoice_number,
            "invoice_date": purchase_invoices.invoice_date,
            "due_date": purchase_invoices.due_date,
            "payment_status_id": purchase_invoices.payment_status_id,
            "payment_term_id": purchase_invoices.payment_term_id,
            "invoice_total": purchase_invoices.invoice_total,
        })

    context = {
        "po_id": po_id,
        "can_pdf_generate":can_pdf_generate,
        "receive_generated":receive_generated,
        "po_receive_id": po_receive_id,
        "all_received": all_received,
        "po_invoices": po_invoices,
        "preferred_shipping_provider": vendor_dets.preferred_shipping_provider,
        "po": {
            "created_by_name" : getUserName(po.created_by),
            "total_po_landed_cost" : total_po_landed_cost,
            "created_at": po.created_at.strftime("%b %d, %Y, %I:%M %p"),
            "currency_code": po.currency_code,
            "po_id": po.po_id,
            "po_number": po.po_number,
            "sbpo_order_date": po.order_date,
            "sb_po_delivery_date": po.delivery_date,
            "global_tax_rate": po.global_tax_rate,
           # "tax_percentage": float(po.tax_percentage),
            "minimum_order_value": po.minimum_order_value,
            "global_discount_percentage": po.global_discount_percentage,
            "warehouse_id": po.warehouse_id,
            "po_delivery_name": po.delivery_name,
            "po_address_line1": po.address_line1,
            "po_address_line2": po.address_line2,
            "po_city": po.city,
            "po_state": po.state,
            "po_state_name": po_state_name,
            "po_country_name": po_country_name,
            "po_state_id": po_state_id,
            "po_zip": po.post_code,
            "po_country":po.country_id,

            "vendor_code": po.vendor_code,
            "vendor_id": po.vendor_id,
            "vendor_name": po.vendor_name,
            "vendor_payment_term_name": getPaymentTermName(vendor_dets.payment_term) if vendor_dets else None,
            "status_id": po.status_id,

            "comments": po.comments,
            "shipping_charge": po.shipping_charge,
            "surcharge_total": po.surcharge_total,

            "summary_total": po.summary_total,
            "invoice_total": total_raised,
            "invoice_paid": total_paid,
            "invoice_balance": total_pending,

            "tax_total": po.tax_total,
            "sub_total": po.sub_total,
            "landed_cost_total": float(landed_cost_total),
        },
        "po_vendor_details": list(
            po_vendor_details.values(
                "po_vendor_id",
                "vendor_po_number",
                "order_number",
                "order_date",
                "is_primary"
            )
        ),
        "receive_details": {
            "po_receive_id": po_receive.po_receive_id,
            "po_receive_number": po_receive.po_receive_number,
            "received_date": po_receive.received_date,
            "status_id": po_receive.status_id,
            "internal_ref_notes": po_receive.internal_ref_notes,
            "created_at": po_receive.created_at.strftime("%b %d, %Y, %I:%M %p"),
            "created_by": getUserName(po_receive.created_by),
            "is_billed": po_receive.is_billed,
            "po_id": po_receive.po_id,
        },
        "line_items": line_items,
    }

    return JsonResponse({"status":True, "message":"success", "data":context})

@api_view(["GET"])
def get_all_receipts(request, po_id):

    if not po_id:
        return Response({"status": False, "message": "po_id is required"}, status=400)

    receipts = PurchaseReceipt.objects.filter(po_id=po_id).order_by("-created_at")

    item_list = []
    sl_no = 1

    for receipt in receipts:
        items = PurchaseReceiptItem.objects.filter(po_receipt_id=receipt.po_receipt_id)

        for item in items:
            po_line = PurchaseOrderItem.objects.filter(
                po_id=po_id,
                product_id=item.product_id
            ).first()

            invoice = PurchaseOrderInvoiceDetails.objects.filter(
                po_invoice_id=item.po_invoice_id
            ).first()

            product = Product.objects.filter(
                product_id=item.product_id
            ).first()

            price = float(po_line.price) if po_line else 0
            discount = float(po_line.discount_percentage) if po_line else 0
            gst_percent = float(po_line.tax_percentage) if po_line else 0
            qty = int(po_line.qty) if po_line else 0
            discount_price = price * (1 - discount / 100)
            line_total = float(po_line.line_total) if po_line else 0

            item_list.append({
                "sl_no": sl_no,
                "po_receipt_id": receipt.po_receipt_id,
                "invoice_number": invoice.invoice_number if invoice else "-",
                "invoice_amount": float(invoice.invoice_total) if invoice else 0,
                "product_title": product.title if product else "-",
                "product_sku": product.sku if product else "-",
                "product_asin": product.asin if product else "-",
                "price": price,
                "discount": discount,
                "discount_price": discount_price,
                "line_total": line_total,
                "gst_rate": gst_percent,
                "received_date": item.received_date,
                "comment": receipt.comments if po_line else "-",
                "qty_ordered": qty,
                "receipt_qty": item.received_qty,
            })
            sl_no += 1

    return JsonResponse({
        "status": True,
        "message": "success",
        "data": item_list
    })

#split receive completed
@api_view(["POST"])
@transaction.atomic
def save_po_receive_complete(request):
    try:
        data = json.loads(request.body)
        po_receive_id = data.get("po_receive_id")
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"status": False, "message": "Invalid JSON"}, status=400)

    if not po_receive_id:
        return JsonResponse({"status": False, "message": "Invalid PO details"}, status=400)

    original_receive = PurchaseReceives.objects.filter(po_receive_id=po_receive_id).first()
    if not original_receive:
        return JsonResponse({"status": False, "message": "Invalid PO Receive"}, status=400)

    try:
        po_detail = PurchaseOrder.objects.get(po_id=original_receive.po_id)
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({"status": False, "message": "Purchase Order not found"}, status=404)

    # Current PO items — ordered vs received
    po_items       = PurchaseOrderItem.objects.filter(po_id=po_detail.po_id)
    total_ordered  = sum(Decimal(str(i.qty or 0)) for i in po_items)
    total_received = sum(Decimal(str(i.received_qty or 0)) for i in po_items)

    if total_received >= total_ordered:
        receive_status = POReceiveStatus.COMPLETED          # 3
        po_status      = POStatus.COMPLETED                 # 4
    else:
        receive_status = POReceiveStatus.PARTIALLY_RECEIVED # 2
        po_status      = POStatus.RECEIPTED                 # 3

    # Update current receive + PO
    PurchaseReceives.objects.filter(po_receive_id=po_receive_id).update(
        status_id = receive_status
    )
    PurchaseOrder.objects.filter(po_id=po_detail.po_id).update(
        status_id = po_status
    )

    # ── Root PO-வா இல்லை Sub PO-வா ──
    is_root_po = po_detail.parent_po_id is None

    if not is_root_po:
        # Parent PO எடு — validate பண்ணி status update
        parent_po = PurchaseOrder.objects.filter(po_id=po_detail.parent_po_id).first()
        if parent_po:
            parent_items    = PurchaseOrderItem.objects.filter(po_id=parent_po.po_id)
            parent_ordered  = sum(Decimal(str(i.qty or 0)) for i in parent_items)
            parent_received = sum(Decimal(str(i.received_qty or 0)) for i in parent_items)

            if parent_received >= parent_ordered:
                parent_status = POStatus.COMPLETED   # 4
            else:
                parent_status = POStatus.RECEIPTED   # 3

            PurchaseOrder.objects.filter(po_id=parent_po.po_id).update(
                status_id = parent_status
            )

    return JsonResponse({
        "status"        : True,
        "message"       : "PO-Receive completed successfully",
        "po_status"     : po_status,
        "receive_status": receive_status,
    })


@api_view(["POST"])
@transaction.atomic
def save_complete_received(request):

    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid method"})

    try:
        data = json.loads(request.body)
        po_receive_id = data.get("po_receive_id")
        comments = data.get("comments")
        line_items = data.get("lineItems", [])
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"status": False, "message": "Invalid JSON"}, status=400)

    if not po_receive_id:
        return JsonResponse({"status": False, "message": "Invalid PO details"}, status=400)

    po_receive = PurchaseReceives.objects.filter(po_receive_id=po_receive_id).first()
    if not po_receive:
        return JsonResponse({"status": False, "message": "Invalid PO details"}, status=400)

    po_id = po_receive.po_id

    try:
        primary_po = PurchaseOrder.objects.get(po_id=po_id)
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({"status": False, "message": "Purchase Order not found"}, status=404)

    primary_po_items = PurchaseOrderItem.objects.filter(po_id=po_id)

    # -------------------------------------------------
    # STAGE 1 — Update received quantities
    # -------------------------------------------------
    for line_item in line_items:
        rid = line_item.get("receive_item_details", {}).get("received_item_id")
        rqty = Decimal(str(line_item.get("receive_item_details", {}).get("received_qty", 0)))

        po_received_item = PurchaseReceivedItems.objects.filter(received_item_id=rid).first()
        if po_received_item:
            po_received_item.received_qty = rqty
            po_received_item.save(update_fields=["received_qty"])

    # -------------------------------------------------
    # STAGE 2 — Mark all PO items as fully received
    # -------------------------------------------------
    for item in primary_po_items:
        item.received_qty = item.qty
        item.pending_qty = Decimal("0")
        item.save(update_fields=["received_qty", "pending_qty"])

    # -------------------------------------------------
    # STAGE 3 — Update Statuses
    # -------------------------------------------------
    primary_po.status_id = POStatus.COMPLETED
    primary_po.save(update_fields=["status_id"])

    po_receive.status_id = POStatus.COMPLETED
    po_receive.save(update_fields=["status_id"])

    return JsonResponse({
        "status": True,
        "message": "Receipt completed successfully"
    })



#Save Complete Receipt
@api_view(["POST"])
def save_po_receipt(request):
    data = request.data

    po_id = data.get("po_id")
    po_receive_id = data.get("po_receive_id", None)
    comments = data.get("comments", "")
    is_complete = data.get("is_complete", False)
    line_items = data.get("lineItems", [])

    if not po_id:
        return Response({"status": False, "message": "PO ID is required"}, status=400)

    if not line_items:
        return Response({"status": False, "message": "No line items provided"}, status=400)

    # Validate each line item has required fields
    po_invoice_id = None
    for i, item in enumerate(line_items):
        if not item.get("product_id"):
            return Response({"status": False, "message": f"Product ID missing in item {i+1}"}, status=400)
        if not item.get("po_invoice_id"):
            return Response({"status": False, "message": f"Invoice ID missing in item {i+1}"}, status=400)
        else:
            po_invoice_id = item.get("po_invoice_id")

    poInvoice = PurchaseOrderInvoiceDetails.objects.filter(po_invoice_id=po_invoice_id).first()

    receipt = PurchaseReceipt.objects.create(
        po_id=po_id,
        po_receive_id=po_receive_id,
        comments=comments,
        status_id=1,
        po_invoice_id = po_invoice_id,
        receipt_total = Decimal(poInvoice.invoice_total),
        created_by = request.user.id,
    )

    receipt_items = []

    for item in line_items:
        receipt_items.append(PurchaseReceiptItem(
            po_receipt_id=receipt.po_receipt_id,
            product_id=item.get("product_id"),
            po_invoice_id=po_invoice_id,
            received_date=item.get("received_date", None),
            received_qty=item.get("received_qty", 0),
        ))

    PurchaseReceiptItem.objects.bulk_create(receipt_items)

    receipt.save(update_fields=["po_invoice_id"])

    po_detail = PurchaseOrder.objects.filter(po_id=po_id).first()

    if is_complete:
        po_detail.status_id = POStatus.COMPLETED
    else:
        po_detail.status_id = POStatus.RECEIPTED  # 3

    po_detail.save(update_fields=["status_id"])

    return Response({
        "status": True,
        "message": "Receipt saved successfully",
        "po_receipt_id": receipt.po_receipt_id
    })

@api_view(["POST"])
@transaction.atomic
def save_split_receive(request):
    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid method"})

    try:
        data          = json.loads(request.body)
        po_receive_id = data.get("po_receive_id")
        comments      = data.get("comments")
        line_items    = data.get("lineItems", [])
        is_complete   = data.get("is_complete", False)
        po_invoice_id = None
        for item in line_items:
            if item.get("po_invoice_id"):
                po_invoice_id = item.get("po_invoice_id")
                break
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"status": False, "message": "Invalid JSON"}, status=400)

    if not po_receive_id:
        return JsonResponse({"status": False, "message": "Invalid PO details"}, status=400)

    po_receive = PurchaseReceives.objects.filter(po_receive_id=po_receive_id).first()
    if not po_receive:
        return JsonResponse({"status": False, "message": "Invalid PO details"}, status=400)

    po_id = po_receive.po_id

    try:
        primary_po = PurchaseOrder.objects.get(po_id=po_id)
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({"status": False, "message": "Purchase Order not found"}, status=404)

    source_po_id = primary_po.po_id
    root_po_id   = primary_po.parent_po_id if primary_po.parent_po_id is not None else primary_po.po_id

    primary_sub_total     = Decimal("0")
    primary_tax_total     = Decimal("0")
    primary_summary_total = Decimal("0")
    sub_sub_total         = Decimal("0")
    sub_tax_total         = Decimal("0")
    sub_summary_total     = Decimal("0")

    # Build received_map from line_items directly
    received_map = {}
    for line_item in line_items:
        pid     = int(line_item.get("product_id"))
        po_item = PurchaseOrderItem.objects.filter(po_id=source_po_id, product_id=pid).first()
        rqty    = Decimal(str(line_item.get("received_qty", 0)))
        if po_item:
            received_map[pid] = {
                "received_qty"  : rqty,
                "ordered_qty"   : Decimal(str(po_item.qty or 0)),
                "received_date" : line_item.get("received_date", None),
                "po_invoice_id" : line_item.get("po_invoice_id", None),
            }

    # -------------------------------------------------
    # STAGE 1 — Update PurchaseReceivedItems
    # Source PO + Parent PO receive records update
    # -------------------------------------------------
    for pid, item_data in received_map.items():
        rqty = item_data.get("received_qty", Decimal("0"))

        # ── Source PO received item update ──
        po_received_item = PurchaseReceivedItems.objects.filter(
            po_receive_id=po_receive_id,
            product_id=pid,
        ).first()
        if po_received_item:
            po_received_item.received_qty = rqty
            po_received_item.save(update_fields=["received_qty"])

        # ── Parent PO received item update ──
        if primary_po.source_po_id:
            parent_receive = PurchaseReceives.objects.filter(
                po_id=primary_po.source_po_id
            ).first()

            if parent_receive:
                parent_received_item = PurchaseReceivedItems.objects.filter(
                    po_receive_id=parent_receive.po_receive_id,
                    product_id=pid,
                ).first()

                if parent_received_item:
                    parent_received_item.received_qty = (
                        parent_received_item.received_qty or Decimal("0")
                    ) + rqty
                    parent_received_item.save(update_fields=["received_qty"])

    # -------------------------------------------------
    # STAGE 2 — Create Sub PO
    # -------------------------------------------------
    root_po        = PurchaseOrder.objects.filter(po_id=root_po_id).first()
    base_po_number = root_po.po_number
    child_count    = PurchaseOrder.objects.filter(parent_po_id=root_po_id).count()

    sub_po = PurchaseOrder.objects.create(
        po_number                  = f"{base_po_number}-{child_count + 1}",
        vendor_id                  = primary_po.vendor_id,
        vendor_code                = primary_po.vendor_code,
        vendor_name                = primary_po.vendor_name,
        currency_code              = primary_po.currency_code,
        warehouse_id               = primary_po.warehouse_id,
        order_date                 = primary_po.order_date,
        delivery_date              = primary_po.delivery_date,
        delivery_name              = primary_po.delivery_name,
        address_line1              = primary_po.address_line1,
        address_line2              = primary_po.address_line2,
        city                       = primary_po.city,
        state                      = primary_po.state,
        post_code                  = primary_po.post_code,
        country_id                 = primary_po.country_id,
        payment_term_id            = primary_po.payment_term_id,
        comments                   = primary_po.comments,
        global_tax_rate            = primary_po.global_tax_rate,
        global_discount_percentage = primary_po.global_discount_percentage,
        shipping_charge            = Decimal("0"),
        surcharge_total            = Decimal("0"),
        status_id                  = POStatus.PLACED,
        parent_po_id               = root_po_id,
        source_po_id               = source_po_id,
        created_by                 = request.user.id,
    )

    approve_and_create_receive_internal(sub_po.po_id, request.user.id)

    # ── Sub PO vendor details clone ──
    primary_vendor_details = PurchaseOrderVendorDetails.objects.filter(po_id=source_po_id)
    for vendor_detail in primary_vendor_details:
        PurchaseOrderVendorDetails.objects.create(
            po_id            = sub_po.po_id,
            is_primary       = vendor_detail.is_primary,
            vendor_po_number = vendor_detail.vendor_po_number,
            order_number     = vendor_detail.order_number,
            order_date       = vendor_detail.order_date,
            created_by       = request.user.id,
        )

    # -------------------------------------------------
    # STAGE 3 — Split Items from source_po_id
    # -------------------------------------------------
    all_po_items = list(PurchaseOrderItem.objects.filter(po_id=source_po_id))

    for po_item in all_po_items:
        pid          = int(po_item.product_id)
        item_data    = received_map.get(pid, {})
        ordered_qty  = Decimal(str(po_item.qty or 0))
        received_qty = item_data.get("received_qty", Decimal("0"))
        primary_qty  = received_qty
        sub_qty      = max(ordered_qty - received_qty, Decimal("0"))

        price                = po_item.price or Decimal("0")
        tax_pct              = po_item.tax_percentage or Decimal("0")
        discount_pct         = po_item.discount_percentage or Decimal("0")
        landed_cost_per_item = po_item.landed_cost or Decimal("0")

        # ── Source PO item update ──
        if primary_qty > 0:
            base          = primary_qty * price
            discount_amt  = (base * discount_pct) / Decimal("100")
            subtotal      = base - discount_amt
            tax_amount    = (subtotal * tax_pct) / Decimal("100")
            line_total    = subtotal + tax_amount
            landed_cost   = landed_cost_per_item * primary_qty
            cost_per_item = landed_cost / primary_qty

            primary_sub_total     += subtotal
            primary_tax_total     += tax_amount
            primary_summary_total += line_total

            PurchaseOrderItem.objects.filter(pk=po_item.pk).update(
                ordered_qty   = primary_qty,
                qty           = primary_qty,
                received_qty  = primary_qty,
                pending_qty   = 0,
                subtotal      = subtotal,
                tax_amount    = tax_amount,
                line_total    = line_total,
                discount_amt  = discount_amt,
                landed_cost   = landed_cost,
                cost_per_item = cost_per_item,
            )
        else:
            PurchaseOrderItem.objects.filter(pk=po_item.pk).delete()

        # ── Sub PO item ──
        if sub_qty > 0:
            base          = sub_qty * price
            discount_amt  = (base * discount_pct) / Decimal("100")
            subtotal      = base - discount_amt
            tax_amount    = (subtotal * tax_pct) / Decimal("100")
            line_total    = subtotal + tax_amount
            landed_cost   = landed_cost_per_item * sub_qty
            cost_per_item = landed_cost / sub_qty

            sub_sub_total     += subtotal
            sub_tax_total     += tax_amount
            sub_summary_total += line_total

            new_item = PurchaseOrderItem.objects.create(
                po_id               = sub_po.po_id,
                product_id          = po_item.product_id,
                qty                 = sub_qty,
                price               = price,
                tax_percentage      = tax_pct,
                discount_percentage = discount_pct,
                delivery_date       = po_item.delivery_date,
                comment             = po_item.comment,
                created_by          = request.user.id,
            )
            PurchaseOrderItem.objects.filter(pk=new_item.pk).update(
                ordered_qty   = sub_qty,
                pending_qty   = sub_qty,
                received_qty  = 0,
                subtotal      = subtotal,
                tax_amount    = tax_amount,
                line_total    = line_total,
                discount_amt  = discount_amt,
                landed_cost   = landed_cost,
                cost_per_item = cost_per_item,
            )

    # ── Sub PO totals ──
    PurchaseOrder.objects.filter(po_id=sub_po.po_id).update(
        sub_total     = sub_sub_total,
        tax_total     = sub_tax_total,
        summary_total = sub_summary_total,
    )

    # ── Source PO totals + status ──
    PurchaseOrder.objects.filter(po_id=source_po_id).update(
        sub_total     = primary_sub_total,
        tax_total     = primary_tax_total,
        summary_total = primary_summary_total,
        status_id     = POStatus.COMPLETED if is_complete else POStatus.RECEIPTED,
    )

    # ── PO Receive status ──
    total_ordered  = sum(Decimal(str(i.qty or 0)) for i in all_po_items)
    total_received = sum(v["received_qty"] for v in received_map.values())

    receive_status = (
        POReceiveStatus.COMPLETED
        if total_received >= total_ordered
        else POReceiveStatus.PARTIALLY_RECEIVED
    )

    PurchaseReceives.objects.filter(po_receive_id=po_receive_id).update(
        internal_ref_notes = comments,
        status_id          = receive_status,
    )

    # ── Source PO Receipt + Receipt Items ──
    if po_invoice_id:
        po_invoice = PurchaseOrderInvoiceDetails.objects.filter(
            po_invoice_id=po_invoice_id
        ).first()

        if po_invoice:
            receipt = PurchaseReceipt.objects.create(
                po_id         = source_po_id,
                po_receive_id = po_receive_id,
                comments      = comments,
                status_id     = 1,
                po_invoice_id = po_invoice_id,
                receipt_total = Decimal(po_invoice.invoice_total),
                created_by    = request.user.id,
            )

            receipt_items = []
            for pid, item_data in received_map.items():
                rqty = item_data.get("received_qty", Decimal("0"))
                if rqty > 0:
                    receipt_items.append(PurchaseReceiptItem(
                        po_receipt_id = receipt.po_receipt_id,
                        product_id    = pid,
                        po_invoice_id = item_data.get("po_invoice_id"),
                        received_date = item_data.get("received_date", None),
                        received_qty  = rqty,
                    ))

            PurchaseReceiptItem.objects.bulk_create(receipt_items)

            # ── Parent PO Receipt Item update ──
            if primary_po.source_po_id:
                parent_receipt = PurchaseReceipt.objects.filter(
                    po_id=primary_po.source_po_id
                ).order_by("-created_at").first()

                if parent_receipt:
                    for pid, item_data in received_map.items():
                        rqty = item_data.get("received_qty", Decimal("0"))
                        if rqty > 0:
                            parent_receipt_item = PurchaseReceiptItem.objects.filter(
                                po_receipt_id = parent_receipt.po_receipt_id,
                                product_id    = pid,
                            ).first()

                            if parent_receipt_item:
                                parent_receipt_item.received_qty = (
                                    parent_receipt_item.received_qty or Decimal("0")
                                ) + rqty
                                parent_receipt_item.save(update_fields=["received_qty"])
                            else:
                                PurchaseReceiptItem.objects.create(
                                    po_receipt_id = parent_receipt.po_receipt_id,
                                    product_id    = pid,
                                    po_invoice_id = item_data.get("po_invoice_id"),
                                    received_date = item_data.get("received_date", None),
                                    received_qty  = rqty,
                                )

    # ── Sub PO fresh receive record ──
    sub_receive = PurchaseReceives.objects.create(
        po_id             = sub_po.po_id,
        vendor_id         = primary_po.vendor_id,
        po_number         = sub_po.po_number,
        po_receive_number = f"REC-{sub_po.po_number}",
        status_id         = POReceiveStatus.PENDING,
        created_by        = request.user.id,
    )

    for sub_item in PurchaseOrderItem.objects.filter(po_id=sub_po.po_id):
        PurchaseReceivedItems.objects.create(
            po_receive_id = sub_receive.po_receive_id,
            product_id    = sub_item.product_id,
            item_id       = sub_item.item_id,
            received_qty  = 0,
            created_by    = request.user.id,
        )

    return JsonResponse({
        "status"           : True,
        "message"          : "Split Receive processed successfully",
        "new_po_number"    : sub_po.po_number,
        "new_po_id"        : sub_po.po_id,
        "new_po_receive_id": sub_receive.po_receive_id,
    })