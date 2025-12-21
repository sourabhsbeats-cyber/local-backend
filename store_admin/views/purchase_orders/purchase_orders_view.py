from django.core.exceptions import ValidationError
from store_admin.helpers import name_validator_none, reference_validator, zip_validator, \
    get_prep_label, format_tax_percentage, validate_purchase_order_model
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.address_model import Addresses
from django.db import transaction
from django.shortcuts import render, redirect
from store_admin.models.po_models.po_models import (PurchaseOrder, POApprovalStatus, PurchaseOrderItem,
                                                    PurchaseOrderShipping, \
                                                    PurchaseOrderVendor, PurchaseReceives, PurchaseReceivedItems)
from store_admin.models.product_model import Product, ProductImages
from store_admin.models.setting_model import UnitOfMeasurements, ShippingProviders
from store_admin.models.vendor_models import Vendor, VendorAddress
from django.db.models import Min, Sum
from store_admin.models import Country
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
            delivery_name="Head Office",
            address_line1="2/31 Amherst Dr",
            state="Victoria",
            city="Truganina",
            post_code=3029,
            country_id=14,
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
    context = {
        'po_id': po_id,
        'po': po,
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

#UPDATE SAVE PO
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
    po_status = data.get("po_status")

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
        po.status_id = int(po_status)  # POStatus.CREATED

        '''sub_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # qty*price
        tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # subtital 's tax amount
        summary_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # subtotal + taxamount
        '''

        can_pdf_generate, err_msg = validate_purchase_order_model(po, line_items)
        if not can_pdf_generate:
            return JsonResponse({"status": False, "message": err_msg})

        PurchaseOrderItem.objects.filter(po_id=po.po_id).delete()

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
    tot_qty = 0
    for po_order_item in po_order_items:
        tot_qty += int(po_order_item.qty)
    
    addntl_totl = float(po.shipping_charge+po.surcharge_total)
    addntl_per_totl = float(addntl_totl/tot_qty)

    for po_order_item in po_order_items:
        po_product = Product.objects.filter(product_id=po_order_item.product_id).first()
        po_images = ProductImages.objects.filter(product_id=po_order_item.product_id).order_by("product_image_id").first()
        
        unit_total = addntl_per_totl*int(po_order_item.qty)
        rate_totl = (float(po_order_item.price)*int(po_order_item.qty))+unit_total
        rate_totl = rate_totl/int(po_order_item.qty)
        #cost_per_item = cost_per_item+float(float(po_order_item.price)*int(po_order_item.qty))
        
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
    context = {
        'po_id': po_id,
        'po': po,
        "shipping_providers": shipping_providers,
        'shipping':shipping_details,
        'can_pdf_generate':can_pdf_generate,
        'po_order_items':po_order_items,
        'user': request.user.id,
        'payment_terms': payment_terms,
        'unit_of_measures': unit_of_measures,
        'line_items':line_items,
        'warehouses': warehouses,
        'country_list': countries_list,
        'currency_list': currency_list,
        'vendor':vendor_detail
    }
    return render(request, 'sbadmin/pages/purchase_order/view/view_po.html', context)

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

    vendors_po = PurchaseOrder.objects.filter(vendor_id=vendor_id).all()
    data = []
    for vendor_po in vendors_po:
        data.append({
            "po_number":vendor_po.po_number,
            "order_date":vendor_po.order_date,
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
    context = {
        "user": request.user.id,
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
    ).all()



    q = request.GET.get("q", "").strip()
    #if q:
     #   qs = qs.filter(Q(title__icontains=q) | Q(sku__icontains=q) | Q(brand_name_val__icontains=q))

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

    data = list(qs.order_by("po_receive_id")[start:end].values(
        "po_receive_id","po_id",  "total_received_qty", "company_name", "vendor_name", "vendor_id", "po_number", "po_receive_number", "received_date",
        "status_id"
    ))
    for row in data:
        row["is_billed"] = False

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

''' TABLES LISTING TABLE '''
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def all_purchases(request):
    warehouse_sub = Warehouse.objects.filter(
        warehouse_id=OuterRef("warehouse_id")
    ).values("warehouse_name")[:1]

    vendor_sub = Vendor.objects.filter(
        id=OuterRef("vendor_id")
    ).values("display_name")[:1]

    qs = PurchaseOrder.objects.filter(
            is_archived=0,          #
            vendor_id__isnull=False,
            vendor_code__isnull=False
        ).annotate(
            warehouse_name=Coalesce(
                Subquery(warehouse_sub),
                Value(""),
                output_field=TextField()
            ),
            vendor_name_val=Coalesce(
                Subquery(vendor_sub),
                Value(""),
                output_field=TextField()
            ),
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


@api_view(["GET"])
def list_product_images(request, product_id):
    q = ProductImages.objects.filter(product_id=request.GET.get("product_id")) if request.GET.get("product_id") else ProductImages.objects.all()
    return JsonResponse(ProductImageSerializer(q, many=True).data)


