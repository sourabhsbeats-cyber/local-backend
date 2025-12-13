from logging import exception

from django.db import transaction
from django.urls import reverse
from django.shortcuts import render
from django.shortcuts import get_object_or_404
from store_admin.helpers import get_int, get_bool_int, get_decimal
from store_admin.models.product_model import Product, ProductShippingDetails, ProductPriceDetails, \
    ProductStaticAttributes, ProductDynamicAttributes, ProductImages
from store_admin.models.setting_model import Category, Brand, Manufacturer, AttributeDefinition
from store_admin.models.vendor_models import Vendor, VendorContact
from django.db import IntegrityError
from store_admin.models import Country
from store_admin.models.warehouse_setting_model import Warehouse
from store_admin.models.warehouse_transaction_model import ProductWarehouse
from django.db.models import IntegerField, TextField
from django.db.models import Exists
from rest_framework.decorators import api_view
from django.conf import settings
from django.http import JsonResponse
import json
from rest_framework import serializers
from django.contrib.auth.decorators import login_required
import math
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Value, CharField, OuterRef, Subquery, Case, When, Q
from django.db.models.functions import Coalesce
from rest_framework.renderers import JSONRenderer
from rest_framework.decorators import api_view, renderer_classes, permission_classes
import os
from django.templatetags.static import static

from store_admin.views.serializers.product_serializers import ProductImageSerializer


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

@login_required
def save_product_image(request):
    if request.method == "POST":
        cdn = request.POST.get("cdn_url")
        img = ProductImages(product_id=request.POST["product_id"])

        if cdn:
            img.cdn_url, img.image_path = cdn, None
        elif request.FILES.get("file"):
            img.image_path = request.FILES["file"]
            img.save()  # save first so path is created
            #img.cdn_url = f"{settings.MEDIA_URL}{img.image_path.name}"
            img.cdn_url = f"{settings.CDN_DOMAIN}{settings.MEDIA_URL}{img.image_path.name}"
        img.save()
        return JsonResponse({"status": "saved", "cdn_url": img.cdn_url})

@api_view(["GET"])
def list_product_images(request, product_id):
    q = ProductImages.objects.filter(product_id=request.GET.get("product_id")) if request.GET.get("product_id") else ProductImages.objects.all()
    return JsonResponse(ProductImageSerializer(q, many=True).data)

@api_view(["DELETE"])
def delete_product_image(request, product_image_id):
    try:
        img = ProductImages.objects.get(product_image_id=product_image_id)  # ❗ primary key lookup fix
    except ProductImages.DoesNotExist:
        return JsonResponse({"status": "not found"}, status=404)

    # If local image exists → delete physical file
    if img.image_path:
        p = img.image_path.path
        os.path.exists(p) and os.remove(p)

    #  If image_path is None → still return success
    img.delete()
    return JsonResponse({"status": "deleted"}, status=200)

#edit form
@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    #category = Category.objects.filter(status=1).all()
    brand = Brand.objects.filter(status=1).all()
    manufacturers = Manufacturer.objects.filter(status=1).all()
    vendors = Vendor.objects.filter(status=1).all()
    shipping_info =  ProductShippingDetails.objects.filter(product_id=product_id).first()
    price_info = ProductPriceDetails.objects.filter(product_id=product_id).first()

    static_attributes = ProductStaticAttributes.objects.filter(product_id=product_id).first()
    custom_atributes = AttributeDefinition.objects.all()
    product_images = ProductImages.objects.filter(product_id=product_id).all()
    warehouses = Warehouse.objects.all().order_by("warehouse_name").annotate(
        current_qty=Coalesce(
            Subquery(
                ProductWarehouse.objects.filter(
                    product_id=product_id,
                    warehouse_id=OuterRef("warehouse_id")
                ).order_by("-product_wh_id").values("stock")[:1],
                output_field=IntegerField()
            ), 0
        ),
        is_enabled=Exists(
            ProductWarehouse.objects.filter(
                product_id=product_id,
                warehouse_id=OuterRef("warehouse_id")
            )
        )
    )
    countries_list = Country.objects.values('name', 'id')
    context = {
        'custom_atributes':custom_atributes,
        'user': request.user.id,
        'brands': brand,
        'warehouses': warehouses,
        'manufacturers': manufacturers,
        'countries_list': countries_list,
        'vendors': vendors,'product_images':product_images, 
        'static_attributes': static_attributes,
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
    # ---- Context ----
    context = {
        "user": request.user.id,
    }
    return render(request, 'sbadmin/pages/product/all_listing.html', context)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def products_json(request):
    stock_sub = ProductWarehouse.objects.values("product_id").annotate(
        total_stock=Sum("stock")
    ).values("product_id", "total_stock")
    qs = Product.objects.annotate(
        total_stock_qty=Coalesce(
            Subquery(stock_sub.filter(product_id=OuterRef("product_id")).values("total_stock")[:1]),
            Value(0),
            output_field=IntegerField()  #  numeric
        ),
        product_type_name=Case(
            When(product_type="1", then=Value("Standard")),
            When(product_type="2", then=Value("Parent")),
            When(product_type="3", then=Value("Child")),
            When(product_type="4", then=Value("Bundle")),
            default=Value("Unknown"),
            output_field=TextField()  #  pure text
        ),
        brand_name_val=Coalesce(
            Subquery(Brand.objects.filter(brand_id=OuterRef("brand_id")).values("name")[:1]),
            Value(""),
            output_field=TextField()  #  pure text
        ),
    )
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

    size = min(size, 50)  # ✅ max 50 cap

    total = qs.count()
    start = (page - 1) * size
    end = start + size

    data = list(qs.order_by("product_id")[start:end].values(
        "product_id", "title", "sku", "brand_name_val", "product_type_name", "total_stock_qty"
    ))

    last_page = math.ceil(total / size) if total else 1

    #  Return EXACT Tabulator compatible JSON
    return Response({
        "data": data,
        "last_page": last_page,
        "total": total, "row_count":200

    })

# edit form save action
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
            product_details.is_taxable = True if data.get('is_taxable') else False
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

            # --- 4. Update Static Attributes ---
            product_static_attributes = ProductStaticAttributes.objects.filter(product_id=product_id).first()
            try:
                if product_static_attributes:
                    product_static_attributes.attrib_depth = get_decimal(data, 'attrib_depth')
                    product_static_attributes.attrib_weight = get_decimal(data, 'attrib_weight')
                    product_static_attributes.attrib_width = get_decimal(data, 'attrib_width')
                    product_static_attributes.attrib_height = get_decimal(data, 'attrib_height')
                    product_static_attributes.attrib_material = data.get( 'attrib_material')
                    product_static_attributes.attrib_size = data.get('attrib_size')
                    product_static_attributes.attrib_color = data.get( 'attrib_color')
                    product_static_attributes.attrib_compatibility = data.get('attrib_compatibility')
                    product_static_attributes.save()
                else:
                    ProductStaticAttributes.objects.create(
                        product_id=product_details.product_id,
                        attrib_depth=get_decimal(data, 'attrib_depth'),
                        attrib_weight=get_decimal(data, 'attrib_depth'),
                        attrib_width=get_decimal(data, 'attrib_width'),
                        attrib_height=get_decimal(data, 'attrib_height'),
                        attrib_material=data.get('attrib_material'),
                        attrib_size=data.get( 'attrib_size'),
                        attrib_color=data.get( 'attrib_color'),
                        attrib_compatibility=data.get('attrib_compatibility'),
                        created_by=request.user.id
                    )
            except Exception as e:
                print(f"Error creating attribute details: {e}")
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
        ProductPriceDetails.objects.filter(product_id=product_id).delete()
        ProductShippingDetails.objects.filter(product_id=product_id).delete()
        ProductStaticAttributes.objects.filter(product_id=product_id).delete()
        ProductWarehouse.objects.filter(product_id=product_id).delete()
        ProductDynamicAttributes.objects.filter(product_id=product_id).delete()

        return JsonResponse({"status": True, "message": "Product deleted successfully"})
    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)}, status=500)

@login_required
def delete_product_bulk(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"})

    data = json.loads(request.body)
    ids = data.get("ids", [])

    if not ids:
        return JsonResponse({"status": "error", "message": "No products selected"})

    Product.objects.filter(product_id__in=ids).delete()

    ProductPriceDetails.objects.filter(product_id__in=ids).delete()

    ProductShippingDetails.objects.filter(product_id__in=ids).delete()

    ProductStaticAttributes.objects.filter(product_id__in=ids).delete()

    ProductDynamicAttributes.objects.filter(product_id__in=ids).delete()
    ProductWarehouse.objects.filter(product_id__in=ids).delete()
    return JsonResponse({"status": "success", "deleted": len(ids)})

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
            product_details.description = data.get('description').strip()
            product_details.short_description = data.get('short_description').strip()

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
            product_details.is_taxable = True if data.get('is_taxable') else False

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
            product_details.full_clean()
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

            # --- 3. Create Product Attribs ---

            try:
                ProductStaticAttributes.objects.create(
                    product_id=product_details.product_id,
                    attrib_depth=get_decimal(data,'attrib_depth'),
                    attrib_weight=get_decimal(data,'attrib_weight'),
                    attrib_width=get_decimal(data,'attrib_width'),
                    attrib_height=get_decimal(data,'attrib_height'),
                    attrib_material=data.get('attrib_material'),
                    attrib_size=data.get('attrib_size'),
                    attrib_color=data.get('attrib_color'),
                    attrib_compatibility=data.get('attrib_compatibility'),
                    created_by=request.user.id
                )
            except (ValueError, TypeError) as e:
                # Handle conversion errors if non-numeric data is passed to int()
                print(f"Error creating shipping details: {e}")
                # You should raise an appropriate error or return a response here
                raise

            return JsonResponse({
                "status": True,
                "message": "Product created successfully",
                "product_id": product_details.pk,
                "redirect_url":reverse("edit_product", args=[product_details.pk])
            })

    except IntegrityError:
        error_message = f"Product creation failed. The SKU '{data.get('sku')}' may already exist."
        return JsonResponse({"status": False, "message": error_message })

    except Exception as e:
        print(str(e))
        error_message = f"An unexpected error occurred: {e}"
        return JsonResponse({"status": False, "message": error_message})

@login_required
def add_dynamic_attribute(request):
    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid request"})

    data = request.POST
    product_id = data.get("product_id")
    attribute_id = data.get("attribute_id")
    attribute_values = data.get("attrib_values", "").strip()
    user_id = request.user.id

    if not product_id or not attribute_id:
        return JsonResponse({"status": False, "message": "Product and Attribute required"})

    if ProductDynamicAttributes.objects.filter(
        product_id=product_id,
        attribute_id=attribute_id
    ).exists():
        return JsonResponse({"status": False, "message": "Attribute already added for this product"})

    try:
        ProductDynamicAttributes.objects.create(
            product_id=product_id,
            attribute_id=attribute_id,
            attribute_values=attribute_values or None,
            created_by=user_id,
        )
        return JsonResponse({"status": True, "message": "Inserted"})
    except Exception as ex:
        return JsonResponse({"status": False, "message": str(ex)})

@login_required
def list_dynamic_attributes(request):
    product_id = request.GET.get("product_id")
    if not product_id:
        return JsonResponse({"status": False, "message": "Invalid product"})

    dyn_rows = list(
        ProductDynamicAttributes.objects.filter(product_id=product_id).values(
            "dynamic_attribute_id", "product_id", "attribute_id", "attribute_values"
        )
    )
    attrib_ids = [r["attribute_id"] for r in dyn_rows]
    attrib_rows = list(
        AttributeDefinition.objects.filter(attribute_id__in=attrib_ids).values(
            "attribute_id", "attribute_name", "attribute_type", "default_value", "option_list"
        )
    )
    attrib_map = {a["attribute_id"]: a for a in attrib_rows}
    data = []
    for r in dyn_rows:
        real = attrib_map.get(r["attribute_id"], {})
        data.append({
            **r,
            "attribute_name": real.get("attribute_name"),
            "attribute_type": real.get("attribute_type"),
            "default_value": real.get("default_value"),
            "option_list": real.get("option_list"),
        })
    return JsonResponse({"status": True, "data": data})

@login_required
def update_dynamic_attribute(request):
    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid request"})

    data = request.POST
    dynamic_attrib_id = data.get("dynamic_attrib_id")
    attrib_values = data.get("attrib_values", "").strip()

    if not dynamic_attrib_id:
        return JsonResponse({"status": False, "message": "Attribute ID required"})

    try:
        ProductDynamicAttributes.objects.filter(
            dynamic_attribute_id=dynamic_attrib_id
        ).update(
            attribute_values=attrib_values or None,
            created_by=request.user.id,
        )
        return JsonResponse({"status": True, "message": "Updated"})
    except Exception as ex:
        return JsonResponse({"status": False, "message": str(ex)})

@login_required
def remove_dynamic_attribute(request):
    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid request"})

    dynamic_attrib_id = request.POST.get("dynamic_attrib_id")
    if not dynamic_attrib_id:
        return JsonResponse({"status": False, "message": "Attribute ID required"})

    try:
        ProductDynamicAttributes.objects.filter(
            dynamic_attribute_id=dynamic_attrib_id
        ).delete()
        return JsonResponse({"status": True, "message": "Removed"})
    except Exception as ex:
        return JsonResponse({"status": False, "message": str(ex)})

#auto complete product search
def api_product_search(request):
    try:
        product_image_sub = ProductImages.objects.filter(
            product_id=OuterRef("product_id")
        ).order_by("product_image_id").values("cdn_url")[:1]

        # Total Stock (may be missing)
        stock_sub = ProductWarehouse.objects.filter(
            product_id=OuterRef("product_id")
        ).values("product_id").annotate(
            qty=Sum("stock")
        ).values("qty")[:1]

        # Sale Price (may be missing)
        sale_price_sub = ProductPriceDetails.objects.filter(
            product_id=OuterRef("product_id")
        ).values("sale_price")[:1]

        # Base queryset
        qs = Product.objects.annotate(
            image=Coalesce(Subquery(product_image_sub), Value(None), output_field=TextField()),
            qty=Coalesce(Subquery(stock_sub), Value(0), output_field=IntegerField()),
            sale_price=Coalesce(Subquery(sale_price_sub), Value(None), output_field=IntegerField()),
            prep_type_name=Case(When(prep_type="no_prep_needed", then=Value("No Prep Needed")),
                When(prep_type="polybag", then=Value("Polybagging")), When(prep_type="bubble_wrap", then=Value("Bubble Wrap")),
                When(prep_type="labeling", then=Value("Labeling")), default=Value(""),output_field=TextField()
            ),
            barcode_label_type_name= Case(When(barcode_label_type="manufacturer", then=Value("Manufacturer")),
                When(barcode_label_type="amazon_barcode", then=Value("Amazon Barcode")),  default=Value(""),
                                          output_field=TextField()
            ),
        )

        # Search filter
        q = request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(sku__icontains=q)
            )
        NO_IMAGE = static("no_product_image.png")
        # Build Response
        data = []
        for p in qs[:20]:  # limit 20 results
            data.append({
                "id": p.product_id,
                "title": p.title,
                "image":p.image if p.image else NO_IMAGE,
                "stock_qty": p.qty,
                "sku": p.sku,
                "asin": p.asin,
                "fnsku": p.fnsku,
                "ean":p.ean, "prep_type":p.prep_type_name,
                "is_taxfree":True if p.is_taxable else False,  # send as number for JS
                "barcode_label_type":p.barcode_label_type_name,
                "price": p.sale_price,
            })

        return JsonResponse({"status": True, "data": data})
    except Exception as e:
        print(e)
        return JsonResponse({"status":False, "data":[]})