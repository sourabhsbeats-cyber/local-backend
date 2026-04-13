from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, URLValidator
from django.db.models import Q
from django.http import JsonResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from store_admin.AuthHandler import StrictJWTCookieAuthentication
from store_admin.vendor_portal_crypto import encrypt_password
from store_admin.models.vendor_models import Vendor, VendorPortalCredential, validate_https_http_url


def _deny():
    return JsonResponse({"status": False, "message": "Super Admin access required."})


def _require_superuser(request):
    if not request.user.is_authenticated:
        return JsonResponse({"status": False, "message": "Authentication required."})
    if not getattr(request.user, "is_superuser", False):
        return _deny()
    return None


def _validate_payload(data, require_password: bool):
    vendor_id = data.get("vendor_id")
    website_username = str(data.get("website_username", "") or "").strip()
    website_user_email = str(data.get("website_user_email", "") or "").strip()
    website_user_password = data.get("website_user_password")
    website_link = str(data.get("website_link", "") or "").strip()
    otp_enabled = bool(data.get("otp_enabled", False))
    is_active = data.get("is_active", True)
    if isinstance(is_active, str):
        is_active = is_active.lower() in ("1", "true", "active", "yes")

    if not vendor_id:
        return False, "Vendor is required."
    if not website_username:
        return False, "Website user name is required."
    if not website_user_email:
        return False, "Website user email is required."
    try:
        EmailValidator()(website_user_email)
    except ValidationError:
        return False, "Website user email is not valid."
    if require_password:
        pwd = str(website_user_password or "").strip()
        if not pwd:
            return False, "Website user password is required."
    if not website_link:
        return False, "Website link is required."
    try:
        validate_https_http_url(website_link)
        URLValidator(schemes=("http", "https"))(website_link)
    except ValidationError:
        return False, "Website link must be a valid http(s) URL."

    return True, {
        "vendor_id": int(vendor_id),
        "website_username": website_username,
        "website_user_email": website_user_email,
        "website_user_password": (str(website_user_password).strip() if website_user_password else ""),
        "website_link": website_link,
        "otp_enabled": otp_enabled,
        "is_active": bool(is_active),
    }


@api_view(["GET"])
@authentication_classes([StrictJWTCookieAuthentication])
@permission_classes([IsAuthenticated])
def list_vendor_portal_credentials(request):
    err = _require_superuser(request)
    if err:
        return err

    search = request.GET.get("search", "").strip()
    qs = VendorPortalCredential.objects.select_related("vendor").all()
    if search:
        qs = qs.filter(
            Q(vendor__vendor_company_name__icontains=search)
            | Q(vendor__vendor_code__icontains=search)
            | Q(website_username__icontains=search)
            | Q(website_user_email__icontains=search)
            | Q(website_link__icontains=search)
        )
    qs = qs.order_by("vendor__vendor_company_name")

    rows = []
    for c in qs:
        v = c.vendor
        rows.append(
            {
                "credential_id": c.id,
                "vendor_id": v.id,
                "vendor_code": v.vendor_code,
                "vendor_company_name": v.vendor_company_name,
                "website_username": c.website_username,
                "website_user_email": c.website_user_email,
                "website_link": c.website_link,
                "otp_enabled": c.otp_enabled,
                "is_active": c.is_active,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
        )

    return JsonResponse({"status": True, "data": rows, "message": ""})


@api_view(["POST"])
@authentication_classes([StrictJWTCookieAuthentication])
@permission_classes([IsAuthenticated])
def create_vendor_portal_credential(request):
    err = _require_superuser(request)
    if err:
        return err

    ok, payload_or_msg = _validate_payload(request.data, require_password=True)
    if not ok:
        return JsonResponse({"status": False, "message": payload_or_msg})

    p = payload_or_msg
    if not Vendor.objects.filter(id=p["vendor_id"]).exists():
        return JsonResponse({"status": False, "message": "Vendor not found."})
    if VendorPortalCredential.objects.filter(vendor_id=p["vendor_id"]).exists():
        return JsonResponse({"status": False, "message": "This vendor already has portal credentials."})

    cred = VendorPortalCredential(
        vendor_id=p["vendor_id"],
        website_username=p["website_username"],
        website_user_email=p["website_user_email"],
        website_link=p["website_link"],
        password_ciphertext=encrypt_password(p["website_user_password"]),
        otp_enabled=p["otp_enabled"],
        is_active=p["is_active"],
        updated_by=request.user.id,
    )
    cred.save()
    return JsonResponse({"status": True, "message": "Vendor login credentials created.", "credential_id": cred.id})


@api_view(["PUT"])
@authentication_classes([StrictJWTCookieAuthentication])
@permission_classes([IsAuthenticated])
def update_vendor_portal_credential(request, credential_id: int):
    err = _require_superuser(request)
    if err:
        return err

    try:
        cred = VendorPortalCredential.objects.get(id=credential_id)
    except VendorPortalCredential.DoesNotExist:
        return JsonResponse({"status": False, "message": "Credential record not found."})

    body = {**request.data, "vendor_id": request.data.get("vendor_id") or cred.vendor_id}
    ok, payload_or_msg = _validate_payload(body, require_password=False)
    if not ok:
        return JsonResponse({"status": False, "message": payload_or_msg})

    p = payload_or_msg
    if cred.vendor_id != p["vendor_id"]:
        return JsonResponse({"status": False, "message": "Vendor mismatch."})

    cred.website_username = p["website_username"]
    cred.website_user_email = p["website_user_email"]
    cred.website_link = p["website_link"]
    cred.otp_enabled = p["otp_enabled"]
    cred.is_active = p["is_active"]
    cred.updated_by = request.user.id
    if p["website_user_password"]:
        cred.password_ciphertext = encrypt_password(p["website_user_password"])
    cred.save()

    return JsonResponse({"status": True, "message": "Vendor login credentials updated."})


@api_view(["DELETE"])
@authentication_classes([StrictJWTCookieAuthentication])
@permission_classes([IsAuthenticated])
def delete_vendor_portal_credential(request, credential_id: int):
    err = _require_superuser(request)
    if err:
        return err

    try:
        cred = VendorPortalCredential.objects.get(id=credential_id)
    except VendorPortalCredential.DoesNotExist:
        return JsonResponse({"status": False, "message": "Credential record not found."})

    cred.delete()
    return JsonResponse({"status": True, "message": "Vendor login credentials removed."})
