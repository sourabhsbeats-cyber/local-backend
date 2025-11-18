from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseBadRequest

from store_admin.models import Country, State
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.vendor_models import Vendor, VendorBank, VendorContact, VendorAddress
from store_admin.models.address_model import Addresses
from django.db import transaction
from django.db.models import Min
from django.db.models import Value as V
from django.db.models.functions import Concat


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
        id=Min('id'),  # pick country with smallest ID per currency
        currency_name=Min('currency_name')
    )
    countries_list = Country.objects.values('name','id')

    billing_rel = VendorAddress.objects.filter(vendor_id=vendor.id, address_type="billing").first()
    billing_address =  Addresses.objects.filter(id=billing_rel.address_id).first() if billing_rel else None
    shipping_rel = VendorAddress.objects.filter(vendor_id=vendor.id, address_type="shipping").first()
    shipping_address = Addresses.objects.filter(id=shipping_rel.address_id).first() if shipping_rel else None

    bank_details = VendorBank.objects.filter(vendor_id=vendor.id)
    contact_details = VendorContact.objects.filter(vendor_id=vendor.id)
    context = {
        'vendor': vendor,
        'payment_terms': payment_terms,
        'countries_list': countries_list,
        'billing': billing_address,
        'shipping': shipping_address,
        'banks': bank_details,
        'contacts': contact_details,
        'currency_list':currency_list
    }
    return render(request, 'sbadmin/pages/vendor/edit_vendor.html', context)

@login_required
def all_vendors(request):
    payment_terms = PaymentTerm.objects.all()
    countries_list = Country.objects.values('currency').annotate(
        id=Min('id'),  # pick country with smallest ID per currency
        currency_name=Min('currency_name')
    )
    currency_list = Country.objects.values('currency').annotate(
        id=Min('id'),  # pick country with smallest ID per currency
        currency_name=Min('currency_name')
    )
    allvendors = Vendor.objects.annotate(
        name=Concat(
            'salutation', V(' '),
            'first_name', V(' '),
            'last_name'
        )
    ).values('id', 'name', 'company_name', 'email_address', 'vendor_code', 'work_phone')
    # context = locals()
    context = {
        'user': request.user.id,
        'payment_terms': payment_terms,
        'countries_list': countries_list,
        'currency_list':currency_list,
        'allvendors': allvendors
    }
    print(allvendors)

    return render(request, 'sbadmin/pages/vendor/all_listing.html', context)


@csrf_exempt
@login_required
def save_vendor(request):
    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid request"}, status=400)

    action_type = request.POST.get('delete_vendor', None)
    vendor_id = request.POST.get("vendor_id")

    try:
        sid = transaction.savepoint()
        with (transaction.atomic()):   #  ROLLBACK STARTS HERE
            if vendor_id:
                vendor = Vendor.objects.get(id=vendor_id)
            else:
                vendor = Vendor()

            vendor.salutation = request.POST.get("saluation")
            vendor.first_name = request.POST.get("first_name")
            vendor.last_name = request.POST.get("last_name")
            vendor.company_name = request.POST.get("company_name")
            vendor.display_name = request.POST.get("display_name")
            vendor.vendor_code = request.POST.get("vendor_code")
            vendor.email_address = request.POST.get("email_address")
            vendor.work_phone = request.POST.get("work_phone")
            vendor.mobile_number = request.POST.get("mobile_number")
            vendor.registered_business = bool(request.POST.get("registeredBusiness"))
            vendor.company_abn = request.POST.get("company_abn")
            vendor.company_acn = request.POST.get("company_acn")
            vendor.currency = request.POST.get("currency")
            vendor.vendor_remarks = request.POST.get("vendor_remarks")
            vendor.created_by = request.user.id
            vendor.status = 1

            if request.POST.get("payment_term"):
                vendor.payment_term = PaymentTerm.objects.get(id=int(request.POST["payment_term"]))

            if request.FILES.get("documents"):
                vendor.documents = request.FILES["documents"]

            vendor.save()

            #return JsonResponse({"status": True, "vendor_id": vendor.id})
            #{"status": true, "vendor_id": 20}
            if request.POST["billing_country"]:
                status = save_address(request, "billing", vendor.id)
                #billing_relation.address = billing_address
                #billing_relation.save()

            if request.POST["shipping_country"]:
                status = save_address(request, "shipping", vendor.id)
                #shipping_relation.address = shipping_address
                #shipping_relation.save()

            # --- CONTACT DETAILS SAVE ---
            contacts = extract_contacts(request)
            active_contact_ids = []
            for c in contacts:
                # Skip blank rows
                if not c["first_name"] and not c["last_name"]:
                    continue
                contact_id = c.get("id")

                if contact_id is not None:  # UPDATE existing contact
                    con = VendorContact.objects.filter(id=contact_id, vendor_id=vendor.id).first()
                    if con:
                        con.department = c["department"]
                        con.email = c["email"]
                        con.phone = c["phone"]
                        con.first_name = c["first_name"]
                        con.last_name = c["last_name"]
                        con.description = c["description"]
                        con.created_by = request.user.id
                        con.save()
                        active_contact_ids.append(con.id)
                        continue

                # CREATE new contact
                new_con = VendorContact.objects.create(
                    vendor_id=vendor.id,
                    department=c["department"],
                    email=c["email"],
                    phone=c["phone"],
                    first_name=c["first_name"],
                    last_name=c["last_name"],
                    description=c["description"],
                    created_by=request.user.id
                )
                active_contact_ids.append(new_con.id)
            # DELETE removed contacts
            VendorContact.objects.filter(vendor_id=vendor.id).exclude(id__in=active_contact_ids).delete()

            #BANK Details
            bank_details = extract_bank_details(request)
            active_ids = []
            for b in bank_details:
                # Skip empty record
                if not b["account_holder"] and not b["bank_name"]:
                    continue

                # Validate account numbers
                if b["account_number"] != b["account_number_confirm"]:
                    return JsonResponse(
                        {"status": False, "message": "Account number mismatch"},
                        status=400
                    )

                bank_id = b.get("id")
                if bank_id and str(bank_id).isdigit():
                    bank = VendorBank.objects.filter(id=bank_id, vendor_id=vendor.id).first()
                    if bank:
                        bank.account_holder = b["account_holder"]
                        bank.bank_name = b["bank_name"]
                        bank.account_number = b["account_number"]
                        bank.bic = b["bic"]
                        bank.created_by = request.user.id
                        bank.save()
                        active_ids.append(bank.id)
                        continue

                new_bank = VendorBank.objects.create(
                    vendor_id=vendor.id,
                    account_holder=b["account_holder"],
                    bank_name=b["bank_name"],
                    account_number=b["account_number"],
                    bic=b["bic"],
                    created_by=request.user.id
                )
                active_ids.append(new_bank.id)

            VendorBank.objects.filter(vendor_id=vendor.id).exclude(id__in=active_ids).delete()
            #EOF Bank details

        return JsonResponse({"status": True, "vendor_id": vendor.id})

    except Exception as e:
        return JsonResponse({
            "status": False,
            "message": "Error in vendor create",
            "detail": str(e)
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
        })

        index += 1

    return contacts


@login_required
def delete_vendor_contact(request, contact_id):
    try:
        obj = VendorContact.objects.filter(id=contact_id).first()
        if not obj:
            return JsonResponse({"status": False, "message": "Contact not found"})

        obj.delete()
        return JsonResponse({"status": True, "message": "Contact deleted"})
    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)})



@login_required
def delete_vendor_bank(request, bank_id):
    try:
        obj = VendorBank.objects.filter(id=bank_id).first()
        if not obj:
            return JsonResponse({"status": False, "message": "Bank details not found"})

        obj.delete()
        return JsonResponse({"status": True, "message": "Bank details deleted"})
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
        vendor.delete()
        return JsonResponse({"status": True, "message": "Vendor deleted successfully"})
    except Exception as e:
        return JsonResponse({"status": False, "message": str(e)}, status=500)
