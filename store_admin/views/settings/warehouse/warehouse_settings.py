from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from rest_framework.decorators import api_view

from store_admin.models import Country, State
from store_admin.models.organization_model import OrganizationInventoryLocation, OrganizationInventoryLocation
from store_admin.models.payment_terms_model import PaymentTerm
from django.contrib.auth.decorators import login_required

from store_admin.models.product_model import ProductStaticAttributes
from store_admin.models.setting_model import Manufacturer, Brand, Category, AttributeDefinition
from store_admin.models.warehouse_setting_model import Warehouse
from django.db import transaction

@api_view(["GET"])
def all_inventory_locations(request):
    # --- Data Retrieval & Filtering ---
    search_query = request.GET.get("q", "").strip()
    # Filter based on your model logic
    terms = Warehouse.objects.filter(status__in=[0, 1]).order_by("warehouse_name")
    locations_qs = OrganizationInventoryLocation.objects.all()
    loc_map = {str(loc.pk): loc.name for loc in locations_qs}
    if search_query:
        terms = terms.filter(warehouse_name__icontains=search_query)
    warehouse_locations = OrganizationInventoryLocation.objects.values(
        "id",
        "name",
        "parent_location_id",
        "attention"
    )
    # --- Pagination ---
    # Tabulator typically sends 'size' for records per page
    page_size = request.GET.get("size", 10)
    page_number = request.GET.get("page", 1)

    paginator = Paginator(terms, page_size)
    page_obj = paginator.get_page(page_number)

    # --- Serialization ---
    data = []
    for w in page_obj:
        loc_key = str(w.location) if w.location else ""
        loc_name = loc_map.get(loc_key, "")
        if OrganizationInventoryLocation.objects.filter(id=w.location).exists():
            loc_name = OrganizationInventoryLocation.objects.filter(id=w.location).first().name

        data.append({
            "warehouse_id": w.warehouse_id,
            "warehouse_name": w.warehouse_name,
            "location_name": loc_name,
            "location":w.location ,
            "status": w.status,  # Returns 'ACTIVE' or 'INACTIVE'
            "is_default": w.is_default,
            "created_at": w.created_at.strftime("%d/%m/%Y %I:%M %p") if w.created_at else ""
        })

    return JsonResponse({
        "status": True,
        "data": data,"warehouse_locations": list(warehouse_locations),
        "last_page": paginator.num_pages,
        "total_record": paginator.count
    })

@api_view(["POST"])
def add_new_inventory_locations(request):
    data = request.data

    warehouse_name = data.get("warehouse_name")
    location = data.get("location")
    status = data.get("status")
    is_default = data.get("is_default")
    try:
        if warehouse_name and location:
            inv_loc = Warehouse()
            inv_loc.warehouse_name = warehouse_name
            inv_loc.location = location
            inv_loc.status = status
            inv_loc.is_default = is_default
            inv_loc.created_by = request.user.id
            inv_loc.save()
        else:
            return JsonResponse({"status": False, "message": "Required fields are missing."})
        return JsonResponse({"status": True, "message": "Inventory location created."})
    except Exception as e:
        return JsonResponse({"status": False, "message": "Error while creating warehouse", "Err":str(e)})


@api_view(["DELETE"])
def delete_inventory_location(request, warehouse_id):
    try:
        inv_loc = Warehouse.objects.filter(warehouse_id=warehouse_id).first()
        inv_loc.status = -1
        inv_loc.save(update_fields=["status"])
        return JsonResponse({"status": True, "message": "Inventory location removed"})
    except Exception as ex:
        return JsonResponse({"status":False, "message":"Error deleting", "err":str(ex)})

@api_view(["PUT"])
def save_inventory_location(request, warehouse_id):
    data = request.data

    warehouse_name = data.get("warehouse_name")
    location = data.get("location")
    status = data.get("status")
    is_default = data.get("is_default")
    try:
        if warehouse_name and location:
            inv_loc = get_object_or_404(Warehouse, warehouse_id=warehouse_id)

            inv_loc.warehouse_name = warehouse_name
            inv_loc.location = location
            inv_loc.status = status
            inv_loc.is_default = is_default
            inv_loc.save()
        else:
            return JsonResponse({"status": False, "message": "Required fields are missing."})
        return JsonResponse({"status": True, "message": "Inventory location updated."})
    except Exception as e:
        return JsonResponse({"status": False, "message": "Error while creating Inventory location", "Err": str(e)})


@api_view(["GET"])
def all_sb_api_listing(request):
    warehouse_locations = list(OrganizationInventoryLocation.objects.all())
    w_locs = []
    for loc in warehouse_locations:
        w_locs.append({
            "id": loc.id,
            "name": loc.name,
            "parent_location_id": loc.parent_location_id,
            "attention": loc.attention,
            "address_line1": loc.address_line1,
            "address_line2": loc.address_line2,
            "city": loc.city,
            "zip_code": loc.zip_code,
            "country_name": loc.country_name,  # plain text
            "country_id": Country.objects.get(name=loc.country_name).id if loc.country_name else None,  # plain text
            "state_name": loc.state_name,
            "state_id": State.objects.get(name=loc.state_name).id if loc.state_name else None,
            "phone": loc.phone,
            "fax": loc.fax,
            "website_url": loc.website_url,
        })

    return JsonResponse({"status": True, "data": w_locs})


from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Concat

import json
@login_required
def delete_locations(request):
    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid request"})

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": False, "message": "Invalid JSON"})

    ids = data.get("ids", [])
    if not ids:
        return JsonResponse({"status": False, "message": "No warehouse selected"})

    terms = Warehouse.objects.filter(warehouse_id__in=ids)

    if not terms.exists():
        return JsonResponse({"status": False, "message": "No records found"})

    # ✅ collect all primary warehouses in the selection
    primary_terms = [t for t in terms if t.is_default == 1]

    if primary_terms:
        names = ", ".join([t.warehouse_name for t in primary_terms])
        return JsonResponse({
            "status": False,
            "message": f"Selected list contains default warehouse ({names}). Remove it from selection and try again."
        })

    try:
        with transaction.atomic():
            terms.update(
                warehouse_name=Concat(Value("ARCHIVED_"), F("warehouse_name")),
                status="ARCHIVED",
                created_by=request.user.id
            )
        return JsonResponse({"status": True, "message": "Removed", "deleted": terms.count()})
    except Exception as ex:
        return JsonResponse({"status": False, "message": str(ex)})

