from django.contrib.auth.decorators import login_required
from django.contrib import messages
from rest_framework.decorators import api_view
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from store_admin.models.setting_model import ShippingProviders
from django.db.models import Q

MAX_CARRIER_NAME_LENGTH = 255
MAX_CARRIER_CODE_LENGTH = 100
MAX_CLASS_CODE_LENGTH = 100
MAX_TRACKING_URL_LENGTH = 2000


def validate_shipping_provider_payload(data):
    carrier_name = str(data.get("carrier_name", "") or "").strip()
    carrier_code = str(data.get("carrier_code", "") or "").strip()
    class_code = str(data.get("class_code", "") or "").strip()
    tracking_url = str(data.get("tracking_url", "") or "").strip()

    if not carrier_name:
        return False, "Carrier name is required."
    if len(carrier_name) > MAX_CARRIER_NAME_LENGTH:
        return False, f"Carrier name cannot exceed {MAX_CARRIER_NAME_LENGTH} characters."

    if not carrier_code:
        return False, "Carrier code is required."
    if len(carrier_code) > MAX_CARRIER_CODE_LENGTH:
        return False, f"Carrier code cannot exceed {MAX_CARRIER_CODE_LENGTH} characters."

    if class_code and len(class_code) > MAX_CLASS_CODE_LENGTH:
        return False, f"Class code cannot exceed {MAX_CLASS_CODE_LENGTH} characters."

    if tracking_url:
        if len(tracking_url) > MAX_TRACKING_URL_LENGTH:
            return False, f"Tracking URL cannot exceed {MAX_TRACKING_URL_LENGTH} characters."
        validator = URLValidator()
        try:
            validator(tracking_url)
        except ValidationError:
            return False, "Tracking URL is not valid."

    return True, {
        "carrier_name": carrier_name,
        "carrier_code": carrier_code,
        "class_code": class_code or None,
        "tracking_url": tracking_url or None,
    }


@api_view(["GET"])
def api_all_shipping_providers(request):

    search = request.GET.get("search", "").strip()
    sort_by = request.GET.get("sort_by", "carrier_name")
    sort_dir = request.GET.get("sort_dir", "asc")

    queryset = ShippingProviders.objects.filter(is_archived=0)

    # -----------------------------
    # SEARCH
    # -----------------------------
    if search:
        queryset = queryset.filter(
            Q(carrier_name__icontains=search) |
            Q(carrier_code__icontains=search) |
            Q(class_code__icontains=search) |
            Q(tracking_url__icontains=search)
        )

    # -----------------------------
    # SORT
    # -----------------------------
    if sort_dir == "desc":
        sort_by = f"-{sort_by}"

    queryset = queryset.order_by(sort_by)

    data = queryset.values(
        "carrier_name",
        "carrier_id",
        "carrier_code",
        "class_code",
        "tracking_url",
        "status",
        "is_archived",
    )

    return JsonResponse({
        "status": True,
        "data": list(data),
        "message": ""
    })

@api_view(["PUT"])
def save_shipping_details(request, carrier_id):
    data = request.data
    valid, payload_or_message = validate_shipping_provider_payload(data)
    if not valid:
        return JsonResponse({"status": False, "message": payload_or_message})

    try:
        provider = get_object_or_404(ShippingProviders, carrier_id=carrier_id)
        if ShippingProviders.objects.exclude(carrier_id=carrier_id).filter(carrier_code=payload_or_message["carrier_code"]).exists():
            return JsonResponse({"status": False, "message": "Carrier code already exists."})

        provider.carrier_name = payload_or_message["carrier_name"]
        provider.carrier_code = payload_or_message["carrier_code"]
        provider.class_code = payload_or_message["class_code"]
        provider.tracking_url = payload_or_message["tracking_url"]
        provider.save()

        return JsonResponse({
            "status": True,
            "message": "Shipping provider updated successfully"
        })

    except Exception:
        return JsonResponse({
            "status": False,
            "message": "Error saving shipping provider details"
        })


@api_view(["POST"])
def toggle_shipping_status(request, carrier_id):
    data = request.data
    try:
        provider = get_object_or_404(ShippingProviders, carrier_id=carrier_id)
        provider.status = 0 if provider.status == 1 else 1
        status_text = "activated" if provider.status == 1 else "deactivated"
        provider.save(update_fields=["status"])
        return JsonResponse({
            "status": True,
            "message": f"Shipping provider {provider.carrier_name} has been {status_text} successfully."
        })

    except Exception as e:
        return JsonResponse({
            "status": False,
            "message": "Error updating shipping provider details"
        })

@api_view(["POST"])
def add_new_shipping_providers(request):
    data = request.data
    valid, payload_or_message = validate_shipping_provider_payload(data)
    if not valid:
        return JsonResponse({"status": False, "message": payload_or_message})

    try:
        if ShippingProviders.objects.filter(carrier_code=payload_or_message["carrier_code"]).exists():
            return JsonResponse({"status": False, "message": "Carrier code already exists."})

        provider = ShippingProviders()
        provider.carrier_name = payload_or_message["carrier_name"]
        provider.carrier_code = payload_or_message["carrier_code"]
        provider.class_code = payload_or_message["class_code"]
        provider.tracking_url = payload_or_message["tracking_url"]
        provider.created_by = getattr(request.user, 'id', None) or 0
        provider.save()

        return JsonResponse({
            "status": True,
            "message": "Shipping provider created successfully"
        })

    except Exception:
        return JsonResponse({
            "status": False,
            "message": "Error saving shipping provider details"
        })


@api_view(["DELETE"])
def delete_shipping_details(request, carrier_id):
    provider = get_object_or_404(ShippingProviders, carrier_id=carrier_id)
    name = provider.carrier_name
    provider.is_archived = 1
    provider.save(update_fields=["is_archived"])
    messages.warning(request, f"Shipping Provider '{name}' has been deleted successfully.")
    return JsonResponse({"status": True, "message": "Shipping Provider '{name}' has been deleted successfully."})
