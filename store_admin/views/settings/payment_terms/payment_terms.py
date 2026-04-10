from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from rest_framework.decorators import api_view

from store_admin.models.payment_terms_model import PaymentTerm
from django.contrib.auth.decorators import login_required


def validate_payment_term_payload(data, payment_term_id=None):
    errors = {}
    name = (data.get("name") or "").strip()
    frequency = data.get("frequency")
    payment_type = data.get("type")
    status = (data.get("status") or "").strip()

    if not name:
        errors["name"] = "Name is required."

    if frequency in [None, ""]:
        errors["frequency"] = "Frequency is required."
    else:
        try:
            frequency = int(frequency)
            if frequency <= 0:
                errors["frequency"] = "Frequency must be a positive integer."
        except (TypeError, ValueError):
            errors["frequency"] = "Frequency must be a valid integer."

    if payment_type in [None, ""]:
        errors["type"] = "Type is required."
    else:
        try:
            payment_type = int(payment_type)
            if payment_type not in dict(PaymentTerm.PAYMENT_TYPES):
                errors["type"] = "Invalid payment type."
        except (TypeError, ValueError):
            errors["type"] = "Type must be a valid integer."

    if not status:
        errors["status"] = "Status is required."
    elif status not in dict(PaymentTerm.STATUS_CHOICES):
        errors["status"] = "Status must be Active or Inactive."

    if name:
        duplicate_qs = PaymentTerm.objects.filter(name__iexact=name)
        if payment_term_id:
            duplicate_qs = duplicate_qs.exclude(id=payment_term_id)
        if duplicate_qs.exists():
            errors["name"] = "Payment Term with this name already exists."

    return errors, {
        "name": name,
        "frequency": frequency,
        "type": payment_type,
        "status": status,
    }


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
    errors, cleaned = validate_payment_term_payload(data, payment_term_id=payment_term_id)
    if errors:
        return JsonResponse({
            "status": False,
            "message": "Validation failed.",
            "errors": errors,
        }, status=400)

    term.name = cleaned["name"]
    term.frequency = cleaned["frequency"]
    term.type = cleaned["type"]
    term.status = cleaned["status"]
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
    data = request.data
    errors, cleaned = validate_payment_term_payload(data)
    if errors:
        return JsonResponse({
            "status": False,
            "message": "Validation failed.",
            "errors": errors,
        }, status=400)

    term = PaymentTerm(
        name=cleaned["name"],
        frequency=cleaned["frequency"],
        type=cleaned["type"],
        status=cleaned["status"],
    )
    term.save()
    return JsonResponse({
        "status": True,
        "message": "Payment Term created successfully.",
    })

