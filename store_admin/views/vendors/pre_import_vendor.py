import os
import re
import uuid

import pandas as pd
from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from store_admin.AuthHandler import StrictJWTCookieAuthentication
from store_admin.models.payment_terms_model import PaymentTerm

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_ROWS = 100
ALLOWED_EXTS = (".csv", ".xlsx")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VENDOR_CODE_REGEX = re.compile(r"^[A-Za-z0-9-]{3,}$")
ABN_REGEX = re.compile(r"^(\d{2}\s?\d{3}\s?\d{3}\s?\d{3})$")
ACN_REGEX = re.compile(r"^(\d{3}\s?\d{3}\s?\d{3})$")


def normalize_duplicate_action(value):
    if not value:
        return "skip"
    normalized = str(value).strip().lower().replace('-', '_')
    if normalized in ["skip", "skip_duplicate", "skipduplicates", "skip_duplicates"]:
        return "skip"
    if normalized in ["update", "overwrite", "overwrite_existing", "update_existing", "overwriteexisting"]:
        return "update"
    return normalized


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([StrictJWTCookieAuthentication])
def pre_import_check(request):
    file = request.FILES.get('file')
    import_type = request.data.get('import_type')
    duplicate_action = normalize_duplicate_action(request.data.get('duplicate_action'))

    if not file:
        return JsonResponse({"status": False, "message": "No file uploaded"})

    if file.size > MAX_FILE_SIZE:
        return JsonResponse({"status": False, "message": "File size exceeds 5 MB"})

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTS:
        return JsonResponse({"status": False, "message": "Only CSV or XLSX files allowed"})

    template_cols = {
        'vendor': [
            'Vendor Code', 'Vendor Name', 'Status', 'Payment Term',
            'Currency Code', 'Taxable', 'Tax %',
            'Company ABN', 'Company ACN', 'Bank Account Number'
        ],
        'contact': [
            'Vendor Code', 'First Name', 'Last Name',
            'Department', 'Email', 'Phone', 'Description'
        ]
    }

    required_fields = template_cols.get(import_type)
    if not required_fields:
        return JsonResponse({"status": False, "message": "Invalid import type"})

    file_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.MEDIA_ROOT, "imports")
    os.makedirs(upload_dir, exist_ok=True)
    saved_path = os.path.join(upload_dir, f"{file_id}_pending{ext}")

    try:
        with open(saved_path, "wb+") as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        df = pd.read_csv(saved_path) if ext == ".csv" else pd.read_excel(saved_path)

        if len(df) > MAX_ROWS:
            os.remove(saved_path)
            return JsonResponse({"status": False, "message": "Maximum 100 records only allowed"})

        df.columns = [c.strip() for c in df.columns]

        missing_cols = [c for c in required_fields if c not in df.columns]
        if missing_cols:
            os.remove(saved_path)
            return JsonResponse({"status": False, "message": f"Template Error. Missing details: {', '.join(missing_cols)}"})

        df = df.where(pd.notnull(df), None)
        error_log = []
        valid_records = []

        seen_vendor_codes = set()
        seen_gst = set()
        seen_emails = set()
        seen_phones = set()

        for index, row in df.iterrows():
            row_num = index + 2
            row_errors = []

            vendor_code = str(row.get('Vendor Code', '') or '').strip()
            if not vendor_code:
                row_errors.append({"row": row_num, "column": "Vendor Code", "message": "Vendor Code is required"})

            if import_type == 'contact':
                first = str(row.get('First Name') or '').strip()
                last = str(row.get('Last Name') or '').strip()
                raw_email = row.get('Email')
                email = str(raw_email).strip().lower() if raw_email else ''
                raw_phone = row.get('Phone')
                phone = str(raw_phone).strip() if raw_phone else ''

                if not (first or last):
                    row_errors.append({"row": row_num, "column": "First Name / Last Name", "message": "Either First Name or Last Name is required"})

                if email:
                    if not EMAIL_REGEX.fullmatch(email):
                        row_errors.append({"row": row_num, "column": "Email", "message": "Invalid email format"})
                    elif email in seen_emails:
                        row_errors.append({"row": row_num, "column": "Email", "message": "Duplicate email in file"})
                    else:
                        seen_emails.add(email)

                if phone:
                    phone = phone.replace('.0', '')
                    if not phone.isdigit():
                        row_errors.append({"row": row_num, "column": "Phone", "message": "Phone must contain digits only"})
                    elif phone in seen_phones:
                        row_errors.append({"row": row_num, "column": "Phone", "message": "Duplicate phone in file"})
                    else:
                        seen_phones.add(phone)

            if import_type == 'vendor':
                name = str(row.get('Vendor Name') or '').strip()
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
                    acn = str(raw_acn).strip().replace(' ', '')
                raw_currency = row.get('Currency Code')
                currency = str(raw_currency).strip() if raw_currency is not None and not pd.isna(raw_currency) else ''

                if not VENDOR_CODE_REGEX.match(vendor_code):
                    row_errors.append({"row": row_num, "column": "Vendor Code", "message": "Invalid vendor code format"})

                if vendor_code in seen_vendor_codes:
                    row_errors.append({"row": row_num, "column": "Vendor Code", "message": "Duplicate vendor code in file"})
                else:
                    seen_vendor_codes.add(vendor_code)

                if not name:
                    row_errors.append({"row": row_num, "column": "Vendor Name", "message": "Vendor Name is required"})

                if gst:
                    if gst in seen_gst:
                        row_errors.append({"row": row_num, "column": "GST Number", "message": "Duplicate GST number in file"})
                    else:
                        seen_gst.add(gst)

                if not payment_term:
                    row_errors.append({"row": row_num, "column": "Payment Term", "message": "Payment Term is required"})
                else:
                    pt_obj = PaymentTerm.objects.filter(name__iexact=payment_term).first()
                    if not pt_obj:
                        row_errors.append({"row": row_num, "column": "Payment Term", "message": f"Payment term '{payment_term}' not found"})

                if taxable == 'no' and tax_pct != 0:
                    row_errors.append({"row": row_num, "column": "Tax %", "message": "Tax % must be 0 for tax-free vendor"})

                if abn and not ABN_REGEX.match(abn):
                    row_errors.append({"row": row_num, "column": "Company ABN", "message": "Invalid ABN format"})

                if acn and not ACN_REGEX.match(acn):
                    row_errors.append({"row": row_num, "column": "Company ACN", "message": "Invalid ACN format"})

                raw_acct = row.get('Bank Account Number')
                acct = ''
                if raw_acct is not None and not pd.isna(raw_acct):
                    if isinstance(raw_acct, (int, float)):
                        acct = str(int(raw_acct))
                    else:
                        acct = str(raw_acct).strip()

                if currency and (len(currency) != 3 or not currency.isalpha()):
                    row_errors.append({"row": row_num, "column": "Currency Code", "message": "Invalid currency code"})

            if row_errors:
                error_log.extend(row_errors)
            else:
                clean_row = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
                valid_records.append(clean_row)

        if error_log:
            os.remove(saved_path)
            return JsonResponse({"status": False, "errors": error_log})

        return JsonResponse({
            "status": True,
            "message": "Validation completed click next to confirm the import",
            "duplicate_action": duplicate_action,
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
            os.remove(saved_path)
        return JsonResponse({"status": False, "message": f"Error in import: {str(e)}"})
