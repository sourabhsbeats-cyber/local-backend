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

@login_required
def import_vendor(request):
    context = {}
    return render(request, 'sbadmin/pages/vendor/bulk_import/import_vendor_form.html', context)

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

VALID_EXTENSIONS = ["csv", "tsv", "xlsx"]
vendor_field_schema = {
    "salutation": {"type": "str", "max": 20, "required": False},
    "first_name": {"type": "str", "max": 100, "required": True},
    "last_name": {"type": "str", "max": 100, "required": True},
    "company_name": {"type": "str", "max": 255, "required": False},
    "display_name": {"type": "str", "max": 255, "required": True},
    "vendor_code": {"type": "str", "max": 50, "required": True},
    "email_address": {"type": "email", "max": 255, "required": False},
    "work_phone": {"type": "str", "max": 50, "required": False},
    "mobile_number": {"type": "str", "max": 50, "required": True},
    "registered_business": {"type": "bool", "required": False},
    "company_abn": {"type": "str", "max": 50, "required": False},
    "company_acn": {"type": "str", "max": 50, "required": True},
    "currency": {"type": "str", "max": 10, "required": False},
    "documents": {"type": "str", "max": 255, "required": False},
    "vendor_remarks": {"type": "str", "required": False},
    "payment_term_id": {"type": "int", "required": False},
    "status": {"type": "int", "required": False},
}

required_headers = mapping_fields = [
        "salutation",
        "first_name",
        "last_name",
        "company_name",
        "display_name",
        "vendor_code",
        "email_address",
        "work_phone",
        "mobile_number",
        "registered_business",
        "company_abn",
        "company_acn",
        "currency",
        "vendor_remarks",
        "payment_term",
    ]

from django.utils.safestring import mark_safe

@login_required
def import_vendor_validate(request):

    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return render(request, 'sbadmin/pages/vendor/bulk_import/import_vendor_form.html')

    uploaded_file = request.FILES.get("import_file")
    encoding = request.POST.get("encoding", "utf-8")
    dup = request.POST.get("dup")

    if not uploaded_file:
        messages.error(request, "No file uploaded.")
        return render(request, 'sbadmin/pages/vendor/bulk_import/import_vendor_form.html')

    ext = uploaded_file.name.split(".")[-1].lower()
    if ext not in VALID_EXTENSIONS:
        messages.error(request, "File must be CSV / TSV / XLSX")
        return render(request, 'sbadmin/pages/vendor/bulk_import/import_vendor_form.html')

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
        messages.error(request, f"Error reading file: {str(e)}")
        return render(request, 'sbadmin/pages/vendor/bulk_import/import_vendor_form.html')

    # Missing headers
    missing_headers = [h for h in required_headers if h not in file_headers]
    if missing_headers:
        msg = (
            "The uploaded file is missing required headers: "
            f"<b>{', '.join(missing_headers)}</b>"
        )
        messages.error(request, mark_safe(msg))
        os.remove(saved_path)
        return render(request, 'sbadmin/pages/vendor/bulk_import/import_vendor_form.html')

    # -------------------------
    #  CLEANING AND VALIDATION
    # -------------------------

    # Only keep mapping_fields
    cleaned_headers = list(mapping_fields)

    validated_rows = []
    row_errors = []

    for idx, row in df.iterrows():

        row_dict = {}

        # Build row dict ONLY from mapping fields
        for col in mapping_fields:
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

        messages.error(request, mark_safe(html))
        return render(request, 'sbadmin/pages/vendor/bulk_import/import_vendor_form.html')

    # -------------------------
    #  WRITE CLEANED CSV
    # -------------------------

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

    # Dropdown list for mapping page
    select_options = [
        {"value": "salutation", "label": "Salutation"},
        {"value": "first_name", "label": "First Name"},
        {"value": "last_name", "label": "Last Name"},
        {"value": "company_name", "label": "Company Name"},
        {"value": "display_name", "label": "Display Name"},
        {"value": "vendor_code", "label": "Vendor Code"},
        {"value": "email_address", "label": "Email Address"},
        {"value": "work_phone", "label": "Work Phone"},
        {"value": "mobile_number", "label": "Mobile Number"},
        {"value": "registered_business", "label": "Registered Business"},
        {"value": "company_abn", "label": "Company ABN"},
        {"value": "company_acn", "label": "Company ACN"},
        {"value": "currency", "label": "Currency"},
        {"value": "vendor_remarks", "label": "Remarks"},
        {"value": "payment_term", "label": "Payment Term"},
    ]

    return render(request, "sbadmin/pages/vendor/bulk_import/import_vendor_stage_1.html", {
        "mapping_fields": mapping_fields,
        "select_options": select_options,
        "dup_option": dup,
        "cleaned_filename": cleaned_filename,
        "uploaded_filename": uploaded_file.name,
    })

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
        print(validated_rows)
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

    dup_option = request.session.get("dup_option")  # skip_duplicate / overwrite_existing / allow_duplicates
    cleaned_filename = request.session.get("cleaned_filename")

    if not cleaned_filename:
        messages.error(request, "No validated file. Please re-upload.")
        return redirect("import_vendor")

    temp_dir = os.path.join(settings.MEDIA_ROOT, "imports", "vendors")
    cleaned_path = os.path.join(temp_dir, cleaned_filename)

    if not os.path.exists(cleaned_path):
        messages.error(request, "Cleaned file not found. Please restart import.")
        return redirect("import_vendor")

    # Load cleaned CSV
    try:
        df = pd.read_csv(cleaned_path, encoding="utf-8")
    except Exception as e:
        messages.error(request, f"Could not read cleaned file: {str(e)}")
        return render(request, "sbadmin/pages/vendor/bulk_import/import_vendor_stage_3.html",
                      {"imported_count": 0})

    imported_count = 0

    # Loop through each row and import into DB
    for _, row in df.iterrows():

        vendor_code = str(row.get("vendor_code", "")).strip()
        email = str(row.get("email_address", "")).strip()

        # 🔍 Check existing vendor
        existing_vendor = Vendor.objects.filter(vendor_code=vendor_code).first()

        # -------------------------------
        # CASE 1: SKIP DUPLICATES
        # -------------------------------
        if dup_option == "skip_duplicate" and existing_vendor:
            continue

        # -------------------------------
        # CASE 2: OVERWRITE EXISTING
        # -------------------------------
        if dup_option == "overwrite_existing" and existing_vendor:
            vendor = existing_vendor  # update existing row

        # -------------------------------
        # CASE 3: ALWAYS CREATE NEW
        # -------------------------------
        else:
            vendor = Vendor()

        # -------------------------------
        #  ASSIGN FIELDS
        # -------------------------------
        vendor.salutation = row.get("salutation", "")
        vendor.first_name = row.get("first_name", "")
        vendor.last_name = row.get("last_name", "")
        vendor.company_name = row.get("company_name", "")
        vendor.display_name = row.get("display_name", "")
        vendor.vendor_code = row.get("vendor_code", "")
        vendor.email_address = row.get("email_address", "")
        vendor.work_phone = row.get("work_phone", "")
        vendor.mobile_number = row.get("mobile_number", "")
        vendor.registered_business = 1 if str(row.get("registered_business", "")).lower() in ["1", "yes", "true"] else 0
        vendor.company_abn = row.get("company_abn", "")
        vendor.company_acn = row.get("company_acn", "")
        vendor.currency = row.get("currency", "")
        vendor.documents = row.get("documents", "")
        vendor.vendor_remarks = row.get("vendor_remarks", "")
        #vendor.payment_term_id = row.get("payment_term", None)

        vendor.status = 1  # default active
        vendor.save()
        imported_count += 1

    return render(request, "sbadmin/pages/vendor/bulk_import/import_vendor_stage_3.html",
                  {"imported_count": imported_count})