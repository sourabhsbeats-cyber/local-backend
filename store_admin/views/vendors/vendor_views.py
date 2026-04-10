import os
import json

from dj_rest_auth.jwt_auth import JWTCookieAuthentication
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from rest_framework.decorators import api_view, parser_classes, permission_classes, authentication_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from sbadmin import settings
from store_admin.AuthHandler import StrictJWTCookieAuthentication, User
from store_admin.helpers import get_bool_int
from store_admin.models import Country, State
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.po_models.po_models import PurchaseOrder
from store_admin.models.vendor_models import Vendor, VendorBank, VendorContact, VendorWarehouse, VendorAddress
from store_admin.models.address_model import Addresses
from django.db import transaction
from django.db.models import Min
from django.db.models import Value as V
from django.db.models.functions import Concat
from django.db.models import Min, Value as V
from django.db.models.functions import Concat
from django.core.paginator import Paginator
from django.db.models import Q
from django.core.validators import validate_email
from store_admin.helpers import parse_json_field, upsert_vendor_bank, upsert_vendor_contacts, upsert_vendor_warehouses, save_vendor_addresses

def parse_json_field(value, default):
    if value in [None, "", "null", "undefined"]:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def normalize_mode_of_payment(raw_modes):
    if isinstance(raw_modes, list):
        return [str(m).strip() for m in raw_modes if str(m).strip()]
    if isinstance(raw_modes, str):
        return [m.strip() for m in raw_modes.split(",") if m.strip()]
    return []


def upsert_vendor_bank(vendor, primary, user_id=0):
    from store_admin.models.vendor_models import VendorBank  # moved inside to avoid circular import

    if not hasattr(vendor, 'mode_of_payment'):
        return

    mode_list = normalize_mode_of_payment(primary.get('mode_of_payment') or "")
    vendor.mode_of_payment = ",".join(mode_list) if mode_list else None

    if 'paypal' in mode_list:
        vendor.paypal_email = primary.get('paypal_email') or None
        vendor.paypal_merchant_id = primary.get('paypal_merchant_id') or None
        vendor.paypal_environment = primary.get('paypal_environment') or 'sandbox'
        vendor.paypal_transaction_fee = primary.get('paypal_transaction_fee') or 0.00
    else:
        vendor.paypal_email = None
        vendor.paypal_merchant_id = None
        vendor.paypal_environment = 'sandbox'
        vendor.paypal_transaction_fee = 0.00

    if 'bank_transfer' in mode_list:
        bank_data = {
            'account_holder': primary.get('account_name') or "",
            'bank_name': primary.get('bank_name') or "",
            'bank_branch': primary.get('bank_branch') or None,
            'account_number': str(primary.get('account_number') or ""),
            'bic': primary.get('bank_ifsc') or "",
            'bank_country': primary.get('bank_country') or None,
            'created_by': user_id
        }
        bank_obj = VendorBank.objects.filter(vendor_id=vendor.id).first()
        if bank_obj:
            for k, v in bank_data.items():
                setattr(bank_obj, k, v)
            bank_obj.save()
        elif any(bank_data.values()):
            VendorBank.objects.create(vendor_id=vendor.id, **bank_data)

    if 'credit_card' in mode_list:
        vendor.cardholder_name = primary.get('cardholder_name') or None
        vendor.card_last_four = primary.get('card_last_four') or None
        vendor.card_expiry = primary.get('card_expiry') or None
        vendor.accepted_card = primary.get('accepted_card') or None
        vendor.payment_gateway = primary.get('payment_gateway') or None
        vendor.processing_fee = primary.get('processing_fee') or 0.00
        vendor.three_d_secure = primary.get('three_d_secure') or 'no'
    else:
        vendor.cardholder_name = None
        vendor.card_last_four = None
        vendor.card_expiry = None
        vendor.accepted_card = None
        vendor.payment_gateway = None
        vendor.processing_fee = 0.00
        vendor.three_d_secure = 'no'

    if 'wallet' in mode_list:
        vendor.wallet_type = primary.get('wallet_type') or None
        vendor.auto_detect_invoice = primary.get('auto_detect_invoice') or 'no'
        vendor.allow_negative_balance = primary.get('allow_negative_balance') or 'no'
        vendor.minimum_wallet_balance = primary.get('minimum_wallet_balance') or 0.00
        vendor.low_balance_email = primary.get('low_balance_email') or None
    else:
        vendor.wallet_type = None
        vendor.auto_detect_invoice = 'no'
        vendor.allow_negative_balance = 'no'
        vendor.minimum_wallet_balance = 0.00
        vendor.low_balance_email = None

    vendor.paypal_notes = primary.get('paypal_notes') or None
    vendor.credit_card_notes = primary.get('credit_card_notes') or None
    vendor.wallet_notes = primary.get('wallet_notes') or None
    vendor.currency = primary.get('currency') or vendor.currency
    vendor.save()


def upsert_vendor_contacts(vendor, contacts, user_id=0):
    from store_admin.models.vendor_models import VendorContact  # moved inside
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError

    if not contacts:
        return
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        contact_id = contact.get('id') or contact.get('contact_id')
        vendor_contact = None
        if contact_id:
            vendor_contact = VendorContact.objects.filter(id=contact_id, vendor_id=vendor.id).first()

        email = (contact.get('email') or '').strip()
        if email:
            try:
                validate_email(email)
            except ValidationError:
                email = None

        if vendor_contact:
            vendor_contact.department = contact.get('department') or vendor_contact.department
            vendor_contact.email = email or vendor_contact.email
            vendor_contact.phone = contact.get('phone') or vendor_contact.phone
            vendor_contact.first_name = (contact.get('first_name') or vendor_contact.first_name).strip()
            vendor_contact.last_name = (contact.get('last_name') or vendor_contact.last_name).strip()
            vendor_contact.description = contact.get('description') or vendor_contact.description
            vendor_contact.role = contact.get('role') or vendor_contact.role
            vendor_contact.save()
        else:
            if not any([contact.get('first_name'), contact.get('last_name'), email, contact.get('phone')]):
                continue
            VendorContact.objects.create(
                vendor_id=vendor.id,
                department=contact.get('department'),
                email=email,
                phone=contact.get('phone'),
                first_name=(contact.get('first_name') or '').strip() or 'Unknown',
                last_name=(contact.get('last_name') or '').strip() or 'Unknown',
                description=contact.get('description'),
                role=contact.get('role') or 'Unknown',
                created_by=user_id
            )


def upsert_vendor_warehouses(vendor, warehouses, user_id=0):
    from store_admin.models.vendor_models import VendorWarehouse  # moved inside

    if not warehouses:
        return
    for warehouse in warehouses:
        if not isinstance(warehouse, dict):
            continue
        warehouse_id = warehouse.get('warehouse_id') or warehouse.get('id')
        vendor_warehouse = None
        if warehouse_id:
            vendor_warehouse = VendorWarehouse.objects.filter(warehouse_id=warehouse_id, vendor_id=vendor.id).first()

        if vendor_warehouse:
            vendor_warehouse.name = warehouse.get('name') or vendor_warehouse.name
            vendor_warehouse.delivery_name = warehouse.get('delivery_name') or vendor_warehouse.delivery_name
            vendor_warehouse.address_line1 = warehouse.get('address_line1') or vendor_warehouse.address_line1
            vendor_warehouse.address_line2 = warehouse.get('address_line2') or vendor_warehouse.address_line2
            vendor_warehouse.city = warehouse.get('city') or vendor_warehouse.city
            vendor_warehouse.state_id = warehouse.get('state_id') or vendor_warehouse.state_id
            vendor_warehouse.zip = warehouse.get('zip') or vendor_warehouse.zip
            vendor_warehouse.country_id = warehouse.get('country_id') or vendor_warehouse.country_id
            vendor_warehouse.is_primary = bool(warehouse.get('is_primary', vendor_warehouse.is_primary))
            vendor_warehouse.save()
        else:
            VendorWarehouse.objects.create(
                vendor_id=vendor.id,
                name=(warehouse.get('name') or '').strip() or 'Unknown',
                delivery_name=(warehouse.get('delivery_name') or '').strip() or 'Unknown',
                address_line1=(warehouse.get('address_line1') or '').strip() or 'Unknown',
                address_line2=(warehouse.get('address_line2') or '').strip() or 'Unknown',
                city=(warehouse.get('city') or '').strip() or 'Unknown',
                state_id=warehouse.get('state_id') or None,
                zip=(warehouse.get('zip') or '').strip() or '000000',
                country_id=warehouse.get('country_id') or None,
                is_primary=bool(warehouse.get('is_primary', False)),
                created_by=user_id
            )


def save_vendor_addresses(vendor_id, billing_address, shipping_address, user_id=0):
    from store_admin.models.vendor_models import VendorAddress  # moved inside

    def save_address(address_data, addr_type, vendor_id, source, user_id):
        if not address_data:
            return
        VendorAddress.objects.update_or_create(
            vendor_id=vendor_id,
            address_type=addr_type,
            defaults={
                'address_line': address_data.get('address_line'),
                'city': address_data.get('city'),
                'state': address_data.get('state'),
                'zipcode': address_data.get('zipcode'),
                'created_by': user_id
            }
        )

    if billing_address:
        save_address(billing_address, 'billing', vendor_id, 'API', user_id)
    if shipping_address:
        save_address(shipping_address, 'shipping', vendor_id, 'API', user_id)


from store_admin.serializers.common_serializers import VendorContactSerializer, VendorBankSerializer
from store_admin.serializers.payment_serializers import VendorPaymentLogSerializer, VendorPaymentLogItemSerializer

@api_view(["GET"])
def get_vendor_details(request):
    vendor_id = request.GET.get("vendor_id")
    try:
        vendor = Vendor.objects.get(id=vendor_id)
        if not vendor:
            raise Exception("vendor not found")

        # Helper function to serialize addresses (Billing/Shipping)
        def serialize_address(address_type):
            # Link Vendor to the specific address type
            rel = VendorAddress.objects.filter(vendor_id=vendor.id, address_type=address_type).first()
            addr = rel.address if rel else None
            if not addr:
                return {
                    "attention": "", "country": "", "street1": "", "street2": "",
                    "city": "", "state": "", "zip": "", "phone": "", "fax": "",
                    "state_list": []
                }

            # Fetch state list for the saved country to populate React dropdowns immediately
            state_list = list(State.objects.filter(country_id=addr.country_id).values('id', 'name'))

            return {
                "attention": addr.attention_name or "",
                "country": addr.country.id if addr.country else "",
                "street1": addr.street1 or "",
                "street2": addr.street2 or "",
                "city": addr.city or "",
                "state": addr.state.id if addr.state else "",
                "state_name": addr.state.name if addr.state else "",
                "zip": addr.zip or "",
                "phone": addr.phone or "",
                "fax": addr.fax or "",
                "state_list": state_list
            }

        def get_vendor_bank_data(vendor_id):
            bank = VendorBank.objects.filter(vendor_id=vendor_id).order_by("-created_at").first()
            if not bank:
                return {
                    "bank_name": "",
                    "bank_branch": "",
                    "bank_ifsc": "",
                    "account_name": "",
                    "bank_country": "",
                    "account_number": "",
                    "bank_verification_doc": ""
                }
            return {
                "bank_name": bank.bank_name or "",
                "bank_branch": bank.bank_branch or "",
                "bank_ifsc": bank.bic or "",
                "account_name": bank.account_holder or "",
                "bank_country": bank.bank_country or "",
                "account_number": bank.account_number or "",
                "bank_verification_doc": ""
            }

        bank_data = get_vendor_bank_data(vendor.id)

        # Serialize Bank and Contact records
        qs = VendorDocuments.objects.filter(vendor_id=vendor.id)

        # collect all user ids
        user_ids = qs.values_list("created_by", flat=True)

        # build id → username map
        user_map = {
            u.id: u.name
            for u in User.objects.filter(id__in=user_ids)
        }

        documents = []
        for d in qs:
            documents.append({
                "id": d.pk,
                "file_path": request.build_absolute_uri(d.file_path.url),
                "file_name": d.file_name,
                "created_by": user_map.get(d.created_by),  # username
                "created_at": d.created_at.strftime("%d-%m-%Y %I:%M %p"),
            })

        contacts = list(VendorContact.objects.filter(vendor_id=vendor.id).values(
            'id', 'first_name', 'last_name', 'role', 'email', 'phone', 'department', 'description'
        ))

        # Structure response to match your React 'profile' and 'details' states
        context = {
            "primary": {
                "vendor_code": vendor.vendor_code ,
                "vendor_company_name": vendor.vendor_company_name ,
                "vendor_name": vendor.vendor_name ,
                "gst_number": vendor.gst_number or "",
                "tax_percent": vendor.tax_percent or "",
                "min_order_value": vendor.min_order_value or "",
                "is_taxable": vendor.is_taxable or "0",
                "default_warehouse": None, #vendor.default_warehouse or "",
                "payment_term": vendor.payment_term or "",
                "company_abn": vendor.company_abn or "",
                "company_acn": vendor.company_acn or "",
                "bank_name": bank_data["bank_name"],
                "bank_branch": bank_data["bank_branch"],
                "bank_ifsc": bank_data["bank_ifsc"],
                "mode_of_payment": [m for m in (vendor.mode_of_payment or "").split(",") if m.strip()],
                "cardholder_name": vendor.cardholder_name or "",
                "card_type": vendor.card_type or "",
                "card_last_four": vendor.card_last_four or "",
                "card_expiry": vendor.card_expiry or "",
                "paypal_email": vendor.paypal_email or "",
                "paypal_merchant_id": vendor.paypal_merchant_id or "",

                "company_acc_no": vendor.company_acc_no or "",
                "company_website": vendor.company_website or "",
                "vendor_model": getattr(vendor, "vendor_model", "") or "",
                "vendor_locality": vendor.vendor_locality or "",

                "paypal_notes": vendor.paypal_notes or "",
                "credit_card_notes": vendor.credit_card_notes or "",
                "wallet_notes": vendor.wallet_notes or "",

                "wallet_type": vendor.wallet_type or "",
                "auto_detect_invoice": vendor.auto_detect_invoice or "",
                "allow_negative_balance": vendor.allow_negative_balance or "",
                "minimum_wallet_balance": vendor.minimum_wallet_balance or "",
                "low_balance_email": vendor.low_balance_email or "",
                "account_name": bank_data["account_name"],
                "bank_country": bank_data["bank_country"],
                "bank_verification_doc": bank_data["bank_verification_doc"],
                "paypal_environment": vendor.paypal_environment or "",
                "paypal_transaction_fee": vendor.paypal_transaction_fee or "",
                "accepted_card": vendor.accepted_card or "",
                "payment_gateway": vendor.payment_gateway or "",
                "processing_fee": vendor.processing_fee or "",
                "three_d_secure": vendor.three_d_secure or "",

                "account_number": bank_data["account_number"],
                "reminder": getattr(vendor, "reminder", "") or "",
                "remarks": getattr(vendor, "remarks", "") or "",
                "status": vendor.status,
                "currency": vendor.currency or "",
                #"document": request.build_absolute_uri(vendor.documents.url) if vendor.documents else None
            },
            "details": {
                "billing_address": serialize_address("billing"),
                "shipping_address": serialize_address("shipping"),
                "contacts": contacts,
                "documents": documents
            },
            "onboard_details":{
                "first_contact_date": getattr(vendor, "first_contact_date", "") or "",
                "first_contact_via": getattr(vendor, "first_contact_via", "") or "",
                "onboard_date": getattr(vendor, "onboard_date", "") or "",
                "onboard_by": getattr(vendor, "onboard_by", "") or "",
                "mode_of_contact": getattr(vendor, "mode_of_contact", "") or "",
                "comments": getattr(vendor, "comments", "") or "",
            }
        }

        return JsonResponse({"status": True, "data": context})
    except Exception as err:
        return JsonResponse({"status": False, "message": f"Error - {str(err)}"}, status=500)


from rest_framework import serializers, status


class PaymentTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTerm
        fields = '__all__'


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([StrictJWTCookieAuthentication])
# Note: Ensure JWTCookieAuthentication is properly configured in your settings
def all_vendors(request):
    # 1. Get Params
    search_query = request.GET.get("vendor_search", "").strip()
    search_status = request.GET.get("status", "").strip()
    vendor_locality = request.GET.get("vendor_locality", "").strip()
    sort_by = request.GET.get("sort_by", "id")  # Default sort by id
    sort_dir = request.GET.get("sort_dir", "desc")
    page_size = int(request.GET.get("size", 20)) # Tabulator sends 'size', not 'page_size'
    page_number = int(request.GET.get("page", 1))

    # 2. Base Queryset
    vendors = Vendor.objects.all()

    # 3. Filtering
    if search_query:
        vendors = vendors.filter(
            Q(vendor_name__icontains=search_query) |
            Q(vendor_code__icontains=search_query)
        )

    if search_status:
        vendors = vendors.filter(status=search_status)

    if vendor_locality:
        vendors = vendors.filter(vendor_locality=vendor_locality)

    # 4. Sorting
    # Map the direction: 'desc' becomes '-field_name'
    if sort_dir == "desc":
        order_string = f"-{sort_by}"
    else:
        order_string = sort_by

    try:
        vendors = vendors.order_by(order_string)
    except Exception:
        # Fallback if an invalid field name is passed
        vendors = vendors.order_by("vendor_name")

    # 5. Pagination
    paginator = Paginator(vendors, page_size)
    page_obj = paginator.get_page(page_number)

    # 6. Serialize (Only the paginated objects!)
    vendor_data = []
    for vendor in page_obj: # Use page_obj, NOT vendors
        billing_details = shipping_details = None

        vendor_addresses = VendorAddress.objects.filter(vendor_id=vendor.id)

        for addr in vendor_addresses:
            if addr.address_type == "billing":
                billing_details = addr.address  # Directly access the related Addresses object
            elif addr.address_type == "shipping":
                shipping_details = Addresses.objects.filter(id=addr.address_id).first()

        vendor_data.append({
            "id": vendor.id,
            "vendor_name": vendor.vendor_name,
            "vendor_code": vendor.vendor_code,
            "currency": vendor.currency,
            "billing_country" : billing_details.country.name  if billing_details and billing_details.country else "",
            "shipping_country" : shipping_details.country.name if shipping_details and shipping_details.country else "",
            "billing_city" : billing_details.city if billing_details else "",
            "shipping_city" : shipping_details.city if shipping_details else "",

            "vendor_model": getattr(vendor, "vendor_model", "") or "",
            "vendor_locality": vendor.vendor_locality,
            "status": vendor.status,
            "tax_percent": vendor.tax_percent,
            "is_taxable": vendor.is_taxable,
            "reminder": getattr(vendor, "reminder", "") or "",
        })

    return JsonResponse({
        "data": vendor_data,
        "last_page": paginator.num_pages,
        "total": paginator.count,
    })

@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([StrictJWTCookieAuthentication])
def api_vendor_warehouses(request, vendor_id):  # Added 'request' argument
    # 1. Check if vendor exists
    get_object_or_404(Vendor, pk=vendor_id)

    # 2. Fetch warehouses associated with the vendor_id
    # Using .values() is the fastest way to get a JSON-serializable list
    # without creating a separate Serializer class.
    warehouses = VendorWarehouse.objects.filter(vendor_id=vendor_id).order_by("-warehouse_id").values(
        'warehouse_id',
        'name',
        'delivery_name',
        'address_line1',
        'address_line2',
        'city',
        'state_id',
        'zip',
        'country_id',
        'is_primary',
        'created_at'
    )

    return JsonResponse({
        "status": True,
        "data": list(warehouses)  # Convert QuerySet to a standard Python list
    })


from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
import json


# Replace with your actual model import
# from .models import VendorWarehouse

class WarehouseDetailManager(APIView):
    permission_classes = [IsAuthenticated]

    # If you are using JWT cookies, add authentication_classes here
    # authentication_classes = [JWTCookieAuthentication]

    def get(self, request, warehouse_id, vendor_id=None):
        """Fetch Details"""
        warehouse = get_object_or_404(VendorWarehouse, pk=warehouse_id)
        data = {
            "id": warehouse.id,
            "name": warehouse.name,
            "delivery_name": warehouse.delivery_name,
            "address_line1": warehouse.address_line1,
            "address_line2": warehouse.address_line2,
            "city": warehouse.city,
            "state_id": warehouse.state_id,
            "zip": warehouse.zip,
            "country_id": warehouse.country_id,
            "is_primary": warehouse.is_primary,
        }
        return JsonResponse({"status": True, "data": data})

    def put(self, request, warehouse_id, vendor_id=None):
        """Update (Edit) Details"""
        warehouse = get_object_or_404(VendorWarehouse, pk=warehouse_id)
        try:
            data = json.loads(request.body)
            warehouse.name = data.get("name", warehouse.name)
            warehouse.delivery_name = data.get("delivery_name", warehouse.delivery_name)
            warehouse.address_line1 = data.get("address_line1", warehouse.address_line1)
            warehouse.address_line2 = data.get("address_line2", warehouse.address_line2)
            warehouse.city = data.get("city", warehouse.city)
            warehouse.state_id = data.get("state_id", warehouse.state_id)
            warehouse.zip = data.get("zip", warehouse.zip)
            warehouse.country_id = data.get("country_id", warehouse.country_id)
            warehouse.is_primary = data.get("is_primary", warehouse.is_primary)

            warehouse.save()
            return JsonResponse({"status": True, "message": "Warehouse updated successfully"})
        except Exception as e:
            return JsonResponse({"status": False, "message": str(e)}, status=400)

    def post(self, request, vendor_id=None):
        """Update (Edit) Details"""
        warehouse = VendorWarehouse()
        try:
            data = json.loads(request.body)
            warehouse.name = data.get("name", warehouse.name)
            warehouse.vendor_id = vendor_id
            warehouse.delivery_name = data.get("delivery_name", warehouse.delivery_name)
            warehouse.address_line1 = data.get("address_line1", warehouse.address_line1)
            warehouse.address_line2 = data.get("address_line2", warehouse.address_line2)
            warehouse.city = data.get("city", warehouse.city)
            warehouse.state_id = data.get("state_id", warehouse.state_id)
            warehouse.zip = data.get("zip", warehouse.zip)
            warehouse.country_id = data.get("country_id", warehouse.country_id)
            warehouse.is_primary = data.get("is_primary", warehouse.is_primary)

            warehouse.save()
            return JsonResponse({"status": True, "message": "Warehouse created successfully"})
        except Exception as e:
            return JsonResponse({"status": False, "message": str(e)}, status=400)

    def delete(self, request, warehouse_id, vendor_id=None):
        """Remove Warehouse"""
        warehouse = get_object_or_404(VendorWarehouse, warehouse_id=warehouse_id)
        warehouse.delete()
        return JsonResponse({"status": True, "message": "Warehouse deleted successfully"})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTCookieAuthentication])
def api_all_vendors(request):
    search = request.GET.get("search", "").strip()

    vendors = Vendor.objects.order_by("id")

    # Apply search filter
    if search:
        vendors = vendors.filter(
            Q(vendor_code__icontains=search) |
            Q(vendor_name__icontains=search)
        )

    vendor_data = []
    for vendor in vendors:
        vendor_data.append({
            "id": vendor.id,
            "vendor_name": vendor.vendor_name,
            "vendor_code": vendor.vendor_code,
            "currency": vendor.currency,
            "tax_percent": vendor.tax_percent,
            "is_taxable": vendor.is_taxable,
            "reminder": getattr(vendor, "reminder", "") or "",
        })

    return JsonResponse({"status": True, "data": vendor_data})


from django.http import FileResponse, Http404
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([StrictJWTCookieAuthentication])
def download_import_template(request):
    import_type = request.GET.get('file_type', 'vendor')
    file_format = request.GET.get('file_format', 'csv')
    #= request.GET.get("order_no", "").strip()
    # Map parameters to the exact filenames shown in your folder structure
    # Map parameters to the exact filenames shown in your folder structure


    file_map = {
        ('vendor', 'csv'): 'vendor_template.csv',
        ('vendor', 'xl'): 'vendor_template.xlsx',
        ('contact', 'csv'): 'vendor_template_contacts.csv',
        ('contact', 'xl'): 'vendor_template_contacts.xlsx',
    }

    filename = file_map.get((import_type, file_format))

    #filename
    if not filename:
        raise Http404("Invalid template parameters provided.")

    # Construct path based on your uploaded folder structure: static/import_templates/vendor/
    # Note: If 'static' is at your project root, use BASE_DIR.
    # If it's handled by STATIC_ROOT, use that.
    temp_dir = os.path.join(settings.MEDIA_ROOT, "imports", "vendors")
    file_path = os.path.join(temp_dir, filename)

    if not os.path.exists(file_path):
        # Fallback check in case your static path is configured differently
        raise Http404(f"Template file not found at: {file_path}")

    # Determine the correct MIME type for the browser
    content_type = 'text/csv' if filename.endswith(
        '.csv') else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    # Stream the file using FileResponse
    response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.http import FileResponse, Http404
import pandas as pd

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([StrictJWTCookieAuthentication])
def download_export_vendors(request):
    file_format = request.GET.get('format', 'csv')
    file_type = request.GET.get('file_type', 'vendor')  # Using the file_type argument

    export_data = []
    sheet_name = 'Data'
    filename_base = 'Export'

    # --- BRANCH 1: VENDOR EXPORT ---
    if file_type == 'vendor':
        vendors = Vendor.objects.all()
        sheet_name = 'Vendors'
        filename_base = 'Vendor_Address_Export'

        for vendor in vendors:
            payment_term_obj = PaymentTerm.objects.filter(id=vendor.payment_term).first()
            bank = VendorBank.objects.filter(vendor_id=vendor.id).order_by("-created_at").first()
            row = {
                'Vendor Code': vendor.vendor_code,
                'Vendor Name': vendor.vendor_name,
                'Payment Term': payment_term_obj.name if payment_term_obj else "",
                'Company ABN': vendor.company_abn,
                'Company ACN': vendor.company_acn,
                'Taxable': 'Yes' if vendor.is_taxable == 0 else 'No',
                'Tax %': vendor.tax_percent,
                'Bank Name': bank.bank_name if bank else "",
                'Bank Branch': bank.bank_branch if bank else "",
                'Bank Account Number': bank.account_number if bank else "",
                'Currency Code': vendor.currency,
                'Status': vendor.get_status_display(),
            }

            def get_address_data(addr_type):
                rel = VendorAddress.objects.filter(vendor_id=vendor.id, address_type=addr_type).first()
                if rel:
                    addr = Addresses.objects.filter(id=rel.address_id).first()
                    if addr:
                        return {
                            'attention': addr.attention_name,
                            'country': addr.country.name if addr.country else "",
                            'street1': addr.street1,
                            'street2': addr.street2,
                            'state': addr.state.name if addr.state else "",
                            'city': addr.city,
                            'zip': addr.zip,
                            'phone': addr.phone
                        }
                return {}

            billing = get_address_data('billing')
            row.update({
                'Billing Attention Name': billing.get('attention', ''),
                'Billing Country': billing.get('country', ''),
                'Billing Street Address': billing.get('street1', ''),
                'Billing Street Address 2': billing.get('street2', ''),
                'Billing State': billing.get('state', ''),
                'Billing City': billing.get('city', ''),
                'Billing ZIP': billing.get('zip', ''),
                'Billing Phone': billing.get('phone', ''),
            })

            shipping = get_address_data('shipping')
            row.update({
                'Shipping Attention Name': shipping.get('attention', ''),
                'Shipping Country': shipping.get('country', ''),
                'Shipping Street Address': shipping.get('street1', ''),
                'Shipping Street Address 2': shipping.get('street2', ''),
                'Shipping State': shipping.get('state', ''),
                'Shipping City': shipping.get('city', ''),
                'Shipping ZIP': shipping.get('zip', ''),
                'Shipping Phone': shipping.get('phone', ''),
            })
            export_data.append(row)

    # --- BRANCH 2: CONTACT EXPORT ---
    elif file_type == 'contact':
        # 1. Fetch all vendors first (Exactly like your vendor branch)
        vendors = Vendor.objects.all()
        sheet_name = 'Vendor Contacts'
        filename_base = 'Vendor_Contacts_Export'

        for vendor in vendors:
            # 2. Fetch all contacts for THIS specific vendor
            # Filter condition: VendorContact.vendor_id = vendor.id
            vendor_contacts = VendorContact.objects.filter(vendor_id=vendor.id).all()

            # 3. Iterate through VendorContacts and insert into export_data
            for contact in vendor_contacts:
                row = {
                    'Vendor Code': vendor.vendor_code,  # Direct vendor-la
                    'First Name': contact.first_name,
                    'Last Name': contact.last_name,
                    'Department': getattr(contact, 'department', ''),
                    'Email': contact.email,
                    'Phone': contact.phone,
                    'Description': getattr(contact, 'description', ''),
                }
                export_data.append(row)

    # 4. Create DataFrame and Export (Common for both)
    df = pd.DataFrame(export_data)

    if file_format == 'xl':
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
        response = HttpResponse(output.getvalue(),
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename_base}.xlsx"'
        return response
    else:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename_base}.csv"'
        df.to_csv(path_or_buf=response, index=False)
        return response


def api_vendor_search(request):
    try:
        # Search filter
        q = request.GET.get("q", "").strip()

        qs = Vendor.objects.all()

        if q:
            # Text search → name/code/company only
            qs = qs.filter(
                Q(vendor_name__icontains=q) |
                Q(vendor_code__icontains=q)
            )

        qs = qs.order_by("vendor_name")[:20]

        data = [
            {
                "id": v.id,
                "vendor_name": v.vendor_name,
                "vendor_code": v.vendor_code,
            }
            for v in qs
        ]

        return JsonResponse({"data": data})
    except Exception as e:
        print(e)
        return JsonResponse({"status":False, "data":[]})


from django.db.models import F
def api_get_vendor_by_id(request, vendor_id):
    try:
        vendor = Vendor.objects.annotate(
            name=F(
                'display_name'
            )
        ).values(
            'id',
            'name',
            'display_name',
            'company_name',
            'vendor_code',
            'currency',
            'company_abn',
            'payment_method',
            'payment_term_id'
        ).get(id=vendor_id)

        if not vendor.get("currency", None):
            try:
                vendor_detail = Vendor.objects.get(id=vendor.get("id"))
                vendor_detail.currency = "AUD"
                vendor_detail.save()
                vendor.setdefault("currency", "AUD")
            except Exception as e:
                vendor.setdefault("currency", "AUD")

        vendor_address_detail = None

        vendor_address = VendorAddress.objects.filter(
            vendor_id=vendor_id,
            address_type="billing"
        ).first()

        if vendor_address:
            address = Addresses.objects.filter(id=vendor_address.address_id).first()

            if address:
                country = Country.objects.filter(id=address.country_id).first()
                state = State.objects.filter(id=address.state_id).first()

                vendor_address_detail = {
                    "attention_name": address.attention_name,
                    "city": address.city,
                    "country": country.name if country else "",
                    "fax": address.fax,
                    "phone": address.phone,
                    "state": state.name if state else "",
                    "street1": address.street1,
                    "street2": address.street2,
                    "zip": address.zip,
                }
        return JsonResponse({
            "status": True,
            "data": vendor,
            "billing_address":vendor_address_detail
        })

    except Vendor.DoesNotExist:
        return JsonResponse({
            "status": False,
            "message": "Vendor not found"
        }, status=404)

import re
import ast
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([StrictJWTCookieAuthentication])
def api_add_new_vendor(request):
    data = request.data
    primary = parse_json_field(data.get('primary'), {})
    details = parse_json_field(data.get('details'), {})
    warehouses = parse_json_field(data.get('warehouses'), [])
    contacts = parse_json_field(data.get('contacts'), [])

    billing_address = details.get('billing_address') or parse_json_field(data.get('billing_address'), {})
    shipping_address = details.get('shipping_address') or parse_json_field(data.get('shipping_address'), {})

    vendor_code = (primary.get('vendor_code') or data.get('vendor_code') or '').strip()
    vendor_name = (primary.get('vendor_name') or data.get('vendor_name') or '').strip()
    vendor_company_name = (primary.get('vendor_company_name') or data.get('vendor_company_name') or '').strip()

    if not vendor_code or not vendor_name or not vendor_company_name:
        return JsonResponse({
            'status': False,
            'message': 'Vendor Code, Name & Company Name are required'
        }, status=400)

    if Vendor.objects.filter(vendor_code=vendor_code).exists():
        return JsonResponse({'status': False, 'message': 'Vendor code already exists'}, status=400)

    if Vendor.objects.filter(vendor_name=vendor_name).exists():
        return JsonResponse({'status': False, 'message': 'Vendor name already exists'}, status=400)

    def safe_float(val, default=0):
        try:
            return float(val)
        except Exception:
            return default

    tax_percent = safe_float(primary.get('tax_percent') or data.get('tax_percent'))
    min_order_value = safe_float(primary.get('min_order_value') or data.get('min_order_value'))
    is_taxable = 1 if str(primary.get('is_taxable') or data.get('is_taxable', '')).lower() in ['1', 'true'] else 0

    if is_taxable and tax_percent <= 0:
        return JsonResponse({
            'status': False,
            'message': 'Tax % required when taxable'
        }, status=400)

    with transaction.atomic():
        vendor = Vendor.objects.create(
            vendor_code=vendor_code,
            vendor_name=vendor_name,
            vendor_company_name=vendor_company_name,
            company_acc_no=primary.get('company_acc_no') or None,
            company_website=primary.get('company_website') or None,
            tax_percent=tax_percent,
            is_taxable=is_taxable,
            min_order_value=min_order_value,
            created_by=request.user.id if request.user.is_authenticated else None,
            status=primary.get('status') or data.get('status') or 0,
            payment_term=primary.get('payment_term') or None,
            company_acn=primary.get('company_acn') or None,
            company_abn=primary.get('company_abn') or None,
            vendor_locality=primary.get('vendor_locality') or None,
            currency=primary.get('currency') or None
        )

        # Optional vendor model field
        if hasattr(vendor, 'vendor_model'):
            vendor.vendor_model = primary.get('vendor_model') or ''

        # Save related models
        upsert_vendor_bank(vendor, primary, request.user.id if request.user.is_authenticated else 0)
        upsert_vendor_contacts(vendor, contacts, request.user.id if request.user.is_authenticated else 0)
        upsert_vendor_warehouses(vendor, warehouses, request.user.id if request.user.is_authenticated else 0)
        save_vendor_addresses(vendor.id, billing_address, shipping_address, request.user.id if request.user.is_authenticated else 0)

        # Set default warehouse if provided
        default_wh_id = primary.get('default_warehouse')
        if default_wh_id:
            VendorWarehouse.objects.create(
                vendor=vendor,
                warehouse_id=default_wh_id,
                is_default=True
            )

    return JsonResponse({
        'status': True,
        'message': 'Vendor created successfully',
        'vendor_id': vendor.id
    }, status=201)

@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def upload_vendor_files(request):
    vendor_id = request.data.get("vendor_id")
    uploaded_file = request.FILES.get("file")

    if not vendor_id or not uploaded_file:
        return JsonResponse({"status": False, "message": "Missing file or vendor ID"})

    try:
        # 1. Define relative and absolute paths
        # Using relative path 'uploads/vendors/' for database storage
        relative_folder = os.path.join("vendor_documents", str(vendor_id))
        absolute_folder = os.path.join(settings.MEDIA_ROOT, relative_folder)
        os.makedirs(absolute_folder, exist_ok=True)

        file_name = uploaded_file.name
        absolute_path = os.path.join(absolute_folder, file_name)
        db_path = os.path.join(relative_folder, file_name)

        # 2. Save the file
        with open(absolute_path, "wb+") as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        # 3. Create Database Entry
        new_doc = VendorDocuments.objects.create(
            vendor_id=vendor_id,
            file_name=file_name,
            file_path=db_path,
            created_by = request.user.id if request.user.is_authenticated else None
        )

        # 4. Return data for the frontend table
        return JsonResponse({
            "status": True,
            "message": "File uploaded successfully",
            "new_file": {
                "id": new_doc.file_id,
                "file_path": file_name,
                "created_by": f"{settings.MEDIA_URL}{db_path}",
                "created_at": f""
            }
        })

    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)})


from django.http import JsonResponse

@api_view(["DELETE"])
def delete_vendor_document(request, file_id):
    """
    Deletes the physical file and the database record for a vendor document.
    """
    try:
        # 1. Retrieve the document record
        document = VendorDocuments.objects.get(file_id=file_id)

        # 2. Delete the physical file from disk
        # Using document.file_path.delete() handles the os.remove logic automatically
        if document.file_path:
            document.file_path.delete(save=False)

        # 3. Delete the database entry
        document.delete()

        return JsonResponse({
            "status": True,
            "message": "Vendor document deleted successfully"
        })

    except VendorDocuments.DoesNotExist:
        return JsonResponse({
            "status": False,
            "message": "File record not found"
        }, status=404)

    except Exception as e:
        return JsonResponse({
            "status": False,
            "message": str(e)
        }, status=500)


from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def api_save_vendor(request):
    data = request.data

    # Parse JSON safely
    try:
        primary = json.loads(data.get("primary", "{}"))
        details = json.loads(data.get("details", "{}"))
        onboard_details = json.loads(data.get("onboard_details", "{}"))

    except json.JSONDecodeError:
        return JsonResponse({
            "status": False,
            "message": "Invalid JSON payload"
        }, status=400)
    verification_file = None #request.FILES.get('bank_verification_doc')
    vendor_id = data.get("vendor_id")

    vendor_code = (primary.get("vendor_code") or "").strip()
    vendor_name = (primary.get("vendor_name") or "").strip()
    vendor_company_name = (primary.get("vendor_company_name") or "").strip()
    company_acc_no = primary.get("company_acc_no")
    #gst_number = primary.get("gst_number")

    # Validation
    if not vendor_code or not vendor_name:
        return JsonResponse({
            "status": False,
            "message": "Vendor code and Vendor name are required"
        }, status=400)




    ''''''

    if Vendor.objects.filter(vendor_code=vendor_code).exclude(id=vendor_id).exists():
        return JsonResponse({
            "status": False,
            "message": "Vendor code already exists"
        }, status=400)

    if Vendor.objects.filter(vendor_name=vendor_name).exclude(id=vendor_id).exists():
        return JsonResponse({
            "status": False,
            "message": "Vendor name already exists"
        }, status=400)
    '''
    if not vendor_name:
        if Vendor.objects.filter(gst_number=gst_number).exclude(id=vendor_id).exists():
            return JsonResponse({
                "status": False,
                "message": "Vendor GST already exists"
            }, status=400)'''

    try:
        with transaction.atomic():

            is_taxable = get_bool_int(primary, "is_taxable")
            tax_percent = primary.get("tax_percent") or  0.0
            if not is_taxable:
                is_taxable = 0
                tax_percent = 0.0

            if vendor_id:
                vendor = Vendor.objects.get(id=vendor_id)
            else:
                vendor = Vendor()
            vendor.vendor_code = vendor_code
            vendor.vendor_name = vendor_name
            vendor.vendor_company_name = vendor_company_name
            #new fields 26/2/2026
            vendor.company_acc_no = company_acc_no if company_acc_no else None
            vendor.company_website = primary.get("company_website") or ""
            if hasattr(vendor, "vendor_model"):
                vendor.vendor_model = primary.get("vendor_model") or ""

            #vendor.gst_number = gst_number or None
            vendor.tax_percent = tax_percent
            vendor.is_taxable = is_taxable
            vendor.default_warehouse = primary.get("default_warehouse") or None
            vendor.payment_term = primary.get("payment_term") or None
            vendor.company_acn = primary.get("company_acn") or None
            vendor.company_abn = primary.get("company_abn") or None
            vendor.vendor_locality = primary.get("vendor_locality") or None

            payment_modes = primary.get('mode_of_payment', [])
            if isinstance(payment_modes, list):
                payment_modes = ",".join(payment_modes)

            vendor.mode_of_payment = payment_modes or None #
            if hasattr(vendor, "bank_ifsc"):
                vendor.bank_ifsc = primary.get("bank_ifsc") or None #
            if hasattr(vendor, "first_contact_date"):
                vendor.first_contact_date = onboard_details.get("first_contact_date") or None #
            if hasattr(vendor, "first_contact_via"):
                vendor.first_contact_via = onboard_details.get("first_contact_via") or None #
            if hasattr(vendor, "onboard_date"):
                vendor.onboard_date = onboard_details.get("onboard_date") or None #
            if hasattr(vendor, "onboard_by"):
                vendor.onboard_by = onboard_details.get("onboard_by") or None #
            if hasattr(vendor, "mode_of_contact"):
                vendor.mode_of_contact = onboard_details.get("mode_of_contact") or None
            if hasattr(vendor, "comments"):
                vendor.comments = onboard_details.get("comments") or None

            raw_modes = primary.get("mode_of_payment") or ""

            # 2. அதை லிஸ்ட்டாக மாற்றவும் (அப்போதுதான் 'in' செக் பண்ண முடியும்)
            if isinstance(raw_modes, str):
                mode_list = [m.strip() for m in raw_modes.split(',') if m.strip()]
            else:
                mode_list = raw_modes  # ஒருவேளை ஏற்கனவே லிஸ்ட்டா இருந்தா அப்படியே விட்ரு

            # 3. டேட்டாபேஸில் ஸ்ட்ரிங்காகவே சேமிக்க
            vendor.mode_of_payment = ",".join(mode_list) if mode_list else None

            # --- PAYPAL SECTION ---
            if "paypal" in mode_list:
                vendor.paypal_email = primary.get("paypal_email") or None
                vendor.paypal_merchant_id = primary.get("paypal_merchant_id") or None
                vendor.paypal_environment = primary.get("paypal_environment") or "sandbox"
                vendor.paypal_transaction_fee = primary.get("paypal_transaction_fee") or 0.00
            else:
                vendor.paypal_email = None
                vendor.paypal_merchant_id = None
                vendor.paypal_environment = "sandbox"
                vendor.paypal_transaction_fee = 0.00

            # --- BANK TRANSFER DETAILS ---
            if "bank_transfer" in mode_list:
                bank_data = {
                    "account_holder": primary.get("account_name") or "",
                    "bank_name": primary.get("bank_name") or "",
                    "bank_branch": primary.get("bank_branch") or None,
                    "account_number": str(primary.get("account_number") or ""),
                    "bic": primary.get("bank_ifsc") or "",
                    "bank_country": primary.get("bank_country") or None,
                    "created_by": request.user.id if request.user.is_authenticated else 0
                }
                bank_obj = VendorBank.objects.filter(vendor_id=vendor.id).first()
                if bank_obj:
                    bank_obj.account_holder = bank_data["account_holder"]
                    bank_obj.bank_name = bank_data["bank_name"]
                    bank_obj.bank_branch = bank_data["bank_branch"]
                    bank_obj.account_number = bank_data["account_number"]
                    bank_obj.bic = bank_data["bic"]
                    bank_obj.bank_country = bank_data["bank_country"]
                    bank_obj.save()
                elif any([bank_data["account_holder"], bank_data["bank_name"], bank_data["account_number"], bank_data["bic"], bank_data["bank_branch"], bank_data["bank_country"]]):
                    VendorBank.objects.create(vendor_id=vendor.id, **bank_data)
            else:
                # preserve existing bank records; do not delete history automatically
                pass

            # --- CREDIT CARD DETAILS ---
            if "credit_card" in mode_list:
                vendor.cardholder_name = primary.get("cardholder_name") or None
                vendor.card_last_four = primary.get("card_last_four") or None
                vendor.card_expiry = primary.get("card_expiry") or None
                vendor.accepted_card = primary.get("accepted_card") or None
                vendor.payment_gateway = primary.get("payment_gateway") or None
                vendor.processing_fee = primary.get("processing_fee") or 0.00
                vendor.three_d_secure = primary.get("three_d_secure") or "no"
            else:
                vendor.cardholder_name = None
                vendor.card_last_four = None
                vendor.card_expiry = None
                vendor.accepted_card = None
                vendor.payment_gateway = None
                vendor.processing_fee = 0.00
                vendor.three_d_secure = "no"

            # --- WALLET SECTION ---
            if "wallet" in mode_list:
                # wallet_type-ம் ஸ்ட்ரிங்கா வர வாய்ப்பிருக்கு, அதனால அப்படியே சேமிக்கலாம்
                vendor.wallet_type = primary.get("wallet_type") or None
                vendor.auto_detect_invoice = primary.get("auto_detect_invoice") or "no"
                vendor.allow_negative_balance = primary.get("allow_negative_balance") or "no"
                vendor.minimum_wallet_balance = primary.get("minimum_wallet_balance") or 0.00
                vendor.low_balance_email = primary.get("low_balance_email") or None
            else:
                vendor.wallet_type = None
                vendor.auto_detect_invoice = "no"
                vendor.allow_negative_balance = "no"
                vendor.minimum_wallet_balance = 0.00
                vendor.low_balance_email = None

            vendor.paypal_notes = primary.get("paypal_notes") or None
            vendor.credit_card_notes = primary.get("credit_card_notes") or None
            vendor.wallet_notes = primary.get("wallet_notes") or None

            vendor.currency = primary.get("currency") or None
            vendor.status = primary.get("status") or 0
            vendor.min_order_value = primary.get("min_order_value") or None
            vendor.save()

            if details.get("billing_address"):
                save_address(
                    details["billing_address"],
                    "billing",
                    vendor.id,
                    "API",
                    int(request.user.id)
                )

            if details.get("shipping_address"):
                save_address(
                    details["shipping_address"],
                    "shipping",
                    vendor.id,
                    "API",
                    int(request.user.id)
                )

        return JsonResponse({
            "status": True,
            "vendor_id": vendor.id
        })

    except Vendor.DoesNotExist:
        return JsonResponse({
            "status": False,
            "message": "Invalid vendor details"
        }, status=404)

    except Exception as e:
        return JsonResponse({
            "status": False,
            "message": "Error in vendor update",
            "detail": str(e)
        }, status=500)

def save_address(request, address_type, vendor_id, method="POST", user_id=1):
    try:
        # Find an existing address relation for the given vendor and address type
        relation = VendorAddress.objects.filter(
            vendor_id=vendor_id,
            address_type=address_type
        ).first()

        # If an existing relation is found, load the associated address object
        if relation:
            address_obj = Addresses.objects.filter(id=relation.address_id).first()
            if not address_obj:
                address_obj = Addresses()
                is_new = True
            else:
                is_new = False
        else:
            address_obj = Addresses()
            is_new = True

        # Determine request data source for form or JSON payloads
        if hasattr(request, "POST"):
            source = request.POST
            field_prefix = f"{address_type}_"
        else:
            source = request
            field_prefix = ""

        def get_value(key):
            value = source.get(field_prefix + key)
            if value is None and field_prefix:
                value = source.get(key)
            return (value or "").strip() if isinstance(value, str) else (value or "")

        address_obj.attention_name = get_value("attention_name")
        address_obj.street1 = get_value("street1")
        address_obj.street2 = get_value("street2")
        address_obj.city = get_value("city")
        address_obj.zip = get_value("zip")
        address_obj.phone = get_value("phone")
        address_obj.fax = get_value("fax")

        country_id = get_value("country")
        state_id = get_value("state")

        # Safe lookup for country
        try:
            address_obj.country = Country.objects.get(id=country_id) \
                if country_id not in [None, "", "0", "undefined"] else None
        except Country.DoesNotExist:
            address_obj.country = None

        # Safe lookup for state
        try:
            address_obj.state = State.objects.get(id=state_id) \
                if state_id not in [None, "", "0", "undefined"] else None
        except State.DoesNotExist:
            address_obj.state = None

        address_obj.created_by = user_id
        address_obj.save()

        if is_new:
            VendorAddress.objects.create(
                vendor_id=vendor_id,
                address_id=address_obj.id,
                address_type=address_type,
                created_by=user_id
            )

        return True

    except Exception as e:
        raise Exception(f"Address save failed: {str(e)}")

def extract_bank_details(request):
    banks = []
    index = 0

    while True:
        prefix = f"banks[{index}]"

        # Exit loop if row does not exist
        if f"{prefix}[account_holder]" not in request.POST:
            break

        banks.append({
            "id": request.POST.get(f"{prefix}[id]"),
            "account_holder": request.POST.get(f"{prefix}[account_holder]", "").strip(),
            "bank_name": request.POST.get(f"{prefix}[bank_name]", "").strip(),
            "account_number": request.POST.get(f"{prefix}[account_number]", "").strip(),
            "account_number_confirm": request.POST.get(f"{prefix}[account_number_confirm]", "").strip(),
            "bic": request.POST.get(f"{prefix}[bic]", "").strip(),
        })

        index += 1

    return banks

def extract_contacts(request):
    contacts = []
    index = 0

    while True:
        prefix = f"contacts[{index}]"

        # Stop if contact is missing
        if not request.POST.get(f"{prefix}[first_name]"):
            break

        contacts.append({
            "department": request.POST.get(f"{prefix}[department]"),
            "email": request.POST.get(f"{prefix}[email]"),
            "phone": request.POST.get(f"{prefix}[phone]"),
            "first_name": request.POST.get(f"{prefix}[first_name]"),
            "last_name": request.POST.get(f"{prefix}[last_name]"),
            "description": request.POST.get(f"{prefix}[description]"),
            "role": request.POST.get(f"{prefix}[role]"),
        })

        index += 1

    return contacts

@api_view(["POST"])
def add_newvendor_contact(request, vendor_id):
    data = request.data
    if not vendor_id:
        return JsonResponse({"status": False, "message": "Required fields missing"})
    print(data)
    if not data.get("first_name") and not data.get("last_name"):
        return JsonResponse({"status":False, "message":"Required fields missing"})

    VendorContact.objects.create(
        vendor_id=vendor_id,
        department=data.get("department"),
        email=data.get("email"),
        phone=data.get("phone"),
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        description=data.get("description"),
        role=data.get("role"),
        created_by = request.user.id if request.user.is_authenticated else None
    )

    return JsonResponse({"status":True, "message":"Contact created successfully"})

@api_view(["POST"])
def update_vendor_contact(request, contact_id):
    data = request.data
    if not contact_id:
        return JsonResponse({"status": False, "message": "Required fields missing"})

    if not data.get("first_name") and not data.get("last_name"):
        return JsonResponse({"status": False, "message": "Required fields missing"})

    vendor_contact = VendorContact.objects.get(id=contact_id)
    vendor_contact.department = data.get("department")
    vendor_contact.email = data.get("email")
    vendor_contact.phone = data.get("phone")
    vendor_contact.first_name = data.get("first_name")
    vendor_contact.last_name = data.get("last_name")
    vendor_contact.description = data.get("description")
    #vendor_contact.role = data.get("role")
    vendor_contact.save()
    return JsonResponse({"status": True, "message": "Contact updated successfully"})

@api_view(["POST"])
def update_vendor_bank(request, bank_id):
    if not bank_id:
        return JsonResponse({"status": False, "message": "Required fields missing"})
    data = request.data
    if not data.get("account_number") and not data.get("account_holder"):
        return JsonResponse({"status": False, "message": "Required fields missing"})

    vendor_bank = VendorBank.objects.get(id=bank_id)
    vendor_bank.account_holder = data.get("account_holder")
    vendor_bank.bank_name = data.get("bank_name")
    vendor_bank.account_number = str(data.get("account_number") or "")
    vendor_bank.bic = data.get("bic")
    vendor_bank.save()
    return JsonResponse({"status": True, "message": "Bank details updated successfully"})

from django.core import serializers as core_serializers
from store_admin.serializers.common_serializers import VendorContactSerializer, VendorBankSerializer
from store_admin.serializers.payment_serializers import VendorPaymentLogSerializer, VendorPaymentLogItemSerializer


def get_all_vendor_contacts(request,vendor_id):
    if vendor_id == None:
        return JsonResponse({"status": False, "message": "Required fields missing"})
    else:
        contacts_queryset = VendorContact.objects.filter(vendor_id=vendor_id)
        serialized_data = VendorContactSerializer(contacts_queryset, many=True)
        return JsonResponse({"status": True, "data": serialized_data.data})


def get_single_vendor_contact(request, vendor_id, contact_id):
    if vendor_id == None:
        return JsonResponse({"status": False, "message": "Required fields missing"})
    else:
        contacts_queryset = VendorContact.objects.filter(vendor_id=vendor_id, id=contact_id).first()
        serialized_data = VendorContactSerializer(contacts_queryset)
        return JsonResponse({"status": True, "data": serialized_data.data})


def delete_vendor_contact(request, contact_id, vendor_id):
    try:
        obj = VendorContact.objects.filter(id=contact_id,vendor_id=vendor_id).first()
        if not obj:
            return JsonResponse({"status": False, "message": "Contact not found"})

        obj.delete()
        return JsonResponse({"status": True, "message": "Contact deleted"})
    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)})

@api_view(["DELETE"])
def delete_vendor(request, vendor_id):
    if request.method != "DELETE":
        return JsonResponse({"status": False, "message": "Invalid request method"}, status=400)
    vendor = Vendor.objects.filter(id=vendor_id).first()
    #clear vendor address
    #clear address details
    #clear address section
    #clear vendor contact
    #option to implement archieve option

    if not vendor:
        return JsonResponse({"status": False, "message": "Vendor not found"}, status=404)

    try:
        with transaction.atomic():
            VendorBank.objects.filter(vendor_id=vendor_id).delete()
            VendorContact.objects.filter(vendor_id=vendor_id).delete()

            Addresses.objects.filter(id__in=VendorAddress.objects.filter(
                vendor_id=vendor_id
            ).values_list('address_id', flat=True)).delete()

            if PurchaseOrder.objects.filter(vendor_id=vendor_id).exists():
                return JsonResponse({"status": False, "message": "This Vendor has Purchase Orders, Can not delete this vendor", "error":"Vendor has PO"})

            VendorAddress.objects.filter(vendor_id=vendor_id).delete()
            vendor.delete()

        return JsonResponse({"status": True, "message": "Vendor deleted successfully"})
    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)}, status=500)

from django.http import JsonResponse
import json

def delete_vendors_bulk(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"})

    data = json.loads(request.body)
    ids = data.get("ids", [])

    if not ids:
        return JsonResponse({"status": "error", "message": "No vendors selected"})

    with transaction.atomic():
        Vendor.objects.filter(id__in=ids).delete()
        VendorBank.objects.filter(vendor_id__in=ids).delete()
        VendorContact.objects.filter(vendor_id__in=ids).delete()
        address_ids = VendorAddress.objects.filter(
            vendor_id__in=ids
        ).values_list('address_id', flat=True)
        Addresses.objects.filter(id__in=address_ids).delete()
        VendorAddress.objects.filter(vendor_id__in=ids).delete()

    return JsonResponse({"status": "success", "deleted": len(ids)})


def delete_vendor_bank(request, bank_id, vendor_id):
    try:
        obj = VendorBank.objects.filter(id=bank_id,vendor_id=vendor_id).first()
        if not obj:
            return JsonResponse({"status": False, "message": "Bank details not found"})

        obj.delete()
        return JsonResponse({"status": True, "message": "Bank details deleted"})
    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)})



#vnew vendor bank details

def get_all_vendor_banks(request, vendor_id):
    # Filter by the integer vendor_id
    banks_queryset = VendorBank.objects.filter(vendor_id=vendor_id)

    # Use the serializer with many=True for a list of objects
    serializer = VendorBankSerializer(banks_queryset, many=True)

    return JsonResponse({"status": True, "data": serializer.data})


@api_view(["POST"])
def add_new_vendor_bank(request, vendor_id):
    data = request.data

    # Ensure the vendor_id is explicitly set from the URL argument
    data['vendor_id'] = vendor_id
    # Set created_by if needed (e.g., current user's ID)
    data['created_by'] = request.user.id if request.user.is_authenticated else 0
    # Ensure account_number is always a string
    data['account_number'] = str(data.get('account_number') or "")

    serializer = VendorBankSerializer(data=data)

    if serializer.is_valid():
        serializer.save()
        return JsonResponse({"status": True, "message": "Bank details added successfully."})
    else:
        # Return detailed error messages from the serializer
        return JsonResponse({"status": False, "message": serializer.errors})




def get_single_vendor_bank(request, vendor_id, bank_id):
    if vendor_id == None or bank_id is None:
        return JsonResponse({"status": False, "message": "Required fields missing"})
    else:
        contacts_queryset = VendorBank.objects.filter(vendor_id=vendor_id, id=bank_id).first()
        serialized_data = VendorBankSerializer(contacts_queryset)
        return JsonResponse({"status": True, "data": serialized_data.data})


def vendor_api_lists(request):
    """
    Returns a JSON list of all vendors.
    Adjust the fields as needed to match your frontend requirements.
    """
    vendors = Vendor.objects.all().values(
    'id',
    'vendor_name',         # instead of 'name'
    'vendor_company_name', # optional
    'vendor_locality',     # instead of 'email' or 'phone' maybe?
    'status'
)
    return JsonResponse(list(vendors), safe=False)