from logging import exception

from django.db import transaction
from django.urls import reverse
from django.shortcuts import render
from django.shortcuts import get_object_or_404
from store_admin.helpers import get_int, get_bool_int, get_decimal
from store_admin.models.product_model import Product, ProductShippingDetails, ProductPriceDetails, \
    ProductStaticAttributes, ProductDynamicAttributes, ProductImages, ProductType
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

from rest_framework import status
#Product Add New Form - Only GET
from django.db import transaction, IntegrityError
from django.http import JsonResponse

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_create_product(request):
    # React-la irunthu vara data QueryDict-ah kidaikkum
    data = request.data

    # 1. Numeric Conversions (Get helpers or use direct int conversion)
    try:
        # ID fields default-ah 0 set pannuvom (as per your model default=0)
        brand_id = int(data.get('brand_id')) if data.get('brand_id') else 0
        manufacturer_id = int(data.get('manufacturer_id')) if data.get('manufacturer_id') else 0
        country_origin_id = int(data.get('country_origin_id')) if data.get('country_origin_id') else 0

        # Choice fields/integers
        stock_status = int(data.get('stock_status', 1))
        status = int(data.get('status', 1))
        publish_status = int(data.get('publish_status', 1))

    except ValueError:
        return JsonResponse({"status": False, "message": "Invalid number input for ID or Status fields."})

    try:
        with transaction.atomic():
            # 2. Main Product Create Logic
            # Unwanted shipping/price/attribute tables ellathayum remove panniyachu
            new_product = Product.objects.create(
                # PRODUCT TYPE & ALIAS
                product_type=int(data.get('product_type', 43)),
                is_alias=True if data.get('is_alias') == 'true' or data.get('is_alias') == 'on' else False,

                # BASIC INFO
                sku=data.get('sku'),
                title=data.get('title'),
                subtitle=data.get('subtitle'),
                description=data.get('description'),
                short_description=data.get('short_description'),

                # IDENTIFIERS
                brand_id=brand_id,
                manufacturer_id=manufacturer_id,
                ean=data.get('ean'),
                upc=data.get('upc'),
                isbn=data.get('isbn'),
                mpn=data.get('mpn'),
                country_origin_id=country_origin_id,
                status_condition=data.get('status_condition', 'new'),

                # AMAZON IDENTIFIERS
                asin=data.get('asin'),
                fnsku=data.get('fnsku'),
                fba_sku=data.get('fba_sku'),
                is_fba=True if data.get('is_fba') == 'true' or data.get('is_fba') == 'on' else False,
                is_taxable=True if data.get('is_taxable') == 'true' or data.get('is_taxable') == 'on' else False,

                # SYSTEM & STATUS
                stock_status=stock_status,
                status=status,
                publish_status=publish_status,

                # OTHER
                vendor_sku=data.get('vendor_sku'),
                sbau=data.get('sbau'),
                created_by=request.user.id,
                updated_by=request.user.id
            )

            # Success response with the new product_id
            return JsonResponse({
                "status": True,
                "message": "Product created successfully",
                "product_id": new_product.product_id
            })

    except IntegrityError:
        # SKU unique=True constraint catch pannum
        return JsonResponse({"status": False, "message": f"SKU '{data.get('sku')}' already exists."})

    except Exception as e:
        # Ethavathu error vantha catch panni error message anupum
        return JsonResponse({"status": False, "message": str(e)})

#edit form
@api_view(["GET"])
def get_product_details_api(request, product_id):
    # 1. Fetch main product or return 404
    product = get_object_or_404(Product, product_id=product_id)

    # 2. Fetch Related Information
    shipping_info = ProductShippingDetails.objects.filter(product_id=product_id).first()
    price_info = ProductPriceDetails.objects.filter(product_id=product_id).first()
    static_attributes = ProductStaticAttributes.objects.filter(product_id=product_id).first()

    # 3. Warehouse Annotations Logic
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

    # 4. Manually construct JSON data
    # This matches your React productData state keys
    data = {
        "status": True,
        "data": {
            "product_id": product.product_id,
            "sku": product.sku,
            "title": product.title,
            "subtitle": product.subtitle,
            "description": product.description,
            "short_description": product.short_description,
            "product_type": product.product_type,
            "is_alias": product.is_alias,


            "inventory_status": {
                "stock_status": product.stock_status,
                "status": product.status,
                "publish_status": product.publish_status,
            },
            "amazon_identifiers":{
                "asin": product.asin,
                "fnsku": product.fnsku,
                "fba_sku": product.fba_sku,
                "is_fba": product.is_fba,
                "prep_type":product.prep_type,
                "barcode_label_type":product.barcode_label_type,
                "amazon_size":product.amazon_size
            },
            "pricing": {
                "is_taxable": product.is_taxable,
                "sale_price": price_info.sale_price if price_info else "0.00",
                "retail_price":price_info.retail_price if price_info else "0.00",
                "cost_per_item": price_info.cost_per_item if price_info else "0.00",
                "margin_percent": price_info.margin_percent if price_info else "0.00",
                "profit": price_info.profit if price_info else "0.00",
                "min_price": price_info.min_price if price_info else "0.00",
                "max_price": price_info.max_price if price_info else "0.00",
                "estimated_shipping_cost": price_info.estimated_shipping_cost if price_info else "0.00",
                "preferred_vendor": product.preferred_vendor,
                "vendor_sku": product.vendor_sku if price_info else "0.00",
            } if price_info else {},

            "identifiers":{
                "brand_id": product.brand_id,
                "manufacturer_id": product.manufacturer_id,
                "ean": product.ean,
                "upc": product.upc,
                "isbn": product.isbn,
                "mpn": product.mpn,
                "country_id": product.country_origin_id,
                "status_condition": product.status_condition,
            },
            # Related Details Objects
            "shipping": {
                "fast_dispatch": shipping_info.fast_dispatch  if shipping_info else False,
                "free_shipping": shipping_info.free_shipping if shipping_info else False,
                "bulky_product": shipping_info.bulky_product if shipping_info else 0,
                "international_note": shipping_info.international_note if shipping_info else 0,
                "example_reference": shipping_info.example_reference if shipping_info else 0,
                "ships_from": shipping_info.ships_from if shipping_info else 0,
                "handling_time_days": shipping_info.handling_time_days if shipping_info else 0,
                "sbau": product.sbau,
            } if shipping_info else {},

            "other_info": {
                "warranty": product.warranty,
                "product_tags": product.product_tags,
            } ,

            "attributes": {
                "color": str(static_attributes.attrib_color) if static_attributes else "0",
                "compatibility": static_attributes.attrib_compatibility if static_attributes else "",
                "depth": static_attributes.attrib_depth if static_attributes else "",
                "height": static_attributes.attrib_height if static_attributes else "",
                "material": static_attributes.attrib_material if static_attributes else "",
                "size": static_attributes.attrib_size if static_attributes else "",
                "weight": static_attributes.attrib_weight if static_attributes else "",
                "width": static_attributes.attrib_width if static_attributes else "",
            } if static_attributes else {},

            # Warehouse List
            "warehouses": list(warehouses.values('warehouse_id', 'warehouse_name', 'current_qty', 'is_enabled'))
        }
    }

    return JsonResponse(data)
















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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_all_product_types(request):
    """
    Returns a list of all product types (Standard, Parent, Child, etc.)
    """
    prd_types_query = ProductType.objects.order_by("type_name").all()
    results = []  # Renamed from prod_type to avoid conflict

    for pt in prd_types_query:
        results.append({
            "type_name": pt.type_name,
            "product_type_id": pt.product_type_id
        })

    return JsonResponse({
        "status": True,  # Added for consistency with your React response checks
        "data": results,
    })

# edit form save action
@api_view(["PUT"])
def save(request, product_id):
    if not product_id:
        return JsonResponse({"status": False, "message": "Invalid request"}, status=400)

    data = request.data  # request.POST is a QueryDict
    product_id = data.get("product_id")
    try:
        brand_id = int(data.get('brand_id')) if data.get('brand_id') else None
    except ValueError:
        brand_id = None  # Handle non-integer input gracefully

    try:
        is_alias_checked = True if data.get('is_alias') else False
    except ValueError: #stock_status, Status, Publish
        return JsonResponse({"status": True, "message": "Invalid number input.", 'error': 'Invalid number input.'})

    try:
        product_details = Product.objects.get(product_id=product_id)
        if not product_details:
             return JsonResponse({"status": False, "message": "Invalid product details"})
        with transaction.atomic():
            identifiers_data = data.get("identifiers", {})
            amazon_identifiers_data = data.get("amazon_identifiers", {})
            inventory_status_data = data.get("inventory_status", {})
            pricing_data = data.get("pricing", {})
            other_info_data = data.get("other_info", {})
            shipping = data.get("shipping", {})


            product_details.product_type = data.get('product_type', '')
            product_details.is_alias = is_alias_checked
            #product_details.sku = data.get('sku')
            product_details.title = data.get('title')
            product_details.subtitle = data.get('subtitle')
            product_details.description = data.get('description')
            product_details.short_description = data.get('short_description')
            product_details.brand_id = identifiers_data.get('brand_id')
            product_details.manufacturer_id = identifiers_data.get('manufacturer_id')
            product_details.ean = identifiers_data.get('ean')
            product_details.upc = identifiers_data.get('upc')
            product_details.isbn = identifiers_data.get('isbn')
            product_details.mpn = identifiers_data.get('mpn')
            product_details.country_origin_id = identifiers_data.get('country_id')
            product_details.status_condition = identifiers_data.get('status_condition', 'new')
            #Amazon Identifiers
            product_details.asin = amazon_identifiers_data.get('asin')
            product_details.fnsku = amazon_identifiers_data.get('fnsku')
            product_details.fba_sku = amazon_identifiers_data.get('fba_sku')
            product_details.is_fba = True if amazon_identifiers_data.get('is_fba') else False
            product_details.amazon_size = amazon_identifiers_data.get('amazon_size')
            product_details.barcode_label_type = amazon_identifiers_data.get('barcode_label_type')
            product_details.prep_type = amazon_identifiers_data.get('prep_type')

            # Inventory & Status
            product_details.stock_status = inventory_status_data.get('stock_status')
            product_details.status = inventory_status_data.get('status')
            product_details.publish_status = inventory_status_data.get('publish_status')

            product_details.preferred_vendor = pricing_data.get('preferred_vendor')
            product_details.vendor_sku =  pricing_data.get('vendor_sku')


            product_details.isbn_type = data.get('isbn_type')

            product_details.warranty = other_info_data.get('warranty')
            product_details.product_tags = other_info_data.get('product_tags')

            product_details.updated_by = request.user.id


            product_details.sbau = shipping.get('sbau')
           # product_details.created_by = request.user.id
            #product_details.created_by = request.user.id
            product_details.is_taxable = get_bool_int(pricing_data, 'is_taxable')

            product_details.save()
            # --- 2. Update Shipping Details ---

            try:

                product_shipping_details = ProductShippingDetails.objects.filter(product_id=product_id).first()
                if product_shipping_details:
                    product_shipping_details.fast_dispatch = get_int(shipping,  'fast_dispatch')
                    product_shipping_details.free_shipping = get_int(shipping, 'free_shipping')
                    product_shipping_details.handling_time_days = get_int(shipping, 'handling_time_days')
                    product_shipping_details.bulky_product = get_int(shipping, 'bulky_product')
                    product_shipping_details.international_note = shipping.get('international_note')
                    product_shipping_details.example_reference = shipping.get('example_reference')
                    product_shipping_details.ships_from = shipping.get('ships_from')
                    product_shipping_details.save()
                else:
                    ProductShippingDetails.objects.create(
                        product_id=product_details.product_id,
                        fast_dispatch= shipping.get('fast_dispatch'),
                        free_shipping= shipping.get( 'free_shipping'),
                        handling_time_days=shipping.get( 'handling_time_days'),
                        bulky_product= shipping.get( 'bulky_product'),
                        international_note=shipping.get('international_note'),
                        example_reference=shipping.get('example_reference'),
                        ships_from=shipping.get('ships_from'),
                        created_by=request.user.id
                    )
            except (ValueError, TypeError) as e:
                # Handle conversion errors if non-numeric data is passed to int()
                print(f"Error creating shipping details: {e}")
                # You should raise an appropriate error or return a response here
                raise

            # --- 3. Update Price Details ---
            product_price_details = ProductPriceDetails.objects.filter(product_id=product_id).first()
            # pricing_data

            try:
                if product_price_details:
                    product_price_details.sale_price = get_decimal(pricing_data, 'sale_price')
                    product_price_details.retail_price = get_decimal(pricing_data, 'retail_price')
                    product_price_details.cost_per_item = get_decimal(pricing_data, 'cost_per_item')
                    product_price_details.margin_percent = get_decimal(pricing_data, 'margin_percent')
                    product_price_details.profit = get_decimal(pricing_data, 'profit')
                    product_price_details.min_price = get_decimal(pricing_data, 'min_price')
                    product_price_details.max_price = get_decimal(pricing_data, 'max_price')
                    product_price_details.estimated_shipping_cost = get_decimal(pricing_data, 'estimated_shipping_cost')
                    product_price_details.save()
                else:
                    ProductPriceDetails.objects.create(
                        product_id=product_details.product_id,
                        sale_price=get_decimal(pricing_data,'sale_price') ,
                        retail_price=get_decimal(pricing_data,'retail_price'),
                        cost_per_item=get_decimal(pricing_data,'cost_per_item'),
                        margin_percent=get_decimal(pricing_data,'margin_percent'),
                        profit=get_decimal(pricing_data,'profit'),
                        min_price=get_decimal(pricing_data,'min_price'),
                        max_price=get_decimal(pricing_data,'max_price'),
                        estimated_shipping_cost=get_decimal(pricing_data,'estimated_shipping_cost'),
                        created_by=request.user.id
                    )
            except Exception as e:
                print(f"Error creating price details: {e}")
                # Handle the error appropriately (e.g., log it, return an error response)
                raise

            # --- 4. Update Static Attributes ---
            product_static_attributes = ProductStaticAttributes.objects.filter(product_id=product_id).first()
            try:
                attributes_data = data.get("attributes", {})
                if product_static_attributes:
                    product_static_attributes.attrib_depth = get_decimal(attributes_data, 'depth')
                    product_static_attributes.attrib_weight = get_decimal(attributes_data, 'weight')
                    product_static_attributes.attrib_width = get_decimal(attributes_data, 'width')
                    product_static_attributes.attrib_height = get_decimal(attributes_data, 'height')
                    product_static_attributes.attrib_material = attributes_data.get( 'material')
                    product_static_attributes.attrib_size = attributes_data.get('size')
                    product_static_attributes.attrib_color = attributes_data.get( 'color')
                    product_static_attributes.attrib_compatibility = attributes_data.get('compatibility')
                    product_static_attributes.save()
                else:
                    ProductStaticAttributes.objects.create(
                        product_id=product_details.product_id,
                        attrib_depth=get_decimal(attributes_data, 'depth'),
                        attrib_weight=get_decimal(attributes_data, 'weight'),
                        attrib_width=get_decimal(attributes_data, 'width'),
                        attrib_height=get_decimal(attributes_data, 'height'),
                        attrib_material=attributes_data.get('material'),
                        attrib_size=attributes_data.get( 'size'),
                        attrib_color=attributes_data.get( 'color'),
                        attrib_compatibility=attributes_data.get('compatibility'),
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
        NO_IMAGE = request.build_absolute_uri(
            static("sbadmin/dist/img/no_product_image.png")
        )
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