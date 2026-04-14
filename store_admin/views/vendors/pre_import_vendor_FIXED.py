import os
import uuid
import pandas as pd
import re
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse

from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.vendor_models import Vendor

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_ROWS = 100
ALLOWED_EXTS = (".csv", ".xlsx")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VENDOR_CODE_REGEX = re.compile(r"^[A-Za-z0-9-]{3,}$")
ABN_REGEX = re.compile(r"^(\d{2}\s?\d{3}\s?\d{3}\s?\d{3})$")
ACN_REGEX = re.compile(r"^(\d{3}\s?\d{3}\s?\d{3})$")


@api_view(['POST'])
def pre_import_check(request):
    """
    Pre-import validation: Check file format, headers, and data validity
    """
    file = request.FILES.get('file')
    import_type = request.data.get('import_type')
    dup_handling = request.data.get('duplicate_action')

    if not file:
        return JsonResponse({"status": False, "message": "No file uploaded"})

    # ---------- FILE VALIDATION ----------
    if file.size > MAX_FILE_SIZE:
        return JsonResponse({"status": False, "message": "File size exceeds 5 MB"})

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTS:
        return JsonResponse({"status": False, "message": "Only CSV or XLSX files allowed"})

    HEADER_ALIASES = {
        'vendor code': 'Vendor Code',
        'vendor name': 'Vendor Name',
        'company name': 'Company Name',
        'vendor type': 'Vendor Type',
        'company locality': 'Company Locality',
        'city': 'City',
        'country': 'Country',
        'currency': 'Currency',
        'currency code': 'Currency Code',
        'tax %': 'Tax %',
        'status': 'Status',
        'payment term': 'Payment Term',
        'actions': 'Actions',
        'first name': 'First Name',
        'last name': 'Last Name',
        'department': 'Department',
        'email': 'Email',
        'phone': 'Phone',
        'mobile': 'Mobile',
        'description': 'Description',
        'role': 'Role',
        'is primary': 'Is Primary'
    }

    REQUIRED_FIELDS = {
        'vendor': ['Vendor Code', 'Vendor Name'],
        'contact': ['Vendor Code', 'Email']
    }

    required_fields = REQUIRED_FIELDS.get(import_type)
    if not required_fields:
        return JsonResponse({"status": False, "message": "Invalid import type"})

    file_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.MEDIA_ROOT, "imports")
    os.makedirs(upload_dir, exist_ok=True)

    saved_path = os.path.join(upload_dir, f"{file_id}_pending{ext}")

    try:
        # Save file
        with open(saved_path, "wb+") as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        # Read file
        df = pd.read_csv(saved_path) if ext == ".csv" else pd.read_excel(saved_path)

        if len(df) > MAX_ROWS:
            os.remove(saved_path)
            return JsonResponse({
                "status": False,
                "message": "Maximum 100 records only allowed"
            })

        df.columns = [c.strip() for c in df.columns]
        df = df.rename(columns={col: HEADER_ALIASES.get(col.strip().lower(), col.strip()) for col in df.columns})

        # ---------- HEADER VALIDATION ----------
        missing_cols = [c for c in required_fields if c not in df.columns]
        if missing_cols:
            os.remove(saved_path)
            return JsonResponse({
                "status": False,
                "message": f"Template Error. Missing details: {', '.join(missing_cols)}"
            })

        df = df.where(pd.notnull(df), None)

        error_log = []
        valid_records = []

        seen_vendor_codes = set()
        seen_vendor_names = set()
        seen_company_names = set()
        seen_gst = set()
        seen_contact_emails = set()
        seen_contact_phones = set()

        # ---------- ROW VALIDATION ----------
        for index, row in df.iterrows():
            row_num = index + 2  # Excel row number
            row_errors = []

            vendor_code = str(row.get('Vendor Code', '') or '').strip()

            # COMMON VALIDATION
            if not vendor_code:
                row_errors.append({
                    "row": row_num, "column": "Vendor Code",
                    "message": "Vendor Code is required"
                })

            # ---------- CONTACT VALIDATION ----------
            if import_type == 'contact':
                first = str(row.get('First Name') or '').strip()
                last = str(row.get('Last Name') or '').strip()
                department = str(row.get('Department') or '').strip()

                raw_email = row.get('Email')
                email = str(raw_email).strip().lower() if raw_email else ''

                raw_phone = row.get('Phone')
                phone = str(raw_phone).strip() if raw_phone else ''

                raw_description = str(row.get('Description') or '').strip()
                if dup_handling == 'skip' and ((email and email in seen_contact_emails) or (phone and phone in seen_contact_phones)):
                    continue

                # ---- Name validation ----
                if not (first or last):
                    row_errors.append({
                        "row": row_num,
                        "column": "First Name / Last Name",
                        "message": "Either First Name or Last Name is required"
                    })

                # Vendor must exist for contact import.
                if vendor_code:
                    vendor_exists = Vendor.objects.filter(vendor_code__iexact=vendor_code).exists()
                    if not vendor_exists:
                        row_errors.append({
                            "row": row_num,
                            "column": "Vendor Code",
                            "message": f"Vendor '{vendor_code}' not found"
                        })

                # ---- Email validation ----
                if email:
                    if not EMAIL_REGEX.fullmatch(email):
                        row_errors.append({
                            "row": row_num,
                            "column": "Email",
                            "message": "Invalid email format"
                        })

                # ---- Phone validation ----
                if phone:
                    # Remove Excel junk like .0
                    phone = phone.replace(".0", "")

                    if not phone.isdigit():
                        row_errors.append({
                            "row": row_num,
                            "column": "Phone",
                            "message": "Phone must contain only digits"
                        })

            # ---------- VENDOR VALIDATION ----------
            if import_type == 'vendor':
                name = str(row.get('Vendor Name') or '').strip()
                company_name = str(row.get('Company Name') or name).strip()

                raw_gst = row.get('GST Number')
                gst = str(raw_gst).strip() if raw_gst is not None and not pd.isna(raw_gst) else ''

                payment_term = row.get('Payment Term')

                taxable = str(row.get('Taxable') or '').lower()
                tax_pct = float(row.get('Tax %') or 0)

                raw_abn = row.get('Company ABN')
                abn = str(raw_abn).strip() if raw_abn is not None and not pd.isna(raw_abn) else ''

                raw_acn = row.get('Company ACN')
                acn = ''
                if raw_acn is not None and not pd.isna(raw_acn):
                    acn = str(raw_acn).strip().replace(" ", "")

                raw_currency = row.get('Currency Code') if row.get('Currency Code') is not None else row.get('Currency')
                currency = str(raw_currency).strip() if raw_currency is not None and not pd.isna(raw_currency) else ''

                status_value = str(row.get('Status') or '').strip()
                company_locality = str(row.get('Company Locality') or '').strip()
                country = str(row.get('Country') or '').strip()

                # ---------- VALIDATIONS ----------

                if not VENDOR_CODE_REGEX.match(vendor_code):
                    row_errors.append({
                        "row": row_num, "column": "Vendor Code",
                        "message": "Invalid vendor code format (3+ alphanumeric/hyphen)"
                    })

                company_name = str(row.get('Company Name') or name).strip()
                normalized_name = name.lower() if name else ""
                normalized_company = company_name.lower() if company_name else ""

                if (vendor_code in seen_vendor_codes or
                    (normalized_name and normalized_name in seen_vendor_names) or
                    (normalized_company and normalized_company in seen_company_names)):
                    if dup_handling == 'skip':
                        continue
                else:
                    seen_vendor_codes.add(vendor_code)
                    if normalized_name:
                        seen_vendor_names.add(normalized_name)
                    if normalized_company:
                        seen_company_names.add(normalized_company)

                if not name:
                    row_errors.append({
                        "row": row_num, "column": "Vendor Name",
                        "message": "Vendor Name is required"
                    })

                if gst:
                    if gst in seen_gst:
                        row_errors.append({
                            "row": row_num, "column": "GST Number",
                            "message": "Duplicate GST in file"
                        })
                    else:
                        seen_gst.add(gst)

                if payment_term:
                    # Validate payment term exists only when provided
                    pt_obj = PaymentTerm.objects.filter(
                        name__iexact=payment_term
                    ).first()
                    if not pt_obj:
                        row_errors.append({
                            "row": row_num, "column": "Payment Term",
                            "message": f"Payment term '{payment_term}' not found in system"
                        })

                if taxable == "no" and tax_pct != 0:
                    row_errors.append({
                        "row": row_num, "column": "Tax %",
                        "message": "Tax % must be 0 for tax-free vendor"
                    })

                if abn and not ABN_REGEX.match(abn):
                    row_errors.append({
                        "row": row_num, "column": "Company ABN",
                        "message": "Invalid ABN format"
                    })

                if acn and not ACN_REGEX.match(acn):
                    row_errors.append({
                        "row": row_num, "column": "Company ACN",
                        "message": "Invalid ACN format"
                    })

                raw_acct = row.get('Bank Account Number')
                acct = ''

                if raw_acct is not None and not pd.isna(raw_acct):
                    if isinstance(raw_acct, (int, float)):
                        acct = str(int(raw_acct))
                    else:
                        acct = str(raw_acct).strip()

                if currency:
                    if len(currency) != 3 or not currency.isalpha():
                        row_errors.append({
                            "row": row_num,
                            "column": "Currency Code",
                            "message": "Currency must be 3-letter ISO code"
                        })

            # ---------- FINAL APPEND (NaN → None) ----------
            if row_errors:
                error_log.extend(row_errors)
            else:
                clean_row = {
                    k: (None if pd.isna(v) else v)
                    for k, v in row.to_dict().items()
                }
                valid_records.append(clean_row)
                if import_type == 'contact' and dup_handling == 'skip':
                    if email:
                        seen_contact_emails.add(email)
                    if phone:
                        seen_contact_phones.add(phone)

        # ---------- FINAL RESPONSE ----------
        if error_log:
            os.remove(saved_path)
            return JsonResponse({
                "status": False,
                "errors": error_log
            })

        return JsonResponse({
            "status": True,
            "message": "Validation completed click next to confirm the import",
            "duplicate_action": dup_handling,
            "data": {
                "file_id": file_id,
                "total_rows": len(df),
                "valid_count": len(valid_records),
                "invalid_count": 0,
                "preview_data": valid_records[:5],
                "errors": []
            }
        })

    except Exception as e:
        if os.path.exists(saved_path):
            try:
                os.remove(saved_path)
            except:
                pass
        return JsonResponse({
            "status": False,
            "message": f"Error in import: {str(e)}"
        })
