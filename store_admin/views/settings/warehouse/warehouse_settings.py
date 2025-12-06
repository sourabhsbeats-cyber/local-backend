from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from store_admin.models.payment_terms_model import PaymentTerm
from django.contrib.auth.decorators import login_required

from store_admin.models.product_model import ProductStaticAttributes
from store_admin.models.setting_model import Manufacturer, Brand, Category, AttributeDefinition
from store_admin.models.warehouse_setting_model import Warehouse
from django.db import transaction

@login_required
def all_listing(request):
    if request.method == "POST":
        action = request.POST.get("action")

        # --- Create ---
        if action == "create":
            name = request.POST.get("warehouse_name", "").strip()
            location = request.POST.get("location")
            status = request.POST.get("status")

            if not name:
                return JsonResponse({"status": False, "message": "Name required"})
            if not location:
                return JsonResponse({"status": False, "message": "Location required"})

            if Warehouse.objects.filter(warehouse_name__iexact=name).exists():
                return JsonResponse({"status": False, "message": "Warehouse name already exists"})
            try:
                Warehouse.objects.create(
                    warehouse_name=name,
                    location=location,
                    status=status,
                    created_by=request.user.id,
                )
                return JsonResponse({"status":True, "message":"Warehouse created successfully."})
            except Exception as ex:
                return JsonResponse({"status": False, "message": str(ex)})

        # --- Edit ---
        elif action == "edit":
            name = request.POST.get("warehouse_name", "").strip()
            location = request.POST.get("location")
            status = request.POST.get("status")
            warehouse_id = request.POST.get("warehouse_id")
            is_default = request.POST.get("is_default")

            if not name:
                return JsonResponse({"status": False, "message": "Name required"})
            if not location:
                return JsonResponse({"status": False, "message": "Location required"})

            term = Warehouse.objects.filter(warehouse_id=warehouse_id).first()
            if not term:
                return JsonResponse({"status": False, "message": "No record found"})

            #  If new primary, remove primary from all others first
            if is_default == "1":
                Warehouse.objects.update(is_default=0)  # → makes all warehouses NON-primary

            try:
                with transaction.atomic():
                    term.warehouse_name = name
                    term.location = location
                    term.status = status
                    term.is_default = 1 if is_default == "1" else 0  # ✅ now this will be the only primary
                    term.save()

                return JsonResponse({"status": True, "message": "Updated"})
            except Exception as ex:
                return JsonResponse({"status": False, "message": str(ex)})
        # --- Delete ---
        elif action == "delete":
            warehouse_id = request.POST.get("warehouse_id")
            term = Warehouse.objects.filter(warehouse_id=warehouse_id).first()
            if term.is_default == 1:
                return JsonResponse({"status": False, "message": "Default warehouse cannot be removed"})
            if not term:
                return JsonResponse({"status": False, "message": "No record found"})

            try:
                with transaction.atomic():
                    term.warehouse_name = "ARCHIVED_"+term.warehouse_name
                    term.status = "ARCHIVED"  # archive instead of deleting
                    term.save()
                return JsonResponse({"status": True, "message": "Removed"})
            except Exception as ex:
                return JsonResponse({"status": False, "message": str(ex)})


    # --- Get / Paginated List ---
    search_query = request.GET.get("q", "").strip()
    terms = Warehouse.objects.filter(status__in=["ACTIVE", "INACTIVE"]).order_by("warehouse_name")

    if search_query:
        terms = terms.filter(warehouse_name__icontains=search_query.strip())

    paginator = Paginator(terms, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "sbadmin/pages/settings/warehouse/manage_warehouses.html",
        {"terms": page_obj, "page_obj": page_obj, "search_query": search_query},
    )

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

