from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from rest_framework.decorators import api_view

from store_admin.models.geo_models import Country, State
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse

# Create your views here.
@api_view(["GET"])
def api_all_listings(request):
    # 1. Get Pagination Parameters from Tabulator
    page_number = request.GET.get("page", 1)
    page_size = request.GET.get("size", 10) # 'size' is the default Tabulator param
    search_query = request.GET.get("q", "").strip()

    # 2. Base Query
    countries = Country.objects.all().order_by("name")
    state_counts = dict(
        State.objects.values_list("country_id")
        .annotate(count=Count("id"))
    )
    # 3. Filtering
    if search_query:
        countries = countries.filter(Q(name__icontains=search_query))

    # 4. Django Paginator
    paginator = Paginator(countries, page_size)
    page_obj = paginator.get_page(page_number)

    # 5. Serialize Data
    data_list = []
    for c in page_obj:
        data_list.append({
            "id": c.id,
            "name": c.name,
            "iso2": c.iso2,
            "iso3": c.iso3,
            "num_states": state_counts.get(c.id, 0) # Or your optimized annotation
        })

    # 6. Response matching your JSON structure
    return JsonResponse({
        "status": True,
        "data": data_list,
        "last_page": paginator.num_pages,
        "total_record": paginator.count
    })


@api_view(["GET"])
def get_country_details(request, country_id):
    # 1. Fetch the Country or return 404
    country = get_object_or_404(Country, id=country_id)

    # 2. Setup States filtering
    search_query = request.GET.get("q", "").strip()
    page_number = request.GET.get("page", 1)
    page_size = request.GET.get("size", 10)

    states_queryset = State.objects.filter(country=country).order_by("name")

    if search_query:
        states_queryset = states_queryset.filter(
            Q(name__icontains=search_query) |
            Q(iso2__icontains=search_query)
        )

    # 3. Paginate States
    paginator = Paginator(states_queryset, page_size)
    page_obj = paginator.get_page(page_number)

    # 4. Serialize Country Data
    country_data = {
        "id": country.id,
        "name": country.name,
        "iso2": country.iso2,
        "iso3": country.iso3,
        "currency": getattr(country, 'currency', ''),
        "currency_name": getattr(country, 'currency_name', ''),
        "symbol": getattr(country, 'currency_symbol', ''),
    }

    # 5. Serialize Paginated States Data
    states_list = []
    for s in page_obj:
        states_list.append({
            "id": s.id,
            "name": s.name,
            "iso2": s.iso2,
        })
    # 6. Return Response
    return JsonResponse({
        "status": True,
        "country": country_data,
        "states": {
            "data": states_list,
            "last_page": paginator.num_pages,
            "total_record": paginator.count,
            "current_page": page_obj.number
        }
    })

@api_view(["PUT"])
def update_country_details(request, country_id):
    country = get_object_or_404(Country, id=country_id)
    data = request.data

    country.name = data.get("name")
    country.iso2 = data.get("iso2")
    country.iso3 = data.get("iso3")
    country.currency = data.get("currency")
    country.currency_name = data.get("currency_name")
    country.currency_symbol = data.get("symbol")
    country.save()

    return JsonResponse({"status": True, "message": "Country details updated successfully."})

@api_view(["PUT"])
def update_state_details(request, state_id):
    state = get_object_or_404(State, id=state_id)
    data = request.data
    state.name = data.get("name")
    state.iso2 = data.get("iso2")
    state.save()
    return JsonResponse({"status": True, "message": f"State '{state.name}' updated successfully."})

@api_view(["DELETE"])
def delete_state_details(request, state_id):
    state = get_object_or_404(State, id=state_id)
    state.delete()
    return JsonResponse({"status": True, "message": f"State '{state.name}' deleted successfully."})


@api_view(["POST"])
def create_state_details(request, country_id):
    data = request.data
    country = Country.objects.get(id=country_id)
    State.objects.create(
        name=data.get("name"),
        iso2=data.get("iso2"),
        country=country,
    )
    return JsonResponse({"status": True,
                         "message": f"State '{data.get('name')}' added successfully."})

#country select 2 js json format render
@api_view(["GET"])
def get_countries(request):
    q = request.GET.get("q", "").strip()

    countries = Country.objects.order_by("name")

    if q:
        countries = countries.filter(name__icontains=q)

    data = [
        {"id": c.id, "text": c.name, "currency": c.currency, "currency_name": c.currency_name}
        for c in countries
    ]

    return JsonResponse({"results": data})

#state select 2 js json format render
@api_view(["GET"])
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


@api_view(["GET"])
def get_states(request, country_id):
    states = State.objects.filter(country_id=country_id).values("id", "name")
    return JsonResponse({"states": list(states)})
