from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from rest_framework.decorators import api_view
from django.core.exceptions import ValidationError
from datetime import date
import calendar

from store_admin.models.payment_terms_model import PaymentTerm
from django.contrib.auth.decorators import login_required


def _days_until(year, month, day):
    today = date.today()
    target = date(year, month, day)
    return (target - today).days


def _dynamic_frequency_from_option(option_value):
    if option_value is None:
        return None
    normalized = str(option_value).strip().lower()
    today = date.today()

    # Example: if today is 15-Apr, this becomes 14-May (29 days)
    if normalized == "14th of next month":
        next_year = today.year + (1 if today.month == 12 else 0)
        next_month = 1 if today.month == 12 else today.month + 1
        return _days_until(next_year, next_month, 14)

    if normalized == "last day of next month":
        next_year = today.year + (1 if today.month == 12 else 0)
        next_month = 1 if today.month == 12 else today.month + 1
        last_day = calendar.monthrange(next_year, next_month)[1]
        return _days_until(next_year, next_month, last_day)

    if normalized == "last day of next to next month":
        month_after_next = today.month + 2
        target_year = today.year + ((month_after_next - 1) // 12)
        target_month = ((month_after_next - 1) % 12) + 1
        last_day = calendar.monthrange(target_year, target_month)[1]
        return _days_until(target_year, target_month, last_day)

    if normalized == "frequency":
        return 0

    return None


def validate_payment_term_payload(data, payment_term_id=None):
    errors = {}
    name = (data.get("name") or "").strip()
    frequency = data.get("frequency")
    payment_type = data.get("type")
    raw_status = data.get("status")
    status = str(raw_status).strip() if raw_status is not None else ""

    if not name:
        errors["name"] = "Name is required."

    if payment_type in [None, ""]:
        errors["type"] = "Type is required."
    else:
        try:
            payment_type = int(payment_type)
            if payment_type not in dict(PaymentTerm.PAYMENT_TYPES):
                errors["type"] = "Invalid payment type."
        except (TypeError, ValueError):
            errors["type"] = "Type must be a valid integer."

    if frequency in [None, ""]:
        errors["frequency"] = "Frequency is required."
    else:
        # Accept both numeric frequency and legacy term labels from UI.
        dynamic_frequency = _dynamic_frequency_from_option(frequency)
        if dynamic_frequency is not None:
            frequency = dynamic_frequency
        try:
            frequency = int(frequency)
            if payment_type == 1:
                # Business rule: Prepaid is always Frequency with 0 days.
                frequency = 0
            elif frequency <= 0:
                errors["frequency"] = "Frequency must be a positive integer."
        except (TypeError, ValueError):
            errors["frequency"] = "Frequency must be a valid integer."

    if status in ["1", "Active", "active"]:
        status = "Active"
    elif status in ["0", "Inactive", "inactive"]:
        status = "Inactive"

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
    try:
        term.save()
    except ValidationError as e:
        return JsonResponse({
            "status": False,
            "message": "Validation failed.",
            "errors": getattr(e, "message_dict", {"non_field_errors": e.messages}),
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "status": False,
            "message": f"Unable to update payment term: {str(e)}",
        }, status=400)
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
    try:
        term.save()
    except ValidationError as e:
        return JsonResponse({
            "status": False,
            "message": "Validation failed.",
            "errors": getattr(e, "message_dict", {"non_field_errors": e.messages}),
        }, status=400)
    except Exception as e:
        return JsonResponse({
            "status": False,
            "message": f"Unable to create payment term: {str(e)}",
        }, status=400)
    return JsonResponse({
        "status": True,
        "message": "Payment Term created successfully.",
    })

