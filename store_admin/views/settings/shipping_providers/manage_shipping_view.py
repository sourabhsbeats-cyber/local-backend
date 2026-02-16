from django.contrib.auth.decorators import login_required
from django.contrib import messages
from rest_framework.decorators import api_view, renderer_classes
from rest_framework.renderers import JSONRenderer
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from store_admin.models.setting_model import ShippingProviders

@api_view(["GET"])
@renderer_classes([JSONRenderer])
@login_required
def api_all_shipping_providers(request):
    shipping_providers = ShippingProviders.objects.filter(is_archived=0).values(
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
        "data": list(shipping_providers),
        "message": ""
    })

@api_view(["PUT"])
def save_shipping_details(request, carrier_id):
    data = request.data
    try:
        provider = get_object_or_404(ShippingProviders, carrier_id=carrier_id)
        provider.carrier_name = data.get("carrier_name")
        provider.carrier_code = data.get("carrier_code")
        provider.class_code = data.get("class_code")
        provider.tracking_url = data.get("tracking_url")

        provider.save()
        return JsonResponse({
            "status": True,
            "message": "Shipping provider updated successfully"
        })

    except Exception as e:
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
    try:
        ex_provider = ShippingProviders.objects.filter(carrier_name=data.get("carrier_name")).exists()

        if ex_provider:
            return JsonResponse({
                "status": False,
                "message": "Shipping provider code already exists"
            })

        provider = ShippingProviders()
        provider.carrier_name = data.get("carrier_name")
        provider.carrier_code = data.get("carrier_code")
        provider.class_code = data.get("class_code")
        provider.tracking_url = data.get("tracking_url")
        provider.created_by = request.user.id
        provider.save()

        return JsonResponse({
            "status": True,
            "message": "Shipping provider created successfully"
        })


    except Exception as e:
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
