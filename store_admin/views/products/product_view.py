from xmlrpc.client import Boolean

from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseBadRequest

from store_admin.models import Country, State
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.product_model import Product
from store_admin.models.setting_model import Category, Brand, Manufacturer
from store_admin.models.vendor_models import Vendor, VendorBank, VendorContact, VendorAddress
from store_admin.models.address_model import Addresses
from django.db import transaction
from django.db.models import Min
from django.db.models import Value as V
from django.db.models.functions import Concat
from django.db import IntegrityError
from django.db.models import Subquery, OuterRef, Value, CharField, When, Case
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator

'''
Product Type	Product Type	Dropdown	Parent, Child, Standard, Bundle	Default = Standard; determines product hierarchy.
	Parent SKU	Text Field	—	Required if Product Type = Child.
	Bundle SKU	Text Field		Required; select which SKUs form this bundle.
	Alias Product	Checkbox	TRUE / FALSE	If checked, product is treated as alias (duplicate listing).
				
Basic Info	SKU	Text Field	—	Unique ID, required.
	Title	Text Field	—	Required; product name.
	Subtitle	Text Field	—	Optional.
	Description	Text Area	—	Full description with formatting allowed 
	Short Description	Text Area	—	Specially for trade me  which don't allow bigger description
				
Identifiers	Brand	Dropdown	From Brand Master	Required; populates from Brand Master sheet.
	Manufacturer	Text Field	—	Optional; can be same as Brand.
	EAN	Text Field	—	Numeric only (13 digits).
	UPC	Text Field	—	Numeric only (12 digits).
	ISBN	Text Field	—	Required for books only.
	Country of Origin	Dropdown	From country of orgin Master	Must be selected.
				
Amazon Identifiers	ASIN	Text Field	—	Amazon-linked items.
	FNSKU	Text Field	—	Auto-filled if FBA = Yes.
	FBA SKU	Text Field	—	Optional.
	FBA	Checkbox	TRUE / FALSE	If TRUE, FBA fields enabled.
	Amazon Size	Dropdown	Standard, Oversize	Default = Standard.
	Barcode Label Type	Dropdown	Manufacturer, Amazon Barcode	Required if FBA = TRUE.
	Prep Type	Dropdown	No Prep Needed, Polybagging, Bubble Wrap, Labeling	Only visible if FBA = TRUE.
				
Stock & Status	Stock Status	Dropdown	In Stock, Out of Stock, Preorder, Discontinued	Required.
	Publish	Dropdown	Yes, No	Determines if product syncs to store.
	'''
@login_required
def add_new(request):
    category = Category.objects.filter(status=1).all()
    brand = Brand.objects.filter(status=1).all()
    manufacturers = Manufacturer.objects.filter(status=1).all()

    currency_list = Country.objects.values('currency').annotate(
        id=Min('id'),  # pick country with smallest ID per currency
        currency_name=Min('currency_name')
    )
    countries_list = Country.objects.values('name', 'id')

    if request.method == 'POST':
        data = request.POST  # request.POST is a QueryDict
        is_alias_value = 'on' in data.getlist('is_alias', []) or False
        is_alias_checked = 'is_alias' in data
        try:
            brand_id = int(data.get('brand_id')) if data.get('brand_id') else 0
        except ValueError:
            brand_id = 0  # Handle non-integer input gracefully

        try:
            manufacturer_id = int(data.get('manufacturer_id')) if data.get('manufacturer_id') else 0
            country_origin_id = int(data.get('country_origin_id')) if data.get('country_origin_id') else 0
            warranty = int(data.get('warranty')) if data.get('warranty') else None
            stock_status = int(data.get('stock_status')) if data.get('stock_status') else 1  # Default is 1
            status = int(data.get('status')) if data.get('status') else 1  # Default is 1
            publish_status = int(data.get('publish_status')) if data.get('publish_status') else 1  # Default is 1
        except ValueError:
            return render(request, 'product_form.html', {'error': 'Invalid number input.'})

        try:
            new_product = Product.objects.create(
                product_type=data.get('product_type', ''),
                parent_sku=data.get('parent_sku', ''),
                bundle_sku=data.get('bundle_sku', ''),
                is_alias=is_alias_checked,
                sku=data.get('sku'),
                title=data.get('title'),
                subtitle=data.get('subtitle'),
                description=data.get('description'),
                short_description=data.get('short_description'),
                brand_id=brand_id,
                manufacturer_id=manufacturer_id,
                ean=data.get('ean'),
                upc=data.get('upc'),
                isbn=data.get('isbn'),
                mpn=data.get('mpn'),
                country_origin_id=country_origin_id,
                status_condition=data.get('condition', 'new'),

                asin=data.get('asin'),
                fnsku=data.get('fnsku'),
                fba_sku=data.get('fba_sku'),
                is_fba='is_fba' in data,
                isbn_type=data.get('isbn_type'),
                barcode_label_type=data.get('barcode_label_type'),
                prep_type=data.get('prep_type', 'no_prep_needed'),

                stock_status=stock_status,
                status=status,
                publish_status=publish_status,

                warranty=warranty,
                product_tags=data.get('product_tags'),
            )
            return JsonResponse({"status": True, "message": "Product added successfully", "product_id":
                                 new_product.product_id})

        except IntegrityError:
            error_message = f"Product creation failed. The SKU '{data.get('sku')}' may already exist."
            return render(request, 'product_form.html', {'error': error_message})
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"
            return render(request, 'product_form.html', {'error': error_message})


    if request.method == "GET":
        # context = locals()
        context = {
            'user': request.user.id,
            'brands': brand,
            'manufacturers': manufacturers,
            'countries_list': countries_list,
            'currency_list':currency_list
        }
        return render(request, 'sbadmin/pages/product/add/addnew_form.html', context)


@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    brand = Brand.objects.filter(status=1).all()
    manufacturers = Manufacturer.objects.filter(status=1).all()

    currency_list = Country.objects.values('currency').annotate(
        id=Min('id'),  # pick country with smallest ID per currency
        currency_name=Min('currency_name')
    )
    countries_list = Country.objects.values('name', 'id')
    product_types = [
        (1, 'Standard'),
        (2, 'Parent'),
        (3, 'Child'),
        (4, 'Bundle'),
    ]
    context = {
        'user': request.user.id,
        'product':product,
        'brands': brand,
        'manufacturers': manufacturers,
        'countries_list': countries_list,
        'currency_list': currency_list,
        'product_types': product_types,
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

    category = Category.objects.filter(status=1).all()
    brand = Brand.objects.filter(status=1).all()
    manufacturers = Manufacturer.objects.filter(status=1).all()

    currency_list = Country.objects.values('currency').annotate(
        id=Min('id'),  # pick country with smallest ID per currency
        currency_name=Min('currency_name')
    )
    countries_list = Country.objects.values('name', 'id')
    product_id = request.POST.get('product_id')

    if request.method == 'POST':
        data = request.POST  # request.POST is a QueryDict
        try:
            brand_id = int(data.get('brand_id')) if data.get('brand_id') else None
        except ValueError:
            brand_id = None  # Handle non-integer input gracefully

        try:
            manufacturer_id = int(data.get('manufacturer_id')) if data.get('manufacturer_id') else None
            country_origin_id = int(data.get('country_origin_id')) if data.get('country_origin_id') else 0
            warranty = int(data.get('warranty')) if data.get('warranty') else None
            stock_status = int(data.get('stock_status')) if data.get('stock_status') else 1  # Default is 1
            status = int(data.get('status')) if data.get('status') else 1  # Default is 1
            publish_status = int(data.get('publish_status')) if data.get('publish_status') else 1  # Default is 1
            is_alias_checked = True if data.get('is_alias') else False
        except ValueError:
            return JsonResponse({"status": True, "message": "Invalid number input.", "product_id":
                product_id, 'error': 'Invalid number input.'})
        try:
            product_details = Product.objects.get(product_id=product_id)
            if not product_details:
                return JsonResponse({"status": False, "message": "Invalid product details"})

            product_details.product_type = data.get('product_type', '')
            product_details.parent_sku = data.get('parent_sku', '')
            product_details.bundle_sku = data.get('bundle_sku', '')

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
            product_details.status_condition = data.get('condition', 'new')

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

            product_details.save()

            return JsonResponse({"status": True, "message": "Product details updated successfully", "product_id":
                product_details.product_id})

        except IntegrityError:
            error_message = f"Product creation failed. The SKU '{data.get('sku')}' may already exist."
            return JsonResponse({"status": False, "message": error_message, "product_id":
                product_id})

        except Exception as e:
            print(str(e))
            error_message = f"An unexpected error occurred: {e}"
            return JsonResponse({"status": False, "message": error_message, "product_id":
                product_id})



@login_required
def delete_product(request, product_id):
    if request.method != "DELETE":
        return JsonResponse({"status": False, "message": "Invalid request method"}, status=400)
    product = Product.objects.filter(product_id=product_id).first()

    if not product:
        return JsonResponse({"status": False, "message": "Product not found"}, status=404)

    try:
        product.delete()
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

    return JsonResponse({"status": "success", "deleted": len(ids)})