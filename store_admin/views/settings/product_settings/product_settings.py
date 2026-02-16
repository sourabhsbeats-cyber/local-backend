from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from rest_framework.decorators import api_view

from store_admin.models.payment_terms_model import PaymentTerm
from django.contrib.auth.decorators import login_required

from store_admin.models.product_model import ProductStaticAttributes
from store_admin.models.setting_model import Manufacturer, Brand, Category, AttributeDefinition, UnitOfMeasurements



@api_view(["POST"])
def add_new_category(request):
    data = request.data
    is_primary = int(data.get("is_primary", "0"))

    if len(data.get("name")) < 2:
        return JsonResponse({"status": False, "message": "Invalid category name",
                             "error": "Invalid request"}, status=500)
    if is_primary==0 and (data.get("parent_id") is None):
        return JsonResponse({"status": False, "message": "Parent Category is required",
                             "error": "Invalid request"}, status=500)
    if Category.objects.filter(name=data.get("name")).exists():
        return JsonResponse({"status": False, "message": "Category name already exists",
                             "error": "Invalid request"}, status=500)
    try:
        Category.objects.create(
            name=data.get("name"),
            is_primary=data.get("is_primary"),
            primary_category_id=data.get("parent_id") or None,
            status=data.get("status"),
            created_by=request.user.id
        )
    except Exception as e:
        return JsonResponse({"status": True, "data": None, "message":"Error creating"})

    return JsonResponse({"status":True, "message":"Category created successfully."})

#update_category
@api_view(["PUT"])
def update_category(request, category_id):

    data = request.data

    category = get_object_or_404(Category, category_id=category_id)
    category.name = data.get("name")
    is_primary = int(data.get("is_primary", "0"))

    if len(data.get("name")) < 2:
        return JsonResponse({"status": False, "message": "Invalid category name",
                             "error": "Invalid request"}, status=500)
    if is_primary==0 and (data.get("parent_id") is None):
        return JsonResponse({"status": False, "message": "Parent Category is required",
                             "error": "Invalid request"}, status=500)

    if data.get("parent_id") == str(category_id):
        return JsonResponse({"status": False, "message": "Invalid Category details",
                             "error": "Invalid request"}, status=500)

    category.is_primary =  is_primary
    category.primary_category_id =data.get("parent_id", None)
    category.status = int(data.get("status"))
    category.save()

    return JsonResponse({"status": True, "message": "Category details updated successfully",
                         "error": "Invalid request"})

@api_view(["DELETE"])
def delete_category(request, category_id):
    term = get_object_or_404(Category, category_id=category_id)
    term.delete()
    return JsonResponse({"status": True, "message": f"Category '{term.name}' deleted successfully."})

@api_view(["GET"])
def all_product_categories(request):
    # --- Get / Paginated List ---
    search_query = request.GET.get("q", "").strip()
    terms = Category.objects.all().order_by("name")

    if search_query:
        terms = terms.filter(name__icontains=search_query)

    paginator = Paginator(terms, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    terms_data = []
    for cat in page_obj:
        terms_data.append({
            "category_id": cat.category_id,  # Using brand_id to match your JS column field
            "name": cat.name,
            "status": cat.status,
            "parent_id":cat.primary_category_id,
            "is_primary": cat.is_primary,
        })

    # Manual Serialization for 'main_categories'
    main_cats_qs = Category.objects.filter(is_primary=True, status=True).order_by("name")
    main_categories_data = [
        {"id": c.category_id, "name": c.name} for c in main_cats_qs
    ]

    return JsonResponse({
        "status": True,
        "data": terms_data,  # Tabulator expects the array here
        "last_page": paginator.num_pages,  # Needed for Tabulator remote pagination
        "main_categories": main_categories_data,
        "current_page": page_obj.number,
    })

#BRAND MANAGEMENT
@api_view(["DELETE"])
def delete_brand(request, brand_id):
    try:
        brand = get_object_or_404(Brand, brand_id=brand_id)
        brand.delete()
        return JsonResponse({"status": True, "message": "Brand deleted successfully."})

    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)}, status=500)

@api_view(["PUT"])
def update_brand(request, brand_id):
    data = request.data
    brand = get_object_or_404(Brand, brand_id=brand_id)
    brand.name = data.get("name")
    brand.status = data.get("status")
    brand.save()
    return JsonResponse({"status": True, "message": f"Brand '{brand.name}' updated successfully."})

@api_view(["POST"])
def api_create_brands(request):
    data = request.data
    try:
        brand = Brand.objects.create(
            name=data.get("name"),
            status=data.get("status"),
            created_by=request.user.id
        )
        return JsonResponse({"status": True, "message": "Brand created successfully.", "brand_id": brand.brand_id})

    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)}, status=500)

@api_view(["GET"])
def api_manage_brands(request):
    # --- GET / Paginated List ---
    search_query = request.GET.get("q", "").strip()
    brands_list = Brand.objects.all().order_by("name")

    if search_query:
        brands_list = brands_list.filter(name__icontains=search_query)

    # Pagination Logic
    paginator = Paginator(brands_list, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    brands_data = [{
        "brand_id": b.brand_id,
        "name": b.name,
        "status": b.status
    } for b in page_obj]

    # --- Matches requested branding format ---
    return JsonResponse({
        "data": brands_data,
        "last_page": paginator.num_pages,
        "total": paginator.count,
        "row_count": len(brands_data),
        "status": True, # Keeping status for frontend logic
        "search_query": search_query
    })

#api_all_brands
@api_view(["GET"])
def api_all_brands(request):
    # --- GET / Paginated List ---
    search_query = request.GET.get("brand_name")
    brands_list = Brand.objects.all().order_by("name")

    if search_query:
        search_query = search_query.strip()
        brands_list = brands_list.filter(name__icontains=search_query)

    # Pagination Logic

    brands_data = [{
        "brand_id": b.brand_id,
        "name": b.name,
        "status": b.status
    } for b in brands_list]

    # --- Matches requested branding format ---
    return JsonResponse({
        "data": brands_data,
        "status": True,
    })
#EOF BRAND MANAGEMENT

@api_view(["GET"])
def api_list_all_manufacturers(request):
     # --- Get / Paginated List ---
    search_query = request.GET.get("q", "").strip()
    page_size = request.GET.get("size", 10)  # Tabulator sends 'size'
    page_number = request.GET.get("page", 1)  # Tabulator sends 'page'

    # 2. Filter QuerySet
    terms = Manufacturer.objects.all().order_by("name")
    if search_query:
        terms = terms.filter(name__icontains=search_query)

    # 4. Manual Serialization (Converting Model objects to Dictionaries)
    # We use 'manufacturer_id' to match your frontend column 'field'
    manufacturer_list = []
    for mfg in terms:
        manufacturer_list.append({
            "manufacturer_id": mfg.manufacturer_id,
            "name": mfg.name,
            "status": 1 if mfg.status else 0,  # Ensure this matches your model field type
        })

    # 5. Return Response in Tabulator-friendly format
    return JsonResponse({
        "status": True,
        "data": manufacturer_list,
    })

@api_view(["GET"])
def list_manufacturers(request):
     # --- Get / Paginated List ---
    search_query = request.GET.get("q", "").strip()
    page_size = request.GET.get("size", 10)  # Tabulator sends 'size'
    page_number = request.GET.get("page", 1)  # Tabulator sends 'page'

    # 2. Filter QuerySet
    terms = Manufacturer.objects.all().order_by("name")
    if search_query:
        terms = terms.filter(name__icontains=search_query)

    # 3. Pagination
    paginator = Paginator(terms, page_size)
    try:
        page_obj = paginator.get_page(page_number)
    except:
        page_obj = paginator.get_page(1)

    # 4. Manual Serialization (Converting Model objects to Dictionaries)
    # We use 'manufacturer_id' to match your frontend column 'field'
    manufacturer_list = []
    for mfg in page_obj:
        manufacturer_list.append({
            "manufacturer_id": mfg.manufacturer_id,
            "name": mfg.name,
            "status": 1 if mfg.status else 0,  # Ensure this matches your model field type
        })

    # 5. Return Response in Tabulator-friendly format
    return JsonResponse({
        "status": True,
        "data": manufacturer_list,
        "last_page": paginator.num_pages,
        "total_record": paginator.count
    })

@api_view(["PUT"])
def update_manufacturers(request, manufacturer_id):
    data = request.data
    term = get_object_or_404(Manufacturer, manufacturer_id=manufacturer_id)
    term.name = data.get("name")
    term.status = data.get("status")
    term.save()
    return JsonResponse({
        "status": True, "message": f"Manufacturer '{term.name}' updated successfully."})

@api_view(["DELETE"])
def delete_manufacturers(request, manufacturer_id):
    term = get_object_or_404(Manufacturer, manufacturer_id=manufacturer_id)
    term.delete()
    return JsonResponse({"status": "success", "message": "Manufacturer deleted successfully."})

@api_view(["POST"])
def create_manufacturer(request):
    data = request.data
    Manufacturer.objects.create(
        name=data.get("name"),
        status=data.get("status"),
        created_by=request.user.id
    )
    return JsonResponse({"status":True, "message": "Manufacturer created successfully."})

#uom
@api_view(["GET"])  # Changed to GET for listing/searching
def list_uoms(request):
    # 1. Get query parameters from Tabulator
    search_query = request.GET.get("q", "").strip()
    page_size = request.GET.get("size", 10)  # Tabulator sends 'size'
    page_number = request.GET.get("page", 1) # Tabulator sends 'page'

    # 2. Filter QuerySet
    terms = UnitOfMeasurements.objects.all().order_by("name")
    if search_query:
        terms = terms.filter(name__icontains=search_query)

    # 3. Pagination
    paginator = Paginator(terms, page_size)
    page_obj = paginator.get_page(page_number)

    # 4. Manual Serialization (Crucial: Convert Model objects to List of Dicts)
    uom_list = []
    for uom in page_obj:
        uom_list.append({
            "uom_id": uom.measurement_id,          # Matches d.uom_id in your JS
            "name": uom.name,
            "short_name": uom.short_name,
            "status": 1 if uom.status else 0, # Logic check for your boolean/int status
        })

    # 5. Return JSON in the format Tabulator expects for remote pagination
    return JsonResponse({
        "status": True,
        "data": uom_list,                # Array of records
        "last_page": paginator.num_pages, # Total pages
        "total_record": paginator.count   # Total record count
    })

@api_view(["PUT"])
def update_uom(request, uom_id):
    data = request.data
    term = get_object_or_404(UnitOfMeasurements, measurement_id=uom_id)
    if data.get("short_name") in [None, ""]:
        return JsonResponse({"status": False, "message": "Short name is required."}, status=400)

    if UnitOfMeasurements.objects.filter(short_name=data.get("short_name")).exclude(measurement_id=uom_id).exists():
        return JsonResponse({"status": False, "message": "Record already exists."}, status=400)

    term.name = data.get("name")
    term.short_name = data.get("short_name")
    term.status = data.get("status")
    term.save()
    return JsonResponse({"status":True, "message": f"Record '{term.name}' updated successfully."})

@api_view(["POST"])
def create_uom(request):
    data = request.data
    if data.get("short_name") in [None, ""]:
        return JsonResponse({"status":False, "message": "Short name is required."}, status=400)

    if UnitOfMeasurements.objects.filter(short_name=data.get("short_name")).exists():
        return JsonResponse({"status":False, "message": "Record already exists."}, status=400)

    UnitOfMeasurements.objects.create(
        name=data.get("name"),
        short_name=data.get("short_name"),
        status=data.get("status"),
        created_by=request.user.id
    )
    return JsonResponse({
        "status": True, "message": "Unit created successfully."
    })

@api_view(["DELETE"])
def delete_uom(request, uom_id):
    term = get_object_or_404(UnitOfMeasurements, measurement_id=uom_id)
    term.delete()
    return JsonResponse({
        "status": True, "message": "Unit removed successfully."
    })

#attributes
@api_view(["GET"])
def list_attributes(request):
    # 1. Get query parameters sent by Tabulator
    search_query = request.GET.get("q", "").strip()
    page_size = request.GET.get("size", 10)  # Tabulator sends 'size'
    page_number = request.GET.get("page", 1)  # Tabulator sends 'page'

    # 2. Filter QuerySet
    terms = AttributeDefinition.objects.all().order_by("attribute_name")
    if search_query:
        # Search by name or type
        terms = terms.filter(attribute_name__icontains=search_query)

    # 3. Pagination
    paginator = Paginator(terms, page_size)
    page_obj = paginator.get_page(page_number)

    # 4. Manual Serialization (Converting Model instances to a list of dicts)
    attributes_list = []
    for attr in page_obj:
        attributes_list.append({
            "attribute_id": attr.attribute_id,
            "attribute_name": attr.attribute_name,
            "attribute_type": attr.attribute_type,
            "default_value": attr.default_value if attr.default_value else "",
            "option_list": attr.option_list if attr.option_list else "",
            "created_at": attr.created_at.strftime("%m/%d/%Y %I:%M %p"),
        })

    # 5. Return JSON in Tabulator-friendly format
    return JsonResponse({
        "status": True,
        "data": attributes_list,  # Array of serialized records
        "last_page": paginator.num_pages,  # Total pages for Tabulator
        "total_record": paginator.count  # Total records count
    })

@api_view(["POST"])
def create_attribute(request):
    data = request.data
    try:
        if AttributeDefinition.objects.filter(attribute_name__icontains=data.get("attribute_name")).exists():
            return JsonResponse({"status": False, "message": "Attribute name already exists"})

        AttributeDefinition.objects.create(
            attribute_name=data.get("attribute_name"),
            attribute_type=data.get("attribute_type"),
            default_value=data.get("default_value"),
            option_list=data.get("option_list", None),
            created_by=request.user.id
        )
    except Exception as e:
        return JsonResponse({"status": False, "message": "Error creating"})
    return JsonResponse({"status": True, "message": "Attribute created successfully."})


@api_view(["PUT"])
def update_attribute(request, attribute_id):
    # 1. Get the existing record
    term = get_object_or_404(AttributeDefinition, attribute_id=attribute_id)

    # 2. Extract data (handling both DRF request.data or standard json.loads)
    if hasattr(request, 'data'):
        data = request.data
    else:
        data = json.loads(request.body)

    new_name = data.get("attribute_name", "").strip()

    # 3. Check for duplicates (excluding the current record)
    if AttributeDefinition.objects.filter(attribute_name__iexact=new_name).exclude(attribute_id=attribute_id).exists():
        return JsonResponse({"status": False, "message": "Attribute name already exists"})

    # 4. Update the fields
    term.attribute_name = new_name
    term.attribute_type = data.get("attribute_type", term.attribute_type)
    term.default_value = data.get("default_value", "")

    # Logic for Option List: Clear it if type is TEXT
    if term.attribute_type == "TEXT":
        term.option_list = None
    else:
        term.option_list = data.get("option_list", "")

    # 5. SAVE the changes to the database
    term.save()

    return JsonResponse({
        "status": True,
        "message": "Attribute updated successfully",
        "data": {
            "id": term.attribute_id,
            "name": term.attribute_name
        }
    })

@api_view(["DELETE"])
def delete_attribute(request, attribute_id):
    AttributeDefinition.objects.filter(attribute_id=attribute_id).delete()
    return JsonResponse({"status": True, "message": f"Attribute deleted successfully."})


import json
@login_required
def delete_product_attributes(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"})

    data = json.loads(request.body)
    ids = data.get("ids", [])

    if not ids:
        return JsonResponse({"status": "error", "message": "No attribute selected"})

    AttributeDefinition.objects.filter(attribute_id__in=ids).delete()

    return JsonResponse({"status": "success", "deleted": len(ids)})

#EOF #attributes