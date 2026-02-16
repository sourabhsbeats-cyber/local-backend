import os

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
from store_admin.models.vendor_models import Vendor, VendorBank, VendorContact, VendorAddress, VendorDocuments, \
    VendorWarehouse
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


import os
import re
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_ROWS = 100
ALLOWED_EXTS = (".csv", ".xlsx")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VENDOR_CODE_REGEX = re.compile(r"^[A-Za-z0-9-]{3,}$")
ABN_REGEX = re.compile(r"^(\d{2}\s?\d{3}\s?\d{3}\s?\d{3})$")
ACN_REGEX = re.compile(r"^(\d{3}\s?\d{3}\s?\d{3})$")

#stage 1
import pandas as pd
import uuid
@api_view(['POST'])
def pre_import_check(request):
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
            return JsonResponse({
                "status": False,
                "message": "Maximum 100 records only allowed"
            })

        df.columns = [c.strip() for c in df.columns]

        # ---------- HEADER VALIDATION ----------
        missing_cols = [c for c in required_fields if c not in df.columns]
        if missing_cols:
            return JsonResponse({
                "status": False,
                "message": f"Template Error. Missing details: {', '.join(missing_cols)}"
            })

        df = df.where(pd.notnull(df), None)

        error_log = []
        valid_records = []

        seen_vendor_codes = set()
        seen_gst = set()
        seen_emails = set()
        seen_phones = set()

        # ---------- ROW VALIDATION ----------
        for index, row in df.iterrows():
            row_num = index + 2  # Excel row number
            row_errors = []

            vendor_code = str(row.get('Vendor Code', '') or '').strip()

            # COMMON
            if not vendor_code:
                row_errors.append({
                    "row": row_num, "column": "Vendor Code",
                    "message": "Vendor Code is required"
                })

            # ---------- CONTACT VALIDATION ----------
            if import_type == 'contact':
                first = str(row.get('First Name') or '').strip()
                last = str(row.get('Last Name') or '').strip()

                raw_email = row.get('Email')
                email = str(raw_email).strip().lower() if raw_email else ''

                raw_phone = row.get('Phone')
                phone = str(raw_phone).strip() if raw_phone else ''

                # ---- Name validation ----
                if not (first or last):
                    row_errors.append({
                        "row": row_num,
                        "column": "First Name / Last Name",
                        "message": "Either First Name or Last Name is required"
                    })

                # ---- Email validation ----
                if email:
                    if not EMAIL_REGEX.fullmatch(email):
                        row_errors.append({
                            "row": row_num,
                            "column": "Email",
                            "message": "Invalid email format"
                        })
                    else:
                        if email in seen_emails:
                            row_errors.append({
                                "row": row_num,
                                "column": "Email",
                                "message": "Duplicate email in file"
                            })
                        else:
                            seen_emails.add(email)

                # ---- Phone validation ----
                if phone:
                    # Remove Excel junk like .0
                    phone = phone.replace(".0", "")

                    if not phone.isdigit():
                        row_errors.append({
                            "row": row_num,
                            "column": "Phone",
                            "message": "Phone must contain digits only"
                        })
                    else:
                        if phone in seen_phones:
                            row_errors.append({
                                "row": row_num,
                                "column": "Phone",
                                "message": "Duplicate phone in file"
                            })
                        else:
                            seen_phones.add(phone)

            # ---------- VENDOR VALIDATION ----------
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
                    acn = str(raw_acn).strip().replace(" ", "")  # ✅ space remove

                raw_currency = row.get('Currency Code')
                currency = str(raw_currency).strip() if raw_currency is not None and not pd.isna(raw_currency) else ''

                # ---------- VALIDATIONS ----------

                if not VENDOR_CODE_REGEX.match(vendor_code):
                    row_errors.append({
                        "row": row_num, "column": "Vendor Code",
                        "message": "Invalid vendor code format"
                    })

                if vendor_code in seen_vendor_codes:
                    row_errors.append({
                        "row": row_num, "column": "Vendor Code",
                        "message": "Duplicate vendor code in file"
                    })
                else:
                    seen_vendor_codes.add(vendor_code)

                if not name:
                    row_errors.append({
                        "row": row_num, "column": "Vendor Name",
                        "message": "Vendor Name is required"
                    })

                if gst:
                    if gst in seen_gst:
                        row_errors.append({
                            "row": row_num, "column": "GST Number",
                            "message": "Duplicate GST number in file"
                        })
                    else:
                        seen_gst.add(gst)

                if not payment_term:
                    row_errors.append({
                        "row": row_num, "column": "Payment Term",
                        "message": "Payment Term is required"
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

                # -------- Bank Account Number FIX --------
                raw_acct = row.get('Bank Account Number')
                acct = ''

                if raw_acct is not None and not pd.isna(raw_acct):
                    if isinstance(raw_acct, (int, float)):
                        acct = str(int(raw_acct))  # 1234570000000.0 → "1234570000000"
                    else:
                        acct = str(raw_acct).strip()

                if acct:
                    if not acct.isdigit() or len(acct) > 32:
                        row_errors.append({
                            "row": row_num,
                            "column": "Bank Account Number",
                            "message": "Invalid bank account number"
                        })

                if currency:
                    if len(currency) != 3 or not currency.isalpha():
                        row_errors.append({
                            "row": row_num, "column": "Currency Code",
                            "message": "Invalid currency code"
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

        # ---------- FINAL RESPONSE ----------
        if error_log:
            os.remove(saved_path)
            return JsonResponse({
                "status": False,
                "errors": error_log
            })



        return JsonResponse({
            "status": True,
            "message":"Validation completed click next to confirm the import",
            "duplicate_action":dup_handling,
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
        return JsonResponse({
            "status": False,
            "message": f"Error in import: {str(e)}"
        })


