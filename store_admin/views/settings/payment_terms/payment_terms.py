from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from rest_framework.decorators import api_view

from store_admin.models.payment_terms_model import PaymentTerm
from django.contrib.auth.decorators import login_required

@api_view(["GET"])
def get_all_payment_terms(request):
    # 1. Get query parameters
    search_query = request.GET.get("q", "").strip()
    page_number = request.GET.get("page", 1)
    page_size = request.GET.get("size", 10)  # Tabulator default

    # 2. Filtering Logic
    terms_queryset = PaymentTerm.objects.all().order_by("name")

    if search_query:
        terms_queryset = terms_queryset.filter(name__icontains=search_query)

    # 3. Pagination
    paginator = Paginator(terms_queryset, page_size)
    page_obj = paginator.get_page(page_number)

    # 4. Manual Serialization
    # This converts the database objects into a list of dictionaries
    data_list = []
    for term in page_obj:
        data_list.append({
            "id": term.id,
            "type": getattr(term, 'type', 'Prepaid'),  # Handles 'Type' from your UI
            "name": term.name,
            "frequency": term.frequency,
            "status": term.status,  # 'Active' or 'Inactive'
        })

    # 5. Return Response optimized for your React Tabulator
    return JsonResponse({
        "status": True,
        "data": data_list,
        "last_page": paginator.num_pages,
        "total_record": paginator.count
    })

@api_view(["PUT"])
def update_payment_terms(request, payment_term_id):
    term = get_object_or_404(PaymentTerm, id=payment_term_id)
    data = request.data
    term.name = data.get("name")
    term.frequency = data.get("frequency")
    term.type = data.get("type")
    term.status = data.get("status")
    term.save()
    return JsonResponse({
        "status": True,
        "message": "Payment Term updated successfully.",
    })

#delete_payment_term
@api_view(["DELETE"])
def delete_payment_term(request, payment_term_id):

    term = PaymentTerm.objects.filter(id=payment_term_id).delete()

    return JsonResponse({
        "status": True,
        "message": "Payment Term removed successfully.",
    })

@api_view(["POST"])
def create_payment_term(request):
    term = PaymentTerm()
    data = request.data
    term.name = data.get("name")
    term.frequency = data.get("frequency")
    term.type = data.get("type")
    term.status = data.get("status")
    term.save()
    return JsonResponse({
        "status": True,
        "message": "Payment Term created successfully.",
    })

