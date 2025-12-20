from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from store_admin.models.geo_models import Country, State
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse

from store_admin.models.setting_model import ShippingProviders
from store_admin.templates.sbadmin.pages.settings.shipping_providers.add.add_new_shipping_form import \
    ShippingProviderForm

# Create your views here.
@login_required
def listing(request):
    search_query = request.GET.get("q", "").strip()
    providers = ShippingProviders.objects.filter(is_archived=0).all().order_by("carrier_name")
    if search_query:
        providers = providers.filter(
            Q(carrier_name__icontains=search_query)
            | Q(carrier_code__icontains=search_query)
            | Q(class_code__icontains=search_query)
        )

    paginator = Paginator(providers, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "sbadmin/pages/settings/shipping_providers/listings/listing.html",
        {
            "providers": page_obj,
            "page_obj": page_obj,
            "search_query": search_query,
        },
    )

# Create your views here.
@login_required
def create(request):
    return render(
        request,
        "sbadmin/pages/settings/shipping_providers/add/add_new_shipping_carrier.html",
        { 'form' : ShippingProviderForm()},
    )

@login_required
def edit_form(request, carrier_id):
    provider = get_object_or_404(ShippingProviders, carrier_id=carrier_id)

    if request.method == "POST":
        # CRITICAL: instance=provider tells the form "I am editing THIS row"
        form = ShippingProviderForm(request.POST, instance=provider)
        if form.is_valid():
            form.save()
            messages.success(request, f"{provider.carrier_name} updated successfully!")
            return redirect('manage_shipping_providers_listing')
    else:
        form = ShippingProviderForm(instance=provider)

    return render(request, "sbadmin/pages/settings/shipping_providers/add/add_new_shipping_carrier.html", {'form': form, 'is_edit': True})

@login_required
def save_shipping_details(request):

    if request.method == "POST":
        # Bind the form to the POST data
        form = ShippingProviderForm(request.POST)

        if form.is_valid():
            # Save the new shipping provider to MySQL
            shipping_instance = form.save(commit=False)
            shipping_instance.created_by = request.user.id
            shipping_instance.save()
            # Add a success message
            messages.success(request, "Shipping carrier added successfully!")
            return redirect('manage_shipping_providers_listing')
        else:
            # If the form is invalid, it will fall through to the render at the bottom
            # and show validation errors in the template
            messages.error(request, "Please correct the errors below.")
    else:
        # Provide a blank form for GET requests
        form = ShippingProviderForm()

    return render(
        request,
        "sbadmin/pages/settings/shipping_providers/add/add_new_shipping_carrier.html",
        {'form': form},
    )

@login_required
def manage_shipping_details(request, carrier_id):
    """
    Edit a country's details and manage its states.
    """
    provider = get_object_or_404(ShippingProviders, carrier_id=carrier_id)

    # Handle Add/Edit/Delete for States
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "delete_shipping_carrier":
            name = provider.carrier_name
            provider.is_archived = 1
            provider.save(update_fields=["is_archived"])
            messages.warning(request, f"Shipping Provider '{name}' has been deleted successfully.")
            return JsonResponse({"status":True, "message":"Shipping Provider '{name}' has been deleted successfully."})

        # Update country details
        elif action == "toggle_status":
            name = provider.carrier_name
            provider.status = 0 if provider.status == 1 else 1
            provider.save(update_fields=["status"])
            status_text = "activated" if provider.status == 1 else "deactivated"
            return JsonResponse({
                'status': 'success',
                'message': f"Shipping Provider '{name}' has been {status_text} successfully."
            })

    return redirect("manage_shipping_providers_listing")
