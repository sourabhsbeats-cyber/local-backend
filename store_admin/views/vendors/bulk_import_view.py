from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from store_admin.models import Country, State
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.vendor_models import Vendor, VendorBank, VendorContact, VendorAddress
from store_admin.models.address_model import Addresses
from django.db import transaction
from django.db.models import Min
from django.db.models import Value as V
from django.db.models.functions import Concat
from django.conf import settings

from django.http import FileResponse, Http404
import os
import pandas as pd
import csv
import re
from datetime import datetime
from openpyxl import load_workbook
from django.contrib.auth.decorators import login_required
from openpyxl import load_workbook  # pip install openpyxl
from django.conf import settings
from django.http import HttpResponseBadRequest
from django.urls import reverse
from urllib.parse import urlencode
from django.utils.safestring import mark_safe
from django.db.models import Q

def to_str(val):
    if val is None or pd.isna(val):
        return ""
    clean_val = str(val)
    # 1. Replace non-breaking space (often imported from Excel/web)
    clean_val = clean_val.replace('\xa0', ' ')
    # 2. Use strip() to remove all leading/trailing whitespace
    return clean_val.strip()

def validate_field(field, value, rules):
    if rules.get("required") and (value is None or value == ""):
        return f"{field} is required."

    if value == "" or value is None:
        return None  # Skip further checks for optional fields

    if rules["type"] == "str":
        if "max" in rules and len(value) > rules["max"]:
            return f"{field} exceeds max length {rules['max']}."

    elif rules["type"] == "int":
        if not str(value).isdigit():
            return f"{field} must be an integer."

    elif rules["type"] == "bool":
        if str(value).lower() not in ["0", "1", "yes", "no", "true", "false"]:
            return f"{field} must be boolean (0/1, yes/no)."

    elif rules["type"] == "email":
        if not re.match(r"[^@]+@[^@]+\.[^@]+", value):
            return f"{field} must be a valid email."

    return None  # No errors

def validate_vendor_row(row_dict):
    errors = {}
    for field, rules in vendor_field_schema.items():
        value = row_dict.get(field)
        error = validate_field(field, value, rules)
        if error:
            errors[field] = error
    return errors

VALID_EXTENSIONS = ["csv", "xlsx"] #"tsv",
vendor_field_schema = {
    "VendorType":               {"type": "str",   "max": 50,  "required": False},
    "Salutation":               {"type": "str",   "max": 20,  "required": False},
    "FirstName":                {"type": "str",   "max": 100, "required": True},
    "LastName":                 {"type": "str",   "max": 100, "required": False},
    "CompanyName":              {"type": "str",   "max": 255, "required": False},
    "CompanyType":              {"type": "str",   "max": 100, "required": False},
    "DisplayName":              {"type": "str",   "max": 255, "required": False},
    "VendorCode":               {"type": "str",   "max": 50,  "required": False},   # auto-generated if missing
    "Email":                    {"type": "email", "max": 255, "required": False},
    "WorkPhone":                {"type": "str",   "max": 50,  "required": False},
    "MobilePhone":              {"type": "str",   "max": 50,  "required": True},
    "IsRegisteredBusiness":     {"type": "bool",               "required": False},
    "ABN":                      {"type": "str",   "max": 15,  "required": False},
    "ACN":                      {"type": "str",   "max": 15,  "required": False},
    "PaymentTerms":             {"type": "str",   "max": 100, "required": False},
    "Currency":                 {"type": "str",   "max": 10,  "required": False},
    "PaymentMethod":            {"type": "str",   "max": 100, "required": False},

    "BillingContact":           {"type": "str",   "max": 255, "required": False},
    "BillingCountry":           {"type": "str",   "max": 100,   "required": False},
    "BillingStreet1":           {"type": "str",   "max": 255, "required": False},
    "BillingStreet2":           {"type": "str",   "max": 255, "required": False},
    "BillingCity":              {"type": "str",   "max": 100, "required": False},
    "BillingState":             {"type": "str",   "max": 100, "required": False},
    "BillingZIP":               {"type": "str",   "max": 20,  "required": False},
    "BillingPhone":             {"type": "str",   "max": 50,  "required": False},
    "BillingFax":               {"type": "str",   "max": 50,  "required": False},

    "ShippingContact":          {"type": "str",   "max": 255, "required": False},
    "ShippingCountry":          {"type": "str",   "max": 100,   "required": False},
    "ShippingStreet1":          {"type": "str",   "max": 255, "required": False},
    "ShippingStreet2":          {"type": "str",   "max": 255, "required": False},
    "ShippingCity":             {"type": "str",   "max": 100, "required": False},
    "ShippingState":            {"type": "str",   "max": 100, "required": False},
    "ShippingZIP":              {"type": "str",   "max": 20,  "required": False},
    "ShippingPhone":            {"type": "str",   "max": 50,  "required": False},
    "ShippingFax":              {"type": "str",   "max": 50,  "required": False},

    "BankAccountName":          {"type": "str",   "max": 255, "required": False},
    "BankName":                 {"type": "str",   "max": 255, "required": False},
    "BankAccountNumber":        {"type": "str",   "max": 50,  "required": False},
    "BankCode":                 {"type": "str",   "max": 50,  "required": False},

    "ContactFirstName":         {"type": "str",   "max": 100, "required": False},
    "ContactLastName":          {"type": "str",   "max": 100, "required": False},
    "ContactPhone":             {"type": "str",   "max": 50,  "required": False},
    "ContactEmail":             {"type": "email", "max": 255, "required": False},
    "ContactRole":              {"type": "str",   "max": 255, "required": False},
    "ContactPurpose":           {"type": "str",   "max": 255, "required": False},
    "Remarks":                  {"type": "str",               "required": False},
}
required_headers_v1 = [
    "VendorType","Salutation","FirstName","LastName","CompanyName","CompanyType","DisplayName",
    "VendorCode","Email","WorkPhone","MobilePhone","IsRegisteredBusiness","ABN","ACN","PaymentTerms",
    "Currency","PaymentMethod","BillingContact","BillingCountry","BillingStreet1","BillingStreet2",
    "BillingCity","BillingState","BillingZIP","BillingPhone","BillingFax","ShippingContact",
    "ShippingCountry","ShippingStreet1","ShippingStreet2","ShippingCity","ShippingState","ShippingZIP",
    "ShippingPhone","ShippingFax","BankAccountName","BankName","BankAccountNumber","BankCode",
    "ContactFirstName","ContactLastName","ContactPhone","ContactEmail","ContactRole","ContactPurpose",
    "Remarks"

]

#Stage - 1 - Form view
@login_required
def import_vendor(request):
    context = {}
    return render(request, 'sbadmin/pages/vendor/bulk_import/import_vendor_form.html', context)

#Stage - 2 - Validate the uploaded file and test the fields - if set redirect to next stage 3
@login_required
def import_vendor_validate(request):

    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid request."})

    uploaded_file = request.FILES.get("import_file")
    encoding = request.POST.get("encoding", "utf-8")
    dup = request.POST.get("dub")

    if not uploaded_file:
        return JsonResponse({"status": False, "message": "No file uploaded."})

    ext = uploaded_file.name.split(".")[-1].lower()
    if ext not in VALID_EXTENSIONS:
        return JsonResponse({"status": False, "message":"File must be CSV / XLSX"})

    # Save uploaded file temporarily
    temp_dir = os.path.join(settings.MEDIA_ROOT, "imports", "vendors")
    os.makedirs(temp_dir, exist_ok=True)

    saved_path = os.path.join(temp_dir, uploaded_file.name)
    with open(saved_path, "wb+") as fp:
        for chunk in uploaded_file.chunks():
            fp.write(chunk)

    # Read file
    try:
        if ext == "csv":
            df = pd.read_csv(saved_path, encoding=encoding)
        elif ext == "tsv":
            df = pd.read_csv(saved_path, sep="\t", encoding=encoding)
        else:
            df = pd.read_excel(saved_path)

        file_headers = df.columns.tolist()
    except Exception as e:
        return JsonResponse({"status": False, "message": "Error reading file", "error":str(e)})

    # Missing headers
    missing_headers = [h for h in required_headers_v1 if h not in file_headers]
    if missing_headers:
        msg = (
            "The uploaded file is missing required headers: "
            f"<b>{', '.join(missing_headers)}</b>"
        )
        os.remove(saved_path)
        return JsonResponse({"status": False, "message": mark_safe(msg)})

    # Only keep mapping_fields
    cleaned_headers = list(required_headers_v1)
    validated_rows = []
    row_errors = []
    for idx, row in df.iterrows():
        row_dict = {}
        # Build row dict ONLY from mapping fields
        for col in required_headers_v1:
            if col in df.columns:
                val = row[col]
                row_dict[col] = "" if pd.isna(val) else str(val).strip()
            else:
                row_dict[col] = ""   # Missing field → empty

        # Validate each row
        errors = validate_vendor_row(row_dict)
        if errors:
            row_errors.append({
                "row": idx + 2,
                "errors": errors
            })
        else:
            validated_rows.append(row_dict)

    # If validation errors → show them
    if row_errors:
        html = "<h4>Data Errors Found:</h4><ul>"
        for row_err in row_errors:
            row_num = row_err["row"]
            err_msg = ", ".join([f"{k}: {v}" for k, v in row_err["errors"].items()])
            html += f"<li><b>Row {row_num}</b>: {err_msg}</li>"
        html += "</ul>"
        return JsonResponse({"status": False, "message": mark_safe(html)})


    cleaned_filename = f"cleaned_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    cleaned_path = os.path.join(temp_dir, cleaned_filename)

    with open(cleaned_path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=cleaned_headers)
        writer.writeheader()
        for row in validated_rows:
            writer.writerow({field: row.get(field, "") for field in cleaned_headers})

    # Store info in session
    request.session["dup_option"] = dup
    request.session["cleaned_filename"] = cleaned_filename

    select_options = []
    for file_header in file_headers:
        select_options.append({"value": file_header, "label": file_header})

    cleaned_filename = cleaned_filename.replace(" ", "_")
    uploaded_filename = uploaded_file.name.replace(" ", "_")

    redirect_url = reverse(
        "import_vendor_stage_map",
        kwargs={
            "cleaned_filename": cleaned_filename,
            "dup_option": dup,
            "uploaded_filename": uploaded_filename,
        }
    )
    return JsonResponse({"status": True, "message": "", "data": {
        "redirect_url": redirect_url
    }})


#stage -3
@login_required
def link_fields(request, cleaned_filename, dup_option, uploaded_filename):
    '''Retrieve file from cleaned_filename - read the headers - map the headers'''
    temp_dir = os.path.join(settings.MEDIA_ROOT, "imports", "vendors")
    saved_path = os.path.join(temp_dir, cleaned_filename)
    df = pd.read_csv(saved_path, encoding="utf-8")
    file_headers = df.columns.tolist()
    select_options = []
    for file_header in file_headers:
        select_options.append({"value": file_header, "label": file_header})

    cleaned_filename = cleaned_filename.replace(" ", "_")

    return render(request, "sbadmin/pages/vendor/bulk_import/import_vendor_stage_1.html", {
        "mapping_fields": required_headers_v1,
        "select_options": select_options,
        "dup_option": dup_option,
        "cleaned_filename": cleaned_filename,
        "uploaded_filename": uploaded_filename,
    })


@login_required
def preview_import(request):
    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return redirect("import_vendor")

        # Get stored session values
    dup_option = request.session.get("dup_option")
    cleaned_filename = request.session.get("cleaned_filename")
    try:

        if not cleaned_filename:
            messages.error(request, "No validated data found. Please re-upload the file.")
            return redirect("import_vendor")

        # Paths
        temp_dir = os.path.join(settings.MEDIA_ROOT, "imports", "vendors")
        cleaned_path = os.path.join(temp_dir, cleaned_filename)

        if not os.path.exists(cleaned_path):
            messages.error(request, f"The file '{cleaned_filename}' could not be located on the server.")
            raise Exception('url_name_for_import_vendor_form')

        df = pd.read_csv(cleaned_path, encoding="utf-8")
        validated_rows = df.to_dict('records')

        valid_count = len(validated_rows)
        headers = df.columns.tolist()
        #print(headers)
        #print(validated_rows)
        # Extract headers from dict keys

        # Render preview page
        return render(request, "sbadmin/pages/vendor/bulk_import/import_vendor_stage_2.html", {
            "error": None,
            "records_preview": validated_rows[:10],  # first 10 only
            "valid_count": valid_count,  # total valid rows
            "headers": headers,
        })
    except Exception as e:
        print(str(e))
        messages.error(request, f"Error reading file: {str(e)}")
        return render(request, "sbadmin/pages/vendor/bulk_import/import_vendor_stage_2.html", {
        })

@login_required
def final_vendor_import(request):

    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return redirect("import_vendor")

    dup_option = request.session.get("dup_option")
    cleaned_filename = request.session.get("cleaned_filename")

    if not cleaned_filename:
        messages.error(request, "No validated file. Please re-upload.")
        return redirect("import_vendor")

    temp_dir = os.path.join(settings.MEDIA_ROOT, "imports", "vendors")
    cleaned_path = os.path.join(temp_dir, cleaned_filename)

    if not os.path.exists(cleaned_path):
        messages.error(request, "Cleaned file not found. Please restart import.")
        return redirect("import_vendor")

    try:
        df = pd.read_csv(cleaned_path, encoding="utf-8")
    except Exception as e:
        messages.error(request, f"Could not read cleaned file: {str(e)}")
        return render(request, "sbadmin/pages/vendor/bulk_import/import_vendor_stage_3.html",
                      {"imported_count": 0})

    imported_count = 0

    payment_map = {
        "LAST_NEXT_NEXT_MONTH": 1,
        "LAST_NEXT_MONTH": 2,
        "FOURTEENTH_NEXT_MONTH": 3,
        "NET_45": 4,
        "NET_60": 5,
    }

    for _, row in df.iterrows():

        vendor_code = to_str(row.get("VendorCode"))
        email = to_str(row.get("Email"))

        # ---------------- CHECK EXISTING VENDOR ----------------
        if vendor_code and email:
            existing_vendor = Vendor.objects.filter(
                Q(vendor_code=vendor_code) | Q(email_address=email)
            ).first()
        elif vendor_code:
            existing_vendor = Vendor.objects.filter(vendor_code=vendor_code).first()
        elif email:
            existing_vendor = Vendor.objects.filter(email_address=email).first()
        else:
            existing_vendor = None

        # ---------------- DUPLICATE HANDLING ----------------
        if dup_option == "skip_duplicate" and existing_vendor:
            continue

        if dup_option == "overwrite_existing" and existing_vendor:
            vendor = existing_vendor
        else:
            vendor = Vendor()
            if vendor_code:
                vendor.vendor_code = vendor_code
            else:
                with transaction.atomic():
                    last = Vendor.objects.order_by("-id").first()
                    next_id = (last.id + 1) if last else 1
                vendor.vendor_code = f"V{next_id:03d}"

        # ---------------- VENDOR CORE FIELDS ----------------
        vendor.vendor_company_name = to_str(row.get("CompanyName")) or None

        vendor.vendor_name = " ".join(
            part for part in [
                to_str(row.get("Salutation")),
                to_str(row.get("FirstName")),
                to_str(row.get("LastName"))
            ] if part
        ) or None

        vendor.gst_number = to_str(row.get("ABN")) or None
        vendor.company_abn = to_str(row.get("ABN")) or None
        vendor.company_acn = to_str(row.get("ACN")) or None
        vendor.currency = to_str(row.get("Currency")) or None

        vendor.company_acc_no = None
        vendor.company_website = None
        vendor.company_locality = None

        is_reg = to_str(row.get("IsRegisteredBusiness")).lower()
        vendor.is_taxable = True if is_reg in ["1", "yes", "true", "y"] else False

        vendor.work_phone = to_str(row.get("WorkPhone")) or None
        vendor.mobile_number = to_str(row.get("MobilePhone")) or None

        vendor.email_address = email

        vendor.company_type = to_str(row.get("CompanyType")) or None
        vendor.vendor_locality = None
        vendor.vendor_remarks = to_str(row.get("Remarks")) or None

        # ---------------- PAYMENT TERM ----------------
        pay_term = to_str(row.get("PaymentTerms"))
        vendor.payment_term = payment_map.get(pay_term, 2)

        if not vendor.id:
            vendor.created_by = request.user.id

        vendor.status = 1
        vendor.save()

        # ======================================================
        # BILLING ADDRESS
        # ======================================================
        billing_contact = to_str(row.get("BillingContact"))
        billing_street1 = to_str(row.get("BillingStreet1"))
        billing_street2 = to_str(row.get("BillingStreet2"))
        billing_city = to_str(row.get("BillingCity"))
        billing_state_txt = to_str(row.get("BillingState"))
        billing_zip = to_str(row.get("BillingZIP"))
        billing_phone = to_str(row.get("BillingPhone"))
        billing_fax = to_str(row.get("BillingFax"))
        billing_country_txt = to_str(row.get("BillingCountry"))

        bill_country = Country.objects.filter(name__iexact=billing_country_txt).first() if billing_country_txt else None
        bill_state = State.objects.filter(name__iexact=billing_state_txt).first() if billing_state_txt else None

        billing_has_data = any([billing_street1, billing_city, billing_zip, bill_country])

        if billing_has_data:

            vendor_addr_link = VendorAddress.objects.filter(
                vendor=vendor, address_type="billing"
            ).first()

            if vendor_addr_link:
                addr = vendor_addr_link.address
                addr.attention = billing_contact or None
                addr.address_line1 = billing_street1 or None
                addr.address_line2 = billing_street2 or None
                addr.suburb = billing_city or None
                addr.state = billing_state_txt or None
                addr.post_code = billing_zip or None
                addr.country = billing_country_txt or None
                addr.phone = billing_phone or None
                addr.fax = billing_fax or None
                addr.save()

            else:
                addr = Addresses.objects.create(
                    attention=billing_contact or None,
                    address_line1=billing_street1 or None,
                    address_line2=billing_street2 or None,
                    suburb=billing_city or None,
                    state=billing_state_txt or None,
                    post_code=billing_zip or None,
                    country=billing_country_txt or None,
                    phone=billing_phone or None,
                    fax=billing_fax or None,
                    created_by=request.user.id,
                )

                VendorAddress.objects.create(
                    vendor=vendor,
                    address_type="billing",
                    address_id=addr.id,
                    created_by=request.user.id
                )

        # ======================================================
        # SHIPPING ADDRESS
        # ======================================================
        shipping_contact = to_str(row.get("ShippingContact"))
        shipping_street1 = to_str(row.get("ShippingStreet1"))
        shipping_street2 = to_str(row.get("ShippingStreet2"))
        shipping_city = to_str(row.get("ShippingCity"))
        shipping_state_txt = to_str(row.get("ShippingState"))
        shipping_zip = to_str(row.get("ShippingZIP"))
        shipping_phone = to_str(row.get("ShippingPhone"))
        shipping_fax = to_str(row.get("ShippingFax"))
        shipping_country_txt = to_str(row.get("ShippingCountry"))

        shipping_has_data = any([shipping_street1, shipping_city, shipping_zip])

        if shipping_has_data:

            vendor_addr_link = VendorAddress.objects.filter(
                vendor=vendor, address_type="shipping"
            ).first()

            if vendor_addr_link:
                addr = vendor_addr_link.address
                addr.attention = shipping_contact or None
                addr.address_line1 = shipping_street1 or None
                addr.address_line2 = shipping_street2 or None
                addr.suburb = shipping_city or None
                addr.state = shipping_state_txt or None
                addr.post_code = shipping_zip or None
                addr.country = shipping_country_txt or None
                addr.phone = shipping_phone or None
                addr.fax = shipping_fax or None
                addr.save()

            else:
                addr = Addresses.objects.create(
                    attention=shipping_contact or None,
                    address_line1=shipping_street1 or None,
                    address_line2=shipping_street2 or None,
                    suburb=shipping_city or None,
                    state=shipping_state_txt or None,
                    post_code=shipping_zip or None,
                    country=shipping_country_txt or None,
                    phone=shipping_phone or None,
                    fax=shipping_fax or None,
                    created_by=request.user.id,
                )

                VendorAddress.objects.create(
                    vendor=vendor,
                    address_type="shipping",
                    address_id=addr.id,
                    created_by=request.user.id
                )

        # ======================================================
        # BANK DETAILS
        # ======================================================
        bank_account_no = to_str(row.get("BankAccountNumber"))

        if bank_account_no:
            vendor_bank = VendorBank.objects.filter(vendor=vendor).first()

            if not vendor_bank:
                vendor_bank = VendorBank(vendor=vendor, created_by=request.user.id)

            vendor_bank.account_holder = to_str(row.get("BankAccountName")) or None
            vendor_bank.bank_name = to_str(row.get("BankName")) or None
            vendor_bank.account_number = bank_account_no
            vendor_bank.bic = to_str(row.get("BankCode")) or None
            vendor_bank.save()

        # ======================================================
        # CONTACT PERSON
        # ======================================================
        contact_email = to_str(row.get("ContactEmail"))
        contact_first = to_str(row.get("ContactFirstName"))
        contact_last = to_str(row.get("ContactLastName"))
        contact_phone = to_str(row.get("ContactPhone"))
        contact_role = to_str(row.get("ContactRole"))

        if contact_email or contact_first or contact_phone:

            VendorContact.objects.create(
                vendor=vendor,
                is_primary=False,
                department=contact_role or "Unknown",
                email=contact_email or None,
                phone=contact_phone or None,
                mobile_no=None,
                first_name=contact_first or "Unknown",
                last_name=contact_last or "Unknown",
                role=contact_role or "Unknown",
                description=to_str(row.get("ContactPurpose")) or None,
                created_by=request.user.id
            )

        imported_count += 1

    return render(request,
        "sbadmin/pages/vendor/bulk_import/import_vendor_stage_3.html",
        {"imported_count": imported_count, "updated_count": 0}
    )

@login_required
def download_vendor_template(request, file_type, file_format):

    if file_type not in ["vendors", "vendor_contacts", "vendor_bank_accounts"] or \
       file_format not in ["csv", "tsv", "xlsx"]:
        raise Http404("Invalid request")

    relative_path = f"import_templates/vendor/{file_type}.{file_format}"
    file_path = None

    if getattr(settings, "STATIC_ROOT", None):
        candidate = os.path.join(settings.STATIC_ROOT, relative_path)
        if os.path.exists(candidate):
            file_path = candidate

    if not file_path:
        for static_dir in getattr(settings, "STATICFILES_DIRS", []):
            candidate = os.path.join(static_dir, relative_path)
            if os.path.exists(candidate):
                file_path = candidate
                break

    if not file_path:
        raise Http404("Sample file not found")

    return FileResponse(
        open(file_path, "rb"),
        as_attachment=True,
        filename=f"{file_type}.{file_format}"
    )

def import_vendor_contacts(request):
    if request.method == "POST":
        data = request.data  # assuming parsed CSV data

        contacts_to_create = []

        for row in data:
            vendor = Vendor.objects.filter(name=row.get("vendor_name")).first()

            if not vendor:
                continue

            contact = VendorContact(
                vendor=vendor,
                first_name=row.get("first_name"),
                last_name=row.get("last_name"),
                email=row.get("email"),
                phone=row.get("phone"),
                mobile_no=row.get("mobile_no"),
                department=row.get("department"),
                role=row.get("role"),
                created_by=1
            )
            contacts_to_create.append(contact)

        VendorContact.objects.bulk_create(contacts_to_create)

        return JsonResponse({"message": "Vendor contacts imported successfully"})

