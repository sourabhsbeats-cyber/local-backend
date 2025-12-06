from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from store_admin.models.payment_terms_model import PaymentTerm
from django.contrib.auth.decorators import login_required

from store_admin.models.product_model import ProductStaticAttributes
from store_admin.models.setting_model import Manufacturer, Brand, Category, AttributeDefinition, UnitOfMeasurements


@login_required
def manage_product_categories(request):

    if request.method == "POST":
        action = request.POST.get("action")

        # --- Create ---
        if action == "create":
            Category.objects.create(
                name = request.POST.get("name"),
                is_primary = 0 if request.POST.get("is_primary") else 1,
                primary_category_id = request.POST.get("primary_category_id") or None,
                status = request.POST.get("status"),
                created_by =    request.user.id
            )
            messages.success(request, "Payment Term created successfully.")
            return redirect("manage_product_categories")

        # --- Edit ---
        elif action == "edit":
            term = get_object_or_404(Category, category_id=request.POST.get("category_id"))

            term.name = request.POST.get("name")
            is_secondary = request.POST.get("is_secondary")
            term.is_primary = 0 if is_secondary else 1
            term.primary_category_id = request.POST.get("primary_category_id") or None
            term.status = int(request.POST.get("status"))
            term.save()
            messages.success(request, f"Category '{term.name}' updated successfully.")
            return redirect("manage_product_categories")

        # --- Delete ---
        elif action == "delete":
            term = get_object_or_404(Category, category_id=request.POST.get("category_id"))
            term.delete()
            messages.warning(request, f"Category '{term.name}' deleted successfully.")
            return redirect("manage_product_categories")

    # --- Get / Paginated List ---
    search_query = request.GET.get("q", "").strip()
    terms = Category.objects.all().order_by("name")

    if search_query:
        terms = terms.filter(name__icontains=search_query)

    paginator = Paginator(terms, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    main_categories = Category.objects.filter(is_primary=1, status=True).order_by("name")
    return render(
        request,
        "sbadmin/pages/product/settings/manage_product_categories.html",
        {"main_categories":main_categories, "terms": page_obj, "page_obj": page_obj, "search_query": search_query},
    )



@login_required
def add_new_brand(request):
    if request.method == "POST":
        brand = Brand.objects.create(
            name=request.POST.get("brand_name"),
            status=1,
            created_by=request.user.id
        )
        return JsonResponse({"status":True, "data": brand.brand_id})
    return JsonResponse({"status": False, "error": "Invalid request"})

@login_required
def add_new_manufacturer(request):
    if request.method == "POST":
        manu = Manufacturer.objects.create(
            name=request.POST.get("manufacturer_name"),
            status=1,
            created_by=request.user.id
        )
        return JsonResponse({"status":True, "data": manu.manufacturer_id})  # return created ID

    return JsonResponse({"status": False, "error": "Invalid request"})


@login_required
def manage_product_attributes(request):
    if request.method == "POST":
        action = request.POST.get("action")
        #print(action)
        #return JsonResponse({"status": True, "message": action})
        # --- Create ---
        if action == "create":
            try:
                if AttributeDefinition.objects.filter(attribute_name__icontains=request.POST.get("attribute_name")).exists():
                    return JsonResponse({"status": False, "message": "Attribute name already exists"})

                AttributeDefinition.objects.create(
                    attribute_name=request.POST.get("attribute_name"),
                    attribute_type=request.POST.get("attribute_type"),
                    default_value=request.POST.get("default_value"),
                    option_list=request.POST.get("option_list", None),
                    created_by=request.user.id
                )
            except Exception as e:
                print(e)
                return JsonResponse({"status": False, "message": "Error creating"})
            return JsonResponse({"status":True, "message":"Attribute created successfully." })

        # --- Edit ---
        elif action == "edit":
            term = get_object_or_404(AttributeDefinition, attribute_id=request.POST.get("attribute_id"))
            if AttributeDefinition.objects.filter(
                    attribute_name__icontains=request.POST.get("attribute_name", "").strip()
            ).exclude(
                attribute_id=request.POST.get("attribute_id")
            ).exists():
                return JsonResponse({"status": False, "message": "Attribute name already exists"})

            term.attribute_name = request.POST.get("attribute_name")
            term.attribute_type = request.POST.get("attribute_type")
            term.default_value = request.POST.get("default_value")
            term.option_list = request.POST.get("option_list")
            term.save()
            return JsonResponse({"status": True, "message": f"Attribute '{term.attribute_name}' updated successfully."})

        # --- Delete ---
        elif action == "delete":
            term = AttributeDefinition.objects.filter(attribute_id=request.POST.get("attribute_id")).delete()
            return JsonResponse({"status": True, "message": f"Attribute deleted successfully."})

    # --- Get / Paginated List ---
    search_query = request.GET.get("q", "").strip()
    terms = AttributeDefinition.objects.all().order_by("attribute_name")
    if search_query:
        terms = terms.filter(attribute_name__icontains=search_query)

    paginator = Paginator(terms, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "sbadmin/pages/settings/custom_attributes/attribute_listing.html",
        {"terms": page_obj, "page_obj": page_obj, "search_query": search_query},
    )

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


@login_required
def manage_product_brands(request):
    if request.method == "POST":
        action = request.POST.get("action")

        # --- Create ---
        if action == "create":
            Brand.objects.create(
                name=request.POST.get("name"),
                status=request.POST.get("status"),
                created_by=request.user.id
            )
            messages.success(request, "Brand created successfully.")
            return redirect("manage_product_brands")

        # --- Edit ---
        elif action == "edit":
            term = get_object_or_404(Brand, brand_id=request.POST.get("brand_id"))
            term.name = request.POST.get("name")
            term.status = request.POST.get("status")
            term.save()
            messages.success(request, f"Brand '{term.name}' updated successfully.")
            return redirect("manage_product_brands")

        # --- Delete ---
        elif action == "delete":
            term = get_object_or_404(Brand, brand_id=request.POST.get("brand_id"))
            term.delete()
            messages.warning(request, f"Payment Term '{term.name}' deleted successfully.")
            return redirect("manage_product_brands")

    # --- Get / Paginated List ---
    search_query = request.GET.get("q", "").strip()
    terms = Brand.objects.all().order_by("name")

    if search_query:
        terms = terms.filter(name__icontains=search_query)

    paginator = Paginator(terms, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "sbadmin/pages/product/settings/manage_product_brands.html",
        {"terms": page_obj, "page_obj": page_obj, "search_query": search_query},
    )

@login_required
def manage_product_manufacturers(request):
    if request.method == "POST":
        action = request.POST.get("action")

        # --- Create ---
        if action == "create":
            Manufacturer.objects.create(
                name=request.POST.get("name"),
                status=request.POST.get("status"),
                created_by=request.user.id
            )
            messages.success(request, "Manufacturer created successfully.")
            return redirect("manage_product_manufacturers")

        # --- Edit ---
        elif action == "edit":
            term = get_object_or_404(Manufacturer, manufacturer_id=request.POST.get("manufacturer_id"))
            term.name = request.POST.get("name")
            term.status = request.POST.get("status")
            term.save()
            messages.success(request, f"Manufacturer '{term.name}' updated successfully.")
            return redirect("manage_product_manufacturers")

        # --- Delete ---
        elif action == "delete":
            term = get_object_or_404(Manufacturer, manufacturer_id=request.POST.get("manufacturer_id"))
            term.delete()
            messages.warning(request, f"Manufacturer '{term.name}' deleted successfully.")
            return redirect("manage_product_manufacturers")

    # --- Get / Paginated List ---
    search_query = request.GET.get("q", "").strip()
    terms = Manufacturer.objects.all().order_by("name")

    if search_query:
        terms = terms.filter(name__icontains=search_query)

    paginator = Paginator(terms, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "sbadmin/pages/product/settings/manage_product_manufacturers.html",
        {"terms": page_obj, "page_obj": page_obj, "search_query": search_query},
    )

@login_required
def manage_unit_of_measures(request):
    if request.method == "POST":
        action = request.POST.get("action")

        # --- Create ---
        if action == "create":
            UnitOfMeasurements.objects.create(
                name=request.POST.get("name"),
                status=request.POST.get("status"),
                created_by=request.user.id
            )
            messages.success(request, "Record created successfully.")
            return redirect("manage_unit_of_measures")

        # --- Edit ---
        elif action == "edit":
            term = get_object_or_404(UnitOfMeasurements, measurement_id=request.POST.get("measurement_id"))

            term.name = request.POST.get("name")
            term.status = request.POST.get("status")
            term.save()
            messages.success(request, f"Record '{term.name}' updated successfully.")
            return redirect("manage_unit_of_measures")

        # --- Delete ---
        elif action == "delete":
            term = get_object_or_404(UnitOfMeasurements, measurement_id=request.POST.get("measurement_id"))
            term.delete()
            messages.warning(request, f"Record '{term.name}' deleted successfully.")
            return redirect("manage_unit_of_measures")

    # --- Get / Paginated List ---
    search_query = request.GET.get("q", "").strip()
    terms = UnitOfMeasurements.objects.all().order_by("name")

    if search_query:
        terms = terms.filter(name__icontains=search_query)

    paginator = Paginator(terms, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "sbadmin/pages/product/settings/manage_product_units.html",
        {"terms": page_obj, "page_obj": page_obj, "search_query": search_query},
    )