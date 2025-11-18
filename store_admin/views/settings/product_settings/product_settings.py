from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from store_admin.models.payment_terms_model import PaymentTerm
from django.contrib.auth.decorators import login_required

from store_admin.models.setting_model import Manufacturer, Brand


@login_required
def manage_product_categories(request):
    return
    if request.method == "POST":
        action = request.POST.get("action")

        # --- Create ---
        if action == "create":
            PaymentTerm.objects.create(
                name=request.POST.get("name"),
                type=request.POST.get("type"),
                frequency=request.POST.get("frequency"),
                status=request.POST.get("status"),
            )
            messages.success(request, "Payment Term created successfully.")
            return redirect("payment_terms")

        # --- Edit ---
        elif action == "edit":
            term = get_object_or_404(PaymentTerm, id=request.POST.get("term_id"))
            term.name = request.POST.get("name")
            term.frequency = request.POST.get("frequency")
            term.type = request.POST.get("type")
            term.status = request.POST.get("status")
            term.save()
            messages.success(request, f"Payment Term '{term.name}' updated successfully.")
            return redirect("payment_terms")

        # --- Delete ---
        elif action == "delete":
            term = get_object_or_404(PaymentTerm, id=request.POST.get("term_id"))
            term.delete()
            messages.warning(request, f"Payment Term '{term.name}' deleted successfully.")
            return redirect("payment_terms")

    # --- Get / Paginated List ---
    search_query = request.GET.get("q", "").strip()
    terms = PaymentTerm.objects.all().order_by("name")

    if search_query:
        terms = terms.filter(name__icontains=search_query)

    paginator = Paginator(terms, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "sbadmin/pages/product/settings/manage_product_categories.html",
        {"terms": page_obj, "page_obj": page_obj, "search_query": search_query},
    )

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