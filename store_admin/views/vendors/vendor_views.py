from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from store_admin.models import Country, State
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.vendor_models import Vendor, VendorBank, VendorContact, VendorAddress
from store_admin.models.address_model import Addresses
from django.db import transaction
from django.db.models import Min
from django.db.models import Value as V
from django.db.models.functions import Concat
from django.db.models import Min, Value as V
from django.db.models.functions import Concat
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.validators import validate_email

@login_required
def add_new_vendor(request):
    payment_terms = PaymentTerm.objects.all()
    currency_list = Country.objects.values('currency').annotate(
                        id=Min('id'),  # pick country with smallest ID per currency
                        currency_name=Min('currency_name')
                    )
    countries_list = Country.objects.values('name','id')

    # context = locals()
    context = {
        'user': request.user.id,
        'payment_terms': payment_terms,
        'countries_list': countries_list,
        'currency_list':currency_list
    }
    return render(request, 'sbadmin/pages/vendor/add_new.html', context)

@login_required
def edit_vendor(request, vendor_id):
    vendor = get_object_or_404(Vendor, id=vendor_id)

    payment_terms = PaymentTerm.objects.all()
    currency_list = Country.objects.values('currency').annotate(
        id=Min('id'),
        currency_name=Min('currency_name')
    )
    countries_list = Country.objects.values('name', 'id')

    # ------------------- BILLING ---------------------
    billing_rel = VendorAddress.objects.filter(
        vendor_id=vendor.id, address_type="billing"
    ).first()

    billing_address = (
        Addresses.objects.select_related("country", "state")
        .filter(id=billing_rel.address_id).first()
        if billing_rel else None
    )

    billing_country_id = billing_address.country_id if billing_address else None
    billing_state_id = billing_address.state_id if billing_address else None
    billing_state_list = (
        State.objects.filter(country_id=billing_country_id)
        if billing_country_id else []
    )

    billing_state_name = billing_address.state.name if billing_address and billing_address.state else ""


    # ------------------- SHIPPING ---------------------
    shipping_rel = VendorAddress.objects.filter(
        vendor_id=vendor.id, address_type="shipping"
    ).first()

    shipping_address = (
        Addresses.objects.select_related("country", "state")
        .filter(id=shipping_rel.address_id).first()
        if shipping_rel else None
    )

    shipping_country_id = shipping_address.country_id if shipping_address else None
    shipping_state_id = shipping_address.state_id if shipping_address else None
    shipping_state_list = (
        State.objects.filter(country_id=shipping_country_id)
        if shipping_country_id else []
    )

    shipping_state_name = shipping_address.state.name if shipping_address and shipping_address.state else ""


    # ------------------- BANK / CONTACT ---------------------
    bank_details = VendorBank.objects.filter(vendor_id=vendor.id)
    contact_details = VendorContact.objects.filter(vendor_id=vendor.id)


    context = {
        'vendor': vendor,
        'payment_terms': payment_terms,
        'countries_list': countries_list,
        'currency_list': currency_list,

        'billing': billing_address,
        'billing_state_list': billing_state_list,
        'billing_state_name': billing_state_name,   # ⬅️ new

        'shipping': shipping_address,
        'shipping_state_list': shipping_state_list,
        'shipping_state_name': shipping_state_name, # ⬅️ new

        'banks': bank_details,
        'contacts': contact_details,
    }

    return render(request, 'sbadmin/pages/vendor/edit_vendor.html', context)

@login_required
def all_vendors(request):
    payment_terms = PaymentTerm.objects.all()

    countries_list = Country.objects.values('currency').annotate(
        id=Min('id'),
        currency_name=Min('currency_name')
    )

    currency_list = Country.objects.values('currency').annotate(
        id=Min('id'),
        currency_name=Min('currency_name')
    )

    search_query = request.GET.get("q", "").strip()

    # Base queryset
    vendors = Vendor.objects.annotate(
        name=Concat(
            'salutation', V(' '),
            'first_name', V(' '),
            'last_name'
        )
    ).values(
        'id', 'name', 'company_name',
        'email_address', 'vendor_code',
        'work_phone'
    ).order_by('id')

    # Searching support
    if search_query:
        vendors = vendors.filter(
            Q(name__icontains=search_query) |
            Q(company_name__icontains=search_query) |
            Q(email_address__icontains=search_query) |
            Q(vendor_code__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(vendors, 10)  # 10 rows per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        'user': request.user.id,
        'payment_terms': payment_terms,
        'countries_list': countries_list,
        'currency_list': currency_list,
        'allvendors': page_obj.object_list,  # Data for table
        'page_obj': page_obj,  # Data for pagination
        'search_query': search_query,
    }

    return render(request, 'sbadmin/pages/vendor/all_listing.html', context)

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

        return JsonResponse({
            "status": True,
            "data": vendor
        })

    except Vendor.DoesNotExist:
        return JsonResponse({
            "status": False,
            "message": "Vendor not found"
        }, status=404)

import re
import ast

@login_required
def save_vendor(request):
    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid request"}, status=400)

    action_type = request.POST.get('action_type', None)
    vendor_id = request.POST.get("vendor_id")

    vendor_code = request.POST.get("vendor_code").strip()
    vendor_email = request.POST.get("email_address").strip()

    if action_type != "update":
        if Vendor.objects.filter(vendor_code=vendor_code).exists():
            return JsonResponse({
                "status": False,
                "message": f"Vendor code already exists",
            }, status=500)

    if action_type != "update":
        if Vendor.objects.filter(email_address=vendor_email).exists():
            return JsonResponse({
                "status": False,
                "message": f"Vendor email already exists",
            }, status=500)

    work_phone = request.POST.get("work_phone").strip()
    mobile_number = request.POST.get("mobile_number").strip()

    errors = []

    if work_phone and not re.fullmatch(r'\+?\d{6,15}', work_phone):
        errors.append("Invalid work phone")

    if mobile_number and not re.fullmatch(r'\+?\d{6,15}', mobile_number):
        errors.append("Invalid mobile number")

    if errors:
        return JsonResponse({"status": False, "message": ", ".join(errors)}, status=400)


    try:
        validate_email(vendor_email)
    except ValidationError:
        return JsonResponse({
            "status": False,
            "message": "Invalid vendor email format"
        }, status=500)

    try:
        sid = transaction.savepoint()
        with (transaction.atomic()):   #  ROLLBACK STARTS HERE
            if vendor_id:
                vendor = Vendor.objects.get(id=vendor_id)
            else:
                vendor = Vendor()
            vendor.vendor_type = request.POST.get("vendor_type")
            vendor.salutation = request.POST.get("saluation")
            vendor.first_name = request.POST.get("first_name")
            vendor.last_name = request.POST.get("last_name")
            vendor.company_name = request.POST.get("company_name")
            vendor.display_name = request.POST.get("display_name")

            if action_type != "update":
                vendor.vendor_code = request.POST.get("vendor_code")

            vendor.email_address = request.POST.get("email_address")
            vendor.work_phone = request.POST.get("work_phone")
            vendor.mobile_number = request.POST.get("mobile_number")
            vendor.registered_business = bool(request.POST.get("registeredBusiness"))
            vendor.company_abn = request.POST.get("company_abn")
            vendor.company_acn = request.POST.get("company_acn")
            vendor.currency = request.POST.get("currency")
            vendor.vendor_remarks = request.POST.get("vendor_remarks")
            vendor.payment_method = request.POST.get("payment_method")
            vendor.created_by = request.user.id
            vendor.status = 1
            if request.POST.get("payment_term"):
                vendor.payment_term = PaymentTerm.objects.get(id=int(request.POST["payment_term"]))
            if request.FILES.get("documents"):
                vendor.documents = request.FILES["documents"]
            vendor.full_clean()
            vendor.save()
            if request.POST["billing_country"]:
                status = save_address(request, "billing", vendor.id)

            if request.POST["shipping_country"]:
                status = save_address(request, "shipping", vendor.id)

        return JsonResponse({"status": True, "vendor_id": vendor.id})

    except Exception as e:
        error_text = str(e)
        try:
            error_dict = ast.literal_eval(error_text)
        except:
            error_dict = {"error": error_text}

        alias = {
            "first_name": "First Name",
            "last_name": "Last Name"
        }
        formatted_errors = {alias.get(k, k): v for k, v in error_dict.items()}
        return JsonResponse({
            "status": False,
            "message": "Error in vendor create - "+str(formatted_errors),
            "detail": formatted_errors
        }, status=500)

def save_address(request, type, vendor_id):
    try:
        field_prefix = f"{type}_"

        relation = VendorAddress.objects.filter(
            vendor_id=vendor_id,
            address_type=type
        ).first()

        if relation:
            address_obj = Addresses.objects.get(id=relation.address_id)
            is_new = False
        else:
            address_obj = Addresses()
            is_new = True

        address_obj.attention_name = request.POST.get(field_prefix + "attention_name")
        address_obj.street1 = request.POST.get(field_prefix + "street1")
        address_obj.street2 = request.POST.get(field_prefix + "street2")
        address_obj.city = request.POST.get(field_prefix + "city")
        address_obj.zip = request.POST.get(field_prefix + "zip")
        address_obj.phone = request.POST.get(field_prefix + "phone")
        address_obj.fax = request.POST.get(field_prefix + "fax")

        country_id = request.POST.get(field_prefix + "country")
        state_id = request.POST.get(field_prefix + "state")

        address_obj.country = Country.objects.get(id=country_id) if country_id else None
        address_obj.state = State.objects.get(id=state_id) if state_id else None

        address_obj.created_by = request.user.id
        address_obj.save()

        if is_new:
            VendorAddress.objects.create(
                vendor_id=vendor_id,
                address_id=address_obj.id,
                address_type=type,
                created_by=request.user.id
            )

        return True
    except Exception as e:
        raise e

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

@login_required
def add_newvendor_contact(request, vendor_id):
    if request.method == "POST":
        if not vendor_id:
            return JsonResponse({"status": False, "message": "Required fields missing"})

        if not request.POST.get("first_name") and not request.POST.get("last_name"):
            return JsonResponse({"status":False, "message":"Required fields missing"})

        VendorContact.objects.create(
            vendor_id=vendor_id,
            department=request.POST.get("department"),
            email=request.POST.get("email"),
            phone=request.POST.get("phone"),
            first_name=request.POST.get("first_name"),
            last_name=request.POST.get("last_name"),
            description=request.POST.get("description"),
            role=request.POST.get("role"),
            created_by=request.user.id
        )

    return JsonResponse({"status":True, "message":"Contact created successfully"})

def update_vendor_contact(request, contact_id):
    if request.method == "POST":
        if not contact_id:
            return JsonResponse({"status": False, "message": "Required fields missing"})

        if not request.POST.get("first_name") and not request.POST.get("last_name"):
            return JsonResponse({"status": False, "message": "Required fields missing"})

        vendor_contact = VendorContact.objects.get(id=contact_id)
        vendor_contact.department = request.POST.get("department")
        vendor_contact.email = request.POST.get("email")
        vendor_contact.phone = request.POST.get("phone")
        vendor_contact.first_name = request.POST.get("first_name")
        vendor_contact.last_name = request.POST.get("last_name")
        vendor_contact.description = request.POST.get("description")
        vendor_contact.role = request.POST.get("role")
        vendor_contact.save()
    return JsonResponse({"status": True, "message": "Contact updated successfully"})

@login_required
def update_vendor_bank(request, bank_id):
    if request.method == "POST":
        if not bank_id:
            return JsonResponse({"status": False, "message": "Required fields missing"})

        if not request.POST.get("account_number") and not request.POST.get("account_holder"):
            return JsonResponse({"status": False, "message": "Required fields missing"})

        vendor_bank = VendorBank.objects.get(id=bank_id)
        vendor_bank.account_holder = request.POST.get("account_holder")
        vendor_bank.bank_name = request.POST.get("bank_name")
        vendor_bank.account_number = request.POST.get("account_number")
        vendor_bank.bic = request.POST.get("bic")
        vendor_bank.save()
    return JsonResponse({"status": True, "message": "Bank details updated successfully"})

from django.core import serializers as core_serializers
from store_admin.models.serializers.common_serializers import VendorContactSerializer, VendorBankSerializer


@login_required
def get_all_vendor_contacts(request,vendor_id):
    if vendor_id == None:
        return JsonResponse({"status": False, "message": "Required fields missing"})
    else:
        contacts_queryset = VendorContact.objects.filter(vendor_id=vendor_id)
        serialized_data = VendorContactSerializer(contacts_queryset, many=True)
        return JsonResponse({"status": True, "data": serialized_data.data})

@login_required
def get_single_vendor_contact(request, vendor_id, contact_id):
    if vendor_id == None:
        return JsonResponse({"status": False, "message": "Required fields missing"})
    else:
        contacts_queryset = VendorContact.objects.filter(vendor_id=vendor_id, id=contact_id).first()
        serialized_data = VendorContactSerializer(contacts_queryset)
        return JsonResponse({"status": True, "data": serialized_data.data})

@login_required
def delete_vendor_contact(request, contact_id, vendor_id):
    try:
        obj = VendorContact.objects.filter(id=contact_id,vendor_id=vendor_id).first()
        if not obj:
            return JsonResponse({"status": False, "message": "Contact not found"})

        obj.delete()
        return JsonResponse({"status": True, "message": "Contact deleted"})
    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)})

@login_required
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


            VendorAddress.objects.filter(vendor_id=vendor_id).delete()
            vendor.delete()

        return JsonResponse({"status": True, "message": "Vendor deleted successfully"})
    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)}, status=500)

from django.http import JsonResponse
import json
@login_required
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

@login_required
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
@login_required
def get_all_vendor_banks(request, vendor_id):
    # Filter by the integer vendor_id
    banks_queryset = VendorBank.objects.filter(vendor_id=vendor_id)

    # Use the serializer with many=True for a list of objects
    serializer = VendorBankSerializer(banks_queryset, many=True)

    return JsonResponse({"status": True, "data": serializer.data})


@login_required
def add_new_vendor_bank(request, vendor_id):
    if request.method == "POST":
        data = request.POST.copy()

        # Ensure the vendor_id is explicitly set from the URL argument
        data['vendor_id'] = vendor_id
        # Set created_by if needed (e.g., current user's ID)
        data['created_by'] = request.user.id if request.user.is_authenticated else 0

        serializer = VendorBankSerializer(data=data)

        if serializer.is_valid():
            serializer.save()
            return JsonResponse({"status": True, "message": "Bank details added successfully."})
        else:
            # Return detailed error messages from the serializer
            return JsonResponse({"status": False, "message": serializer.errors})

    return JsonResponse({"status": False, "message": "Only POST method supported."}, status=405)


@login_required
def get_single_vendor_bank(request, vendor_id, bank_id):
    if vendor_id == None or bank_id is None:
        return JsonResponse({"status": False, "message": "Required fields missing"})
    else:
        contacts_queryset = VendorBank.objects.filter(vendor_id=vendor_id, id=bank_id).first()
        serialized_data = VendorBankSerializer(contacts_queryset)
        return JsonResponse({"status": True, "data": serialized_data.data})
