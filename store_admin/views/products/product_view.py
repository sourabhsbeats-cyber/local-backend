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

from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from store_admin.models.product_model import Product, ProductShippingDetails, ProductPriceDetails
from store_admin.models.setting_model import Category, Brand, Manufacturer
from store_admin.models.vendor_models import Vendor, VendorBank, VendorContact, VendorAddress
from django.db.models import Min
from django.db import IntegrityError
from django.db.models import Subquery, OuterRef, Value, CharField, When, Case
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from store_admin.models import Country, State

#Product Add New Form - Only GET
@login_required
def add_new(request):
    category = Category.objects.filter(status=1).all()
    brand = Brand.objects.filter(status=1).all()
    manufacturers = Manufacturer.objects.filter(status=1).all()
    vendors = Vendor.objects.filter(status=1).all()

    countries_list = Country.objects.values('name', 'id')
    context = {
        'user': request.user.id,
        'brands': brand,
        'manufacturers': manufacturers,
        'countries_list': countries_list,
        'vendors':vendors
    }
    return render(request, 'sbadmin/pages/product/add/addnew_form.html', context)

#edit form
@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    category = Category.objects.filter(status=1).all()
    brand = Brand.objects.filter(status=1).all()
    manufacturers = Manufacturer.objects.filter(status=1).all()
    vendors = Vendor.objects.filter(status=1).all()
    shipping_info =  ProductShippingDetails.objects.filter(product_id=product_id).first()
    price_info = ProductPriceDetails.objects.filter(product_id=product_id).first()

    countries_list = Country.objects.values('name', 'id')
    context = {
        'user': request.user.id,
        'brands': brand,
        'manufacturers': manufacturers,
        'countries_list': countries_list,
        'vendors': vendors,
        'product':product, 'shipping_info':shipping_info, 'price_info':price_info
    }

    return render(request, 'sbadmin/pages/product/edit/edit_form.html', context)

@login_required
def delete(request, contact_id):
    try:
        obj = VendorContact.objects.filter(id=contact_id).first()
        if not obj:
            return JsonResponse({"status": False, "message": "Contact not found"})

        obj.delete()
        return JsonResponse({"status": True, "message": "Contact deleted"})
    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)})

@login_required
def listing(request):
    products = Product.objects.annotate(
        brand_name=Coalesce(
            Subquery(
                Brand.objects.filter(brand_id=OuterRef('brand_id'))
                .values('name')[:1]
            ),
            Value("", output_field=CharField())
        ),
        manufacturer_name=Coalesce(
            Subquery(
                Manufacturer.objects.filter(manufacturer_id=OuterRef('manufacturer_id'))
                .values('name')[:1]
            ),
            Value("", output_field=CharField())
        ),
        product_type_name=Case(
            When(product_type=1, then=Value("Standard")),
            When(product_type=2, then=Value("Parent")),
            When(product_type=3, then=Value("Child")),
            When(product_type=4, then=Value("Bundle")),
            default=Value("Unknown"),
            output_field=CharField()
        )
    ).values(
        'product_id',
        'title',
        'sku',
        'product_type',
        'product_type_name',
        'brand_id',
        'brand_name',
        'manufacturer_id',
        'manufacturer_name',
        'stock_status',
        'publish_status',
        'status',
        'created_at'
    )

    # ---- Search ----
    search_query = request.GET.get("q", "").strip()

    if search_query:
        products = products.filter(
            Q(title__icontains=search_query) |
            Q(sku__icontains=search_query) |
            Q(brand_name__icontains=search_query) |
            Q(manufacturer_name__icontains=search_query)
        )

    # ---- Pagination ----
    paginator = Paginator(products, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # ---- Context ----
    context = {
        "user": request.user.id,
        "allproducts": page_obj,  # for listing loop
        "page_obj": page_obj,  # for pagination UI
        "search_query": search_query,
    }
    return render(request, 'sbadmin/pages/product/all_listing.html', context)

@login_required
def save(request):
    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid request"}, status=400)

    data = request.POST  # request.POST is a QueryDict
    product_id = data.get("product_id")
    try:
        brand_id = int(data.get('brand_id')) if data.get('brand_id') else None
    except ValueError:
        brand_id = None  # Handle non-integer input gracefully

    try:
        manufacturer_id = int(data.get('manufacturer_id')) if data.get('manufacturer_id') else None
        country_origin_id = int(data.get('country_origin_id')) if data.get('country_origin_id') else 0
        warranty = int(data.get('warranty')) if data.get('warranty') else None
        stock_status = get_int(data, 'stock_status')
        status = get_int(data,'status')
        publish_status = get_int(data,'publish_status')
        is_alias_checked = True if data.get('is_alias') else False
    except ValueError: #stock_status, Status, Publish
        return JsonResponse({"status": True, "message": "Invalid number input.", 'error': 'Invalid number input.'})

    try:
        product_details = Product.objects.get(product_id=product_id)
        if not product_details:
             return JsonResponse({"status": False, "message": "Invalid product details"})
        with transaction.atomic():

            #product_details.product_type = data.get('product_type', '')
            product_details.is_alias = is_alias_checked
            product_details.sku = data.get('sku')
            product_details.title = data.get('title')
            product_details.subtitle = data.get('subtitle')
            product_details.description = data.get('description')
            product_details.short_description = data.get('short_description')
            product_details.brand_id = brand_id
            product_details.manufacturer_id = manufacturer_id
            product_details.ean = data.get('ean')
            product_details.upc = data.get('upc')
            product_details.isbn = data.get('isbn')
            product_details.mpn = data.get('mpn')
            product_details.country_origin_id = country_origin_id
            product_details.status_condition = data.get('status_condition', 'new')
            product_details.asin = data.get('asin')
            product_details.fnsku = data.get('fnsku')
            product_details.fba_sku = data.get('fba_sku')
            product_details.is_fba = True if data.get('is_fba') else False
            product_details.isbn_type = data.get('isbn_type')
            product_details.barcode_label_type = data.get('barcode_label_type')
            product_details.prep_type = data.get('prep_type', 'no_prep_needed')
            product_details.stock_status = stock_status
            product_details.status = status
            product_details.publish_status = publish_status
            product_details.warranty = warranty
            product_details.product_tags = data.get('product_tags')
            product_details.updated_by = request.user.id
            product_details.preferred_vendor = get_int(data, "preferred_vendor") #preferred_vendor id
            product_details.amazon_size = data.get('amazon_size')
            product_details.vendor_sku = data.get('vendor_sku')
            product_details.sbau = data.get('sbau')
            product_details.created_by = request.user.id
            product_details.save()
            # --- 2. Update Shipping Details ---

            try:
                product_shipping_details = ProductShippingDetails.objects.filter(product_id=product_id).first()
                if product_shipping_details:
                    product_shipping_details.fast_dispatch = get_bool_int(data, 'fast_dispatch')
                    product_shipping_details.free_shipping = get_bool_int(data, 'free_shipping')
                    product_shipping_details.handling_time_days = get_int(data, 'handling_time_days')
                    product_shipping_details.bulky_product = get_bool_int(data, 'bulky_product')
                    product_shipping_details.international_note = data.get('international_note')
                    product_shipping_details.example_reference = data.get('example_reference')
                    product_shipping_details.ships_from = data.get('ships_from')
                    product_shipping_details.save()
                else:
                    ProductShippingDetails.objects.create(
                        product_id=product_details.product_id,
                        fast_dispatch=get_bool_int(data, 'fast_dispatch'),
                        free_shipping= get_bool_int(data, 'free_shipping'),
                        handling_time_days=get_bool_int(data, 'handling_time_days'),
                        bulky_product= get_bool_int(data, 'bulky_product'),
                        international_note=data.get('international_note'),
                        example_reference=data.get('example_reference'),
                        ships_from=data.get('ships_from'),
                        created_by=request.user.id
                    )
            except (ValueError, TypeError) as e:
                # Handle conversion errors if non-numeric data is passed to int()
                print(f"Error creating shipping details: {e}")
                # You should raise an appropriate error or return a response here
                raise

            # --- 3. Update Price Details ---
            product_price_details = ProductPriceDetails.objects.filter(product_id=product_id).first()
            try:
                if product_price_details:
                    product_price_details.sale_price = get_decimal(data, 'sale_price')
                    product_price_details.retail_price = get_decimal(data, 'retail_price')
                    product_price_details.cost_per_item = get_decimal(data, 'cost_per_item')
                    product_price_details.margin_percent = get_decimal(data, 'margin_percent')
                    product_price_details.profit = get_decimal(data, 'profit')
                    product_price_details.min_price = get_decimal(data, 'min_price')
                    product_price_details.max_price = get_decimal(data, 'max_price')
                    product_price_details.estimated_shipping_cost = get_decimal(data, 'estimated_shipping_cost')
                    product_price_details.save()
                else:
                    ProductPriceDetails.objects.create(
                        product_id=product_details.product_id,
                        sale_price=get_decimal(data,'sale_price') ,
                        retail_price=get_decimal(data,'retail_price'),
                        cost_per_item=get_decimal(data,'cost_per_item'),
                        margin_percent=get_decimal(data,'margin_percent'),
                        profit=get_decimal(data,'profit'),
                        min_price=get_decimal(data,'min_price'),
                        max_price=get_decimal(data,'max_price'),
                        estimated_shipping_cost=get_decimal(data,'estimated_shipping_cost'),
                        created_by=request.user.id
                    )
            except Exception as e:
                print(f"Error creating price details: {e}")
                # Handle the error appropriately (e.g., log it, return an error response)
                raise

            return JsonResponse({
                "status": True,
                "message": "Product updated successfully",
                "product_id": product_details.pk
            })

    except IntegrityError:
        error_message = f"Product updated failed. The SKU '{data.get('sku')}' may already exist."
        return JsonResponse({"status": False, "message": error_message })

    except Exception as e:
        print(str(e))
        error_message = f"An unexpected error occurred: {e}"
        return JsonResponse({"status": False, "message": error_message})



@login_required
def delete_product(request, product_id):
    if request.method != "DELETE":
        return JsonResponse({"status": False, "message": "Invalid request method"}, status=400)
    product = Product.objects.filter(product_id=product_id).first()

    if not product:
        return JsonResponse({"status": False, "message": "Product not found"}, status=404)

    try:
        product.delete()
        price = ProductPriceDetails.objects.filter(product_id=product_id).first()
        if price:
            price.delete()
        ship = ProductShippingDetails.objects.filter(product_id=product_id).first()
        if ship:
            ship.delete()
        return JsonResponse({"status": True, "message": "Product deleted successfully"})
    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)}, status=500)

from django.http import JsonResponse
import json
@login_required
def delete_product_bulk(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"})

    data = json.loads(request.body)
    ids = data.get("ids", [])

    if not ids:
        return JsonResponse({"status": "error", "message": "No products selected"})

    Product.objects.filter(product_id__in=ids).delete()

    price = ProductPriceDetails.objects.filter(product_id=ids).first()
    if price:
        price.delete()
    ship = ProductShippingDetails.objects.filter(product_id=ids).first()
    if ship:
        ship.delete()

    return JsonResponse({"status": "success", "deleted": len(ids)})


def to_boolean_int(value_list):
    if not value_list or not value_list[0]:
        return None  # Or 0, depending on your default logic for an unchecked box

    return 1 if str(value_list[0]).lower() in ['true', '1', 'on'] else 0

def to_int_bool(value_list):
    value = value_list[0] if isinstance(value_list, list) and value_list else None
    if value is None:
        return None
    value_lower = str(value).lower()
    if value_lower in ('true', '1', 'on'):
        return 1
    if value_lower in ('false', '0', 'off'):
        return 0
    return None

from decimal import Decimal, InvalidOperation

def get_decimal(data, key):
    raw = data.get(key)
    if raw is None:
        return None
    try:
        value = raw.strip()
        return Decimal(value) if value else None
    except (InvalidOperation, AttributeError):
        return None


from typing import Optional, List, Union


def get_int(data, key):
    try:
        raw = data.get(key)
        return int(raw.strip()) if raw and raw.strip().lstrip("-").isdigit() else None
    except Exception as e:
        print(e)
        return None

def get_bool_int(data, key):
    raw = data.get(key) if hasattr(data, "get") else data[key] if key in data else None
    if raw is None:
        return None

    raw = str(raw).strip().lower()
    if raw in ("true", "1", "yes", "y"):
        return 1
    if raw in ("false", "0", "no", "n"):
        return 0
    return None


@login_required
def create_product(request):

    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid request"}, status=400)

    data = request.POST  # request.POST is a QueryDict

    if Product.objects.filter(sku=data.get('sku')).exists():
        return JsonResponse({"status": False, "message": "Product SKU already exists"}, status=400)

    try:
        brand_id = int(data.get('brand_id')) if data.get('brand_id') else None
    except ValueError:
        brand_id = None  # Handle non-integer input gracefully

    try:
        manufacturer_id = int(data.get('manufacturer_id')) if data.get('manufacturer_id') else None
        country_origin_id = int(data.get('country_origin_id')) if data.get('country_origin_id') else 0
        warranty = int(data.get('warranty')) if data.get('warranty') else None
        stock_status = get_int(data, 'stock_status')
        status = get_int(data,'status')
        publish_status = get_int(data,'publish_status')
        is_alias_checked = True if data.get('is_alias') else False
    except ValueError:
        return JsonResponse({"status": True, "message": "Invalid number input.", 'error': 'Invalid number input.'})
    try:

        #product_details = Product.objects.get(product_id=product_id)
        #if not product_details:
        #     return JsonResponse({"status": False, "message": "Invalid product details"})
        with transaction.atomic():
            product_details = Product()
            product_details.product_type = data.get('product_type', '')

            product_details.is_alias = is_alias_checked

            product_details.sku = data.get('sku')
            product_details.title = data.get('title')
            product_details.subtitle = data.get('subtitle')
            product_details.description = data.get('description')
            product_details.short_description = data.get('short_description')

            product_details.brand_id = brand_id
            product_details.manufacturer_id = manufacturer_id

            product_details.ean = data.get('ean')
            product_details.upc = data.get('upc')
            product_details.isbn = data.get('isbn')
            product_details.mpn = data.get('mpn')

            product_details.country_origin_id = country_origin_id
            product_details.status_condition = data.get('status_condition', 'new')

            product_details.asin = data.get('asin')
            product_details.fnsku = data.get('fnsku')
            product_details.fba_sku = data.get('fba_sku')

            product_details.is_fba = True if data.get('is_fba') else False

            product_details.isbn_type = data.get('isbn_type')
            product_details.barcode_label_type = data.get('barcode_label_type')
            product_details.prep_type = data.get('prep_type', 'no_prep_needed')

            product_details.stock_status = stock_status
            product_details.status = status
            product_details.publish_status = publish_status

            product_details.warranty = warranty
            product_details.product_tags = data.get('product_tags')

            product_details.updated_by = request.user.id
            #new fields
            product_details.preferred_vendor = get_int(data, "preferred_vendor") #preferred_vendor id
            product_details.amazon_size = data.get('amazon_size')
            product_details.vendor_sku = data.get('vendor_sku')
            product_details.sbau = data.get('sbau')
            product_details.created_by = request.user.id

            #shipping info
            product_details.save()

            # --- 2. Create Shipping Details ---

            try:
                ProductShippingDetails.objects.create(
                    product_id=product_details.product_id,
                    fast_dispatch=get_bool_int(data, 'fast_dispatch'),
                    free_shipping= get_bool_int(data, 'free_shipping'),
                    handling_time_days=get_int(data, 'handling_time_days'),
                    bulky_product= get_bool_int(data, 'bulky_product'),
                    international_note=data.get('international_note'),
                    example_reference=data.get('example_reference'),
                    ships_from=data.get('ships_from'),
                    created_by=request.user.id
                )
            except (ValueError, TypeError) as e:
                # Handle conversion errors if non-numeric data is passed to int()
                print(f"Error creating shipping details: {e}")
                # You should raise an appropriate error or return a response here
                raise

            # --- 3. Create Price Details ---

            try:
                ProductPriceDetails.objects.create(
                    product_id=product_details.product_id,
                    sale_price=get_decimal(data,'sale_price') ,
                    retail_price=get_decimal(data,'retail_price'),
                    cost_per_item=get_decimal(data,'cost_per_item'),
                    margin_percent=get_decimal(data,'margin_percent'),
                    profit=get_decimal(data,'profit'),
                    min_price=get_decimal(data,'min_price'),
                    max_price=get_decimal(data,'max_price'),
                    estimated_shipping_cost=get_decimal(data,'estimated_shipping_cost'),
                    created_by=request.user.id
                )
            except Exception as e:
                print(f"Error creating price details: {e}")
                # Handle the error appropriately (e.g., log it, return an error response)
                raise

            return JsonResponse({
                "status": True,
                "message": "Product created successfully",
                "product_id": product_details.pk
            })

    except IntegrityError:
        error_message = f"Product creation failed. The SKU '{data.get('sku')}' may already exist."
        return JsonResponse({"status": False, "message": error_message })

    except Exception as e:
        print(str(e))
        error_message = f"An unexpected error occurred: {e}"
        return JsonResponse({"status": False, "message": error_message})

