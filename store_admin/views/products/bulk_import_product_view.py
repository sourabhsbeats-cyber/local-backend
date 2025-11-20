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
from store_admin.models.product_model import Product
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
from django.contrib.auth.decorators import login_required
from datetime import datetime
from openpyxl import load_workbook

from openpyxl import load_workbook
from django.conf import settings
from django.http import HttpResponseBadRequest
from django.utils.safestring import mark_safe

@login_required
def import_product(request):
    context = {}
    return render(request, 'sbadmin/pages/product/bulk_import/import_product_form.html', context)

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

def validate_product_row(row_dict):
    errors = {}
    for field, rules in product_field_schema.items():
        value = row_dict.get(field)
        error = validate_field(field, value, rules)
        if error:
            errors[field] = error
    return errors

VALID_EXTENSIONS = ["csv"] #, "tsv", "xlsx" - FOr now csv only allowed
# "product_id": {"type": "int", "required": True},
# "created_by": {"type": "int", "required": True},
product_field_schema = {
    "product_type": {"type": "str", "max": 120, "required": False},
    "parent_sku": {"type": "str", "max": 120, "required": False},
    "bundle_sku": {"type": "str", "max": 120, "required": False},
    "is_alias": {"type": "bool", "required": False},
    "sku": {"type": "str", "max": 120, "required": True},
    "title": {"type": "str", "max": 255, "required": True},
    "subtitle": {"type": "str", "max": 255, "required": False},
    "description": {"type": "str", "required": False},
    "short_description": {"type": "str", "required": False},
    "status_condition": {"type": "str", "max": 20, "required": False},
    "asin": {"type": "str", "max": 50, "required": False},
    "fnsku": {"type": "str", "max": 50, "required": False},
    "fba_sku": {"type": "str", "max": 50, "required": False},
    "is_fba": {"type": "bool", "required": False},
    "isbn_type": {"type": "str", "max": 20, "required": False},
    "barcode_label_type": {"type": "str", "max": 20, "required": False},
    "prep_type": {"type": "str", "max": 20, "required": False},
    "ean": {"type": "str", "max": 50, "required": False},
    "upc": {"type": "str", "max": 50, "required": False},
    "isbn": {"type": "str", "max": 50, "required": False},
    "mpn": {"type": "str", "max": 120, "required": False},
    "warranty": {"type": "int", "required": False},
    "product_tags": {"type": "str", "required": False},

    #"country_origin_id": {"type": "int", "required": True},
    # "brand_id": {"type": "int", "required": True},
    # "manufacturer_id": {"type": "int", "required": True},
    #"stock_status": {"type": "int", "required": True},
    #"status": {"type": "int", "required": True},
    #"publish_status": {"type": "int", "required": True},
}
'''product_type,parent_sku,bundle_sku,is_alias,sku,title,subtitle,description,short_description,
ean,upc,isbn,mpn,status_condition,asin,fnsku,fba_sku,is_fba,isbn_type,barcode_label_type,prep_type,
warranty,product_tags'''

required_headers = [
    "product_type", "parent_sku", "bundle_sku", "is_alias", "sku", "title",
    "subtitle", "description", "short_description",
    "status_condition", "asin", "fnsku",
    "fba_sku", "is_fba", "isbn_type", "barcode_label_type", "prep_type",
    "ean", "upc", "isbn" , "mpn",
    "warranty", "product_tags",
    #"brand_id",    "manufacturer_id",
    #"country_origin_id",
    #"stock_status",
    #"status", "publish_status",
]

@login_required
def import_product_validate(request):

    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return render(request, 'sbadmin/pages/product/bulk_import/import_product_form.html')

    uploaded_file = request.FILES.get("import_file")
    encoding = request.POST.get("encoding", "utf-8")
    dup = request.POST.get("dup")

    if not uploaded_file:
        messages.error(request, "No file uploaded.")
        return render(request, 'sbadmin/pages/product/bulk_import/import_product_form.html')

    ext = uploaded_file.name.split(".")[-1].lower()
    if ext not in VALID_EXTENSIONS:
        messages.error(request, "File must be CSV ") #/ TSV / XLSX
        return render(request, 'sbadmin/pages/product/bulk_import/import_product_form.html')

    # Save uploaded file temporarily
    temp_dir = os.path.join(settings.MEDIA_ROOT, "imports", "product")
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
        return render(request, 'sbadmin/pages/product/bulk_import/import_product_form.html')

    # Missing headers
    missing_headers = [h for h in required_headers if h not in file_headers]
    if missing_headers:
        msg = (
            "The uploaded file is missing required headers: "
            f"<b>{', '.join(missing_headers)}</b>"
        )
        messages.error(request, mark_safe(msg))
        os.remove(saved_path)
        return render(request, 'sbadmin/pages/product/bulk_import/import_product_form.html')

    # -------------------------
    #  CLEANING AND VALIDATION
    # -------------------------

    # Only keep mapping_fields
    cleaned_headers = list(required_headers)

    validated_rows = []
    row_errors = []

    for idx, row in df.iterrows():

        row_dict = {}

        # Build row dict ONLY from mapping fields
        for col in required_headers:
            if col in df.columns:
                val = row[col]
                row_dict[col] = "" if pd.isna(val) else str(val).strip()
            else:
                row_dict[col] = ""   # Missing field → empty

        # Validate each row
        errors = validate_product_row(row_dict)
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
        return render(request, 'sbadmin/pages/product/bulk_import/import_product_form.html')

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
        {"value": "product_type", "label": "Product Type"},
        {"value": "parent_sku", "label": "Parent Sku"},
        {"value": "bundle_sku", "label": "Bundle Sku"},
        {"value": "is_alias", "label": "Is Alias"},
        {"value": "sku", "label": "Sku"},
        {"value": "title", "label": "Title"},
        {"value": "subtitle", "label": "Subtitle"},
        {"value": "description", "label": "Description"},
        {"value": "short_description", "label": "Short Description"},
        #{"value": "brand_id", "label": "Brand Id"}, #Reference
        #{"value": "manufacturer_id", "label": "Manufacturer Id"},  #Reference
        {"value": "ean", "label": "Ean"},
        {"value": "upc", "label": "Upc"},
        {"value": "isbn", "label": "Isbn"},
        {"value": "mpn", "label": "Mpn"},
        #{"value": "country_origin_id", "label": "Country Origin Id"},
        {"value": "status_condition", "label": "Status Condition"}, #string options
        {"value": "asin", "label": "Asin"},
        {"value": "fnsku", "label": "Fnsku"},
        {"value": "fba_sku", "label": "Fba Sku"},
        {"value": "is_fba", "label": "Is Fba"},
        {"value": "isbn_type", "label": "Isbn Type"},
        {"value": "barcode_label_type", "label": "Barcode Label Type"},
        {"value": "prep_type", "label": "Prep Type"},
        {"value": "stock_status", "label": "Stock Status"}, #int value
        #{"value": "status", "label": "Status"},
        #{"value": "publish_status", "label": "Publish Status"},
        {"value": "warranty", "label": "Warranty"},
        {"value": "product_tags", "label": "Product Tags"},
    ]

    return render(request, "sbadmin/pages/product/bulk_import/import_product_stage_1.html", {
        "mapping_fields": required_headers,
        "select_options": select_options,
        "dup_option": dup,
        "cleaned_filename": cleaned_filename,
        "uploaded_filename": uploaded_file.name,
    })

@login_required
def download_product_template(request, file_type, file_format):

    if file_type not in ["product"] or \
       file_format not in ["csv"]: #, "tsv", "xlsx"
        raise Http404("Invalid request")

    relative_path = f"import_templates/product/{file_type}.{file_format}"
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
        return redirect("import_product")

        # Get stored session values
    dup_option = request.session.get("dup_option")
    cleaned_filename = request.session.get("cleaned_filename")
    try:

        if not cleaned_filename:
            messages.error(request, "No validated data found. Please re-upload the file.")
            return redirect("import_product")

        # Paths
        temp_dir = os.path.join(settings.MEDIA_ROOT, "imports", "product")
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
        return render(request, "sbadmin/pages/product/bulk_import/import_product_stage_2.html", {
            "error": None,
            "records_preview": validated_rows[:10],  # first 10 only
            "valid_count": valid_count,  # total valid rows
            "headers": headers,
        })
    except Exception as e:
        print(str(e))
        messages.error(request, f"Error reading file: {str(e)}")
        return render(request, "sbadmin/pages/product/bulk_import/import_product_stage_2.html", {
        })

@login_required
def final_product_import(request):

    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return redirect("import_product")

    dup_option = request.session.get("dup_option", "skip_duplicate")  # skip_duplicate / overwrite_existing / allow_duplicates
    cleaned_filename = request.session.get("cleaned_filename")

    if not cleaned_filename:
        messages.error(request, "No validated file. Please re-upload.")
        return redirect("import_product")

    temp_dir = os.path.join(settings.MEDIA_ROOT, "imports", "product")
    cleaned_path = os.path.join(temp_dir, cleaned_filename)

    if not os.path.exists(cleaned_path):
        messages.error(request, "Cleaned file not found. Please restart import.")
        return redirect("import_product")

    # Load cleaned CSV
    try:
        df = pd.read_csv(cleaned_path, encoding="utf-8")
    except Exception as e:
        messages.error(request, f"Could not read cleaned file: {str(e)}")
        return render(request, "sbadmin/pages/product/bulk_import/import_vendor_stage_3.html",
                      {"imported_count": 0})

    imported_count = 0

    # Loop through each row and import into DB
    for _, row in df.iterrows():

        sku = str(row.get("sku", "")).strip()

        #  Check existing product
        existing_product = Product.objects.filter(sku=sku).first()

        # -------------------------------
        # CASE 1: SKIP DUPLICATES
        # -------------------------------
        if dup_option == "skip_duplicate" and existing_product:
            continue

        # -------------------------------
        # CASE 2: OVERWRITE EXISTING
        # -------------------------------
        if dup_option == "overwrite_existing" and existing_product:
            product = existing_product  # update existing row

        # -------------------------------
        # CASE 3: ALWAYS CREATE NEW
        # -------------------------------
        else:
            product = Product()

            # -------------------------------
            #  ASSIGN FIELDS
            # -------------------------------
        product.product_type = row.get("product_type", "")
        product.parent_sku = row.get("parent_sku", "")
        product.bundle_sku = row.get("bundle_sku", "")
        product.is_alias = row.get("is_alias", "")
        product.sku = row.get("sku", "")
        product.title = row.get("title", "")
        product.subtitle = row.get("subtitle", "")

        product.description = row.get("description", "")
        product.short_description = row.get("short_description", "")
        product.status_condition = row.get("status_condition", "")
        product.asin = row.get("asin", "")
        product.fnsku = row.get("fnsku", "")
        product.fba_sku = row.get("fba_sku", "")
        product.is_fba = row.get("is_fba", "")
        product.isbn_type = row.get("isbn_type", "")
        product.barcode_label_type = row.get("barcode_label_type", "")
        product.prep_type = row.get("prep_type", "")

        product.ean = row.get("ean", "")
        product.upc = row.get("upc", "")
        product.isbn = row.get("isbn", "")
        product.mpn = row.get("mpn", "")
        product.warranty = row.get("warranty", "")
        product.product_tags = row.get("product_tags", "")

        #vendor.payment_term_id = row.get("payment_term", None)

        product.status = 1  # default active
        product.save()
        imported_count += 1

    return render(request, "sbadmin/pages/product/bulk_import/import_product_stage_3.html",
                  {"imported_count": imported_count})