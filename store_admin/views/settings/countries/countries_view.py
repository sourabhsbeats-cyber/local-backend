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

# Create your views here.
@login_required
def all_listings(request):
    search_query = request.GET.get("q", "").strip()

    countries = Country.objects.all().order_by("name")

    if search_query:
        countries = countries.filter(
            Q(name__icontains=search_query)
            | Q(iso2__icontains=search_query)
            | Q(iso3__icontains=search_query)
        )

    paginator = Paginator(countries, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    state_counts = dict(
        State.objects.values_list("country_id")
        .annotate(count=Count("id"))
        .values_list("country_id", "count")
    )

    return render(
        request,
        "sbadmin/pages/settings/countries/listing.html",
        {
            "countries": page_obj,
            "page_obj": page_obj,
            "search_query": search_query,
            "state_counts": state_counts,
        },
    )

#country select 2 js json format render
@login_required
def get_countries(request):
    q = request.GET.get("q", "").strip()

    countries = Country.objects.order_by("name")

    if q:
        countries = countries.filter(name__icontains=q)

    countries = countries[:20]  # limit 20 results

    data = [
        {"id": c.id, "text": c.name}
        for c in countries
    ]

    return JsonResponse({"results": data})
#state select 2 js json format render
@login_required
def get_states_by_country(request):
    country_id = request.GET.get("country_id")
    q = request.GET.get("q", "").strip()

    if not country_id:
        return JsonResponse({"results": []})

    # base queryset
    states = State.objects.filter(country_id=country_id)

    # search filter
    if q:
        states = states.filter(name__icontains=q)

    # limit results for performance
    states = states.order_by("name")[:20]

    # Select2 format → id + text
    results = [{"id": s.id, "text": s.name} for s in states]

    return JsonResponse({"results": results})






@login_required
def get_states(request, country_id):
    states = State.objects.filter(country_id=country_id).values("id", "name")
    return JsonResponse({"states": list(states)})

@login_required
def edit_country(request, country_id):
    """
    Edit a country's details and manage its states.
    """
    country = get_object_or_404(Country, id=country_id)

    # Handle Add/Edit/Delete for States
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "delete_country":
            name = country.name
            country.delete()
            messages.warning(request, f"Country '{name}' has been deleted successfully.")
            return redirect("all_countries")

        # Add new state
        if action == "add_state":
            State.objects.create(
                name=request.POST.get("name"),
                iso2=request.POST.get("iso2"),
                country=country
            )
            messages.success(request, f"State '{request.POST.get('name')}' added successfully.")
            return redirect("edit_country", country_id=country.id)

        # Edit existing state
        elif action == "edit_state":
            state_id = request.POST.get("state_id")
            state = get_object_or_404(State, id=state_id, country=country)
            state.name = request.POST.get("name")
            state.iso2 = request.POST.get("iso2")
            state.save()
            messages.success(request, f"State '{state.name}' updated successfully.")
            return redirect("edit_country", country_id=country.id)

        # Delete state
        elif action == "delete_state":
            state_id = request.POST.get("state_id")
            state = get_object_or_404(State, id=state_id, country=country)
            state.delete()
            messages.warning(request, f"State '{state.name}' deleted successfully.")
            return redirect("edit_country", country_id=country.id)

        # Update country details
        elif action == "update_country":
            country.name = request.POST.get("name")
            country.iso2 = request.POST.get("iso2")
            country.iso3 = request.POST.get("iso3")
            country.currency = request.POST.get("currency")
            country.currency_name = request.POST.get("currency_name")
            country.currency_symbol = request.POST.get("currency_symbol")
            country.phonecode = request.POST.get("phonecode")
            country.capital = request.POST.get("capital")
            country.region = request.POST.get("region")
            country.subregion = request.POST.get("subregion")
            country.save()
            messages.success(request, "Country details updated successfully.")
            return redirect("edit_country", country_id=country.id)

    # Search and paginate states
    search_query = request.GET.get("q", "").strip()
    states = State.objects.filter(country=country).order_by("name")

    if search_query:
        states = states.filter(
            Q(name__icontains=search_query)
            | Q(iso2__icontains=search_query)
            | Q(fips_code__icontains=search_query)
        )

    paginator = Paginator(states, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "sbadmin/pages/settings/countries/edit_country.html",
        {
            "country": country,
            "states": page_obj,
            "page_obj": page_obj,
            "search_query": search_query,
        },
    )

@login_required
def state_list(request, country_id):
    """
    Shows a paginated list of states belonging to a given country.
    """
    search_query = request.GET.get("q", "").strip()
    country = get_object_or_404(Country, id=country_id)

    # Filter states for the selected country
    states = State.objects.filter(country=country).order_by("name")

    # Optional: Add search filter
    if search_query:
        states = states.filter(
            Q(name__icontains=search_query)
            | Q(iso2__icontains=search_query)
            | Q(fips_code__icontains=search_query)
        )

    # Paginate results (10 per page)
    paginator = Paginator(states, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "country": country,
        "states": page_obj,
        "page_obj": page_obj,
        "search_query": search_query,
    }

    return render(request, "sbadmin/pages/settings/countries/states.html", context)