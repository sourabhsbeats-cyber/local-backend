from sys import get_int_max_str_digits
from xmlrpc.client import Boolean
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
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.address_model import Addresses
from django.db import transaction
from django.db.models import Value as V
from django.db.models.functions import Concat
from django.urls import reverse
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

from store_admin.models.po_models.po_models import PurchaseOrder, POStatus, PurchaseOrderItem
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


def validate_purchase_order_model(po, line_items):
    rules = [
        ("vendor_id",       "Vendor is required"),
        ("vendor_name",     "Vendor Name is required"),
        ("currency_code",   "Currency Code is required"),
        ("vendor_reference","Vendor Reference is required"),
        ("invoice_date",    "Invoice Date is required"),
        ("warehouse_id",    "Warehouse is required"),
        ("order_date",      "Order Date is required"),
        ("delivery_date",   "Delivery Date is required"),
        ("payment_term_id", "Payment Term is required"),
        ("delivery_name",   "Delivery Name is required"),
        ("address_line1",   "Address Line 1 is required"),
        ("address_line2",   "Address Line 2 is required"),
        ("suburb",          "Suburb is required"),
        ("state",           "State is required"),
        ("post_code",       "Postcode is required"),
        ("country_id",      "Country is required"),
        ("tax_percentage",  "Tax Percentage is required"),
    ]

    # Loop the model fields
    for field, msg in rules:
        value = getattr(po, field, None)
        if value is None or str(value).strip() == "":
            return False

    # Line items check
    if not line_items or len(line_items) == 0:
        return False, "Please add at least one product line item"

    return True


#Product Add New Form - Only GET
@login_required
def create_order(request, po_id=None):
    if po_id is None:
        po = PurchaseOrder.objects.create(
            vendor_code="",
            vendor_name="",
            created_by = request.user.id,
            status_id= POStatus.CREATED   # Created / Draft
        )
        po_number = f"PO{po.po_id:04d}"

        #  Update the record with PO number
        po.po_number = po_number
        po.save()
        # redirect to the same page WITH PO ID in URL
        return redirect('create_order', po_id=po.po_id)

    po = PurchaseOrder.objects.filter(po_id=po_id).first()
    if not po:
        return HttpResponse("Invalid PO", status=404)

    #category = Category.objects.filter(status=1).all()
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
        po_images = ProductImages.objects.filter(product_id=po_order_item.product_id).order_by("product_image_id").first()

        line_items.append({
            "row_item": {
                "id": po_product.product_id,
                "title": po_product.title,
                "image": po_images.cdn_url if po_images else NO_IMAGE,
                "stock_qty": 0,  # if you have stock, replace 0
                "sku": po_product.sku,
                "price": float(po_order_item.price),  # send as number for JS
            },
            "qty": int(po_order_item.qty),
            "price": float(po_order_item.price),
            "discount": float(po_order_item.discount_percentage),
            "tax": float(po_order_item.tax_percentage),
            "tax_amount": float(po_order_item.tax_amount),
            "sub_total": float(po_order_item.subtotal),
            "line_total": float(po_order_item.line_total),
        })

    can_pdf_generate = validate_purchase_order_model(po, line_items)
    payment_terms = PaymentTerm.objects.all()
    context = {
        'po_id': po_id,
        'po': po,
        'can_pdf_generate':can_pdf_generate,
        'po_order_items':po_order_items,
        'user': request.user.id,
        'payment_terms': payment_terms,
        'unit_of_measures': unit_of_measures,
        'line_items':line_items,
        'warehouses': warehouses,
        'country_list': countries_list,
        'currency_list': currency_list,
        'vendors':vendors
    }

    return render(request, 'sbadmin/pages/purchase_order/add/addnew_form.html', context)



class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImages
        fields = ["product_image_id", "product_id", "image_path", "cdn_url", "uploaded_at"]

@api_view(["GET"])
def list_product_images(request, product_id):
    q = ProductImages.objects.filter(product_id=request.GET.get("product_id")) if request.GET.get("product_id") else ProductImages.objects.all()
    return JsonResponse(ProductImageSerializer(q, many=True).data)

from django.template.loader import render_to_string
from django.http import HttpResponse
from rest_framework.views import APIView
from weasyprint import HTML
import datetime
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

        po_items.append({"name": line_product.title,
                         "qty": line_item.qty,
                         "rate": line_item.price,
                         "amount":line_item.line_total})

    po = {
        "number": po_details.po_number,
        "date": po_details.order_date.strftime("%d/%m/%Y"),
        "ref": po_details.vendor_reference,
        "vendor": {
            "name": po_details.vendor_name,
            "address": f"{vendor_billing_address.street1}\n{vendor_billing_address.street2}\n{vendor_billing_address.city}, \n{vendor_billing_address.state}, \n{vendor_billing_address.zip}, \n{vendor_billing_address.country.name}"
            if vendor_billing_address else "Vendor Address"
        },
        "deliver_to": {
            "name": po_details.delivery_name,
            "address": f"{po_details.address_line1}\n{po_details.address_line2}\n{po_details.suburb}\n{po_details.city}\n{po_details.state}\n{delivery_country}-{po_details.post_code}"
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
    total = (po_details.summary_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # ---------- CONTEXT ----------
    context = {
        "po": po,
        "company_name": "SHOPPERBEATS TECHNOLOGIES PTY LTD",
        "company_tagline": "Company ID · ABN - 32637549770",
        "company_address": {
            "line1": "2/31 Amherst Dr",
            "line2": "Truganina Victoria 3029",
            "city": "Truganina",
            "postcode": "3029",
            "country": "Australia"
        },
        "company_phone": "0406958192",
        "company_email": "shopperdoornz@gmail.com",
        "company_website": "https://www.shopperbeats.com.au",
        "logo_url": "https://www.shopperbeats.com/cdn/shop/files/logo_260x_2x_600c8b6c-c0e8-4f59-82df-6a2d9bed69da_260x@2x.jpg",  # swap with your logo
        "subtotal": subtotal,
        "gst_percent": gst_percent,
        "gst_amount": gst_amount,
        "total": total,
    }

    # Render html
    html_string = render_to_string("po_pdftemplates/purchase_order.html", context)

    # Generate PDF
    html = HTML(string=html_string)
    pdf = html.write_pdf()

    # Return response
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = "inline; filename=purchase_order.pdf" #attachment
    return response


def clean_percent(value):
    if value in (None, "", " ", "null"):
        return 0
    try:
        val = float(value)
    except:
        return 0
    if val.is_integer():
        return int(val)
    return val

@api_view(["POST"])
#@authentication_classes([])     # allow Postman
#@permission_classes([])         # allow Postman
#@csrf_exempt
def save_po(request):
    data = request.data  #  RAW JSON is captured here

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
    country = data.get("country")
    tax_percentage = data.get("tax_percentage")
    line_items = data.get("lineItems", [])

    # Simple validation
    if not vendor_id or not po_id:
        return Response({"error": "Invalid Operation"}, status=400)

    try:
        po = PurchaseOrder.objects.get(po_id=po_id)
    except PurchaseOrder.DoesNotExist:
        return Response({"error": "Invalid Operation"}, status=400)

    if len(line_items) == 0:
        return Response({"error": "At least one line item required"}, status=400)

    po_vendor = Vendor.objects.get(id=vendor_id)

    with transaction.atomic():
        po.vendor_id = po_vendor.id
        po.vendor_code = po_vendor.vendor_code
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
        po.comments = comments
        po.created_by = request.user.id
        po.status_id = POStatus.CREATED

        '''sub_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # qty*price
        tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # subtital 's tax amount
        summary_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # subtotal + taxamount
        '''


        PurchaseOrderItem.objects.filter(po_id=po.po_id).delete()

        for item in line_items:
            PurchaseOrderItem.objects.create(
                po_id=po.po_id,
                product_id=item["row_item"]["id"],  # correct mapping
                qty=item["qty"],
                price=item["price"],
                tax_percentage=item["tax"],  # percentage tax
                discount_percentage=item["discount"],
                created_by = request.user.id,
            )
            '''
               subtotal, tax_amount, actual_total, discount_amt,
            '''
        items = PurchaseOrderItem.objects.filter(po_id=po.po_id)

        subtotal_total = sum(i.subtotal for i in items)
        discount_total = sum(i.discount_amt for i in items)
        tax_total = sum(i.tax_amount for i in items)
        line_total_total = sum(i.line_total for i in items)

        po.sub_total = subtotal_total
        po.discount_total = discount_total
        po.tax_total = tax_total
        po.summary_total = line_total_total

        po.save()

    return Response({"status": True, "message": "PO updated successfully"})

#PO Listing
@login_required
def listing(request):
    # ---- Context ----
    context = {
        "user": request.user.id,
    }
    return render(request, 'sbadmin/pages/purchase_order/all_listing.html', context)



class TabulatorPagination(PageNumberPagination):
    page_size = 20
    page_query_param = "page"
    page_size_query_param = "size"
    max_page_size = 50  # ✅ cap at 50


from django.db.models import OuterRef, Subquery, Value, TextField, DecimalField
from django.db.models.functions import Coalesce
from django.db.models.functions import Right, Concat
from django.db.models import F

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
