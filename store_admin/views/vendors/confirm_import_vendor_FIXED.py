import os
import glob
import pandas as pd
import json
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

from store_admin.AuthHandler import StrictJWTCookieAuthentication
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.vendor_models import Vendor, VendorBank, VendorContact, VendorStatus, PaymentTerms

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


def clean_val(v):
    """Convert NaN and None values to None"""
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else v


def _to_bool(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _normalize_contact_number(value):
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return format(value, "f").rstrip("0").rstrip(".")

    text = str(value).strip()
    if not text or text.lower() in {"none", "nan", "null"}:
        return ""

    compact = text.replace(" ", "")
    if compact.endswith(".0"):
        compact = compact[:-2]

    if "e" in compact.lower():
        try:
            dec = Decimal(compact)
            if dec == dec.to_integral():
                return str(dec.to_integral())
            return format(dec.normalize(), "f")
        except (InvalidOperation, ValueError):
            return compact
    return compact


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([StrictJWTCookieAuthentication])
def confirm_import_vendor(request):
    """
    Final confirmation and import of vendor data from pre-validated file.
    Handles duplicate records based on specified action.
    """
    import_type = request.data.get('import_type')
    file_id = request.data.get('file_id')
    duplicate_action = request.data.get('duplicate_action')  # skip / update
    user_id = request.user.id

    # Validation
    if not import_type or not file_id:
        return Response(
            {"status": False, "message": "file_id and import_type are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    if duplicate_action not in ["skip", "update"]:
        return Response(
            {"status": False, "message": "Invalid duplicate_action"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        upload_dir = os.path.join(settings.MEDIA_ROOT, "imports")
        matches = glob.glob(os.path.join(upload_dir, f"{file_id}_pending.*"))

        if not matches:
            return Response(
                {"status": False, "message": "Import file not found"},
                status=status.HTTP_400_BAD_REQUEST
            )

        file_path = matches[0]
        ext = os.path.splitext(file_path)[1].lower()

        # Read file
        df = pd.read_csv(file_path) if ext == ".csv" else pd.read_excel(file_path)
        df.columns = [c.strip() for c in df.columns]
        df = df.rename(columns={col: HEADER_ALIASES.get(col.strip().lower(), col.strip()) for col in df.columns})
        df = df.where(pd.notnull(df), None)

        import_data = df.to_dict(orient="records")

        if not import_data:
            return Response(
                {"status": False, "message": "No data found in import file"},
                status=status.HTTP_400_BAD_REQUEST
            )

        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_log = []

        with transaction.atomic():

            if import_type == 'vendor':
                for item in import_data:
                    vendor_code = str(item.get('Vendor Code', '')).strip()
                    vendor_name = (item.get('Vendor Name') or '').strip()

                    if not vendor_code:
                        skipped_count += 1
                        error_log.append("Row skipped: Missing Vendor Code")
                        continue

                    # Payment Term Processing
                    raw_payment = clean_val(item.get('Payment Term'))
                    payment_term_name = raw_payment
                    payment_term_id = None

                    if payment_term_name:
                        payment_term_obj = PaymentTerm.objects.filter(
                            name__iexact=payment_term_name
                        ).first()

                        if payment_term_obj:
                            payment_term_id = payment_term_obj.id
                        else:
                            error_log.append(f"Payment term '{payment_term_name}' not found")
                            skipped_count += 1
                            continue

                    # Tax Percent Processing
                    raw_tax = clean_val(item.get('Tax %'))
                    tax_percent = float(raw_tax) if raw_tax is not None else 0.0

                    # Bank Account Processing
                    raw_acct = clean_val(item.get('Bank Account Number'))
                    account_number = None
                    if raw_acct is not None:
                        account_number = str(int(raw_acct)) if isinstance(raw_acct, (int, float)) else str(raw_acct).strip()

                    # Status mapping
                    status_name = (item.get('Status') or '').strip()
                    try:
                        status_id = VendorStatus[status_name.upper().replace(" ", "_")].value if status_name else VendorStatus.PENDING
                    except KeyError:
                        status_id = VendorStatus.PENDING

                    # Check for duplicates
                    existing_vendor = Vendor.objects.filter(
                        Q(vendor_code=vendor_code) |
                        Q(vendor_name__iexact=vendor_name)
                    ).first()

                    company_name = clean_val(item.get('Company Name')) or vendor_name
                    company_locality = clean_val(item.get('Company Locality'))
                    country = clean_val(item.get('Country'))
                    currency_value = clean_val(item.get('Currency Code')) or clean_val(item.get('Currency'))

                    if existing_vendor:
                        if duplicate_action == "skip":
                            skipped_count += 1
                            continue

                        # Update existing vendor
                        vendor = existing_vendor
                        if payment_term_id is not None:
                            vendor.payment_term = payment_term_id
                        vendor.company_abn = clean_val(item.get('Company ABN'))
                        vendor.company_acn = clean_val(item.get('Company ACN'))
                        vendor.is_taxable = True if str(item.get('Taxable', '')).lower() == 'yes' else False
                        vendor.tax_percent = tax_percent
                        vendor.company_acc_no = account_number
                        vendor.currency = currency_value
                        vendor.company_locality = company_locality
                        if country:
                            vendor.vendor_locality = country
                        vendor.status = status_id
                        vendor.updated_by = user_id
                        vendor.vendor_company_name = company_name
                        vendor.save()

                        updated_count += 1

                    else:
                        # Create new vendor
                        Vendor.objects.create(
                            vendor_code=vendor_code,
                            vendor_name=vendor_name,
                            vendor_company_name=company_name,
                            gst_number=clean_val(item.get('GST Number')),
                            payment_term=payment_term_id if payment_term_id is not None else PaymentTerms.LAST_NEXT_MONTH,
                            company_abn=clean_val(item.get('Company ABN')),
                            company_acn=clean_val(item.get('Company ACN')),
                            is_taxable=True if str(item.get('Taxable', '')).lower() == 'yes' else False,
                            tax_percent=tax_percent,
                            company_acc_no=account_number,
                            currency=currency_value,
                            company_locality=company_locality,
                            vendor_locality=country,
                            created_by=user_id,
                            updated_by=user_id,
                            status=status_id
                        )

                        created_count += 1

            elif import_type == 'contact':
                seen_contacts = set()
                cleared_vendor_contacts = set()

                for item in import_data:
                    vendor_code = str(item.get('Vendor Code', '')).strip()
                    vendor_name = str(item.get('Vendor Name', '')).strip()
                    email = str(item.get('Email', '')).strip().lower()
                    first_name = str(item.get('First Name') or '').strip()
                    last_name = str(item.get('Last Name') or '').strip()
                    phone_number = _normalize_contact_number(item.get('Phone'))
                    mobile_value = item.get('Mobile')
                    if mobile_value in [None, ""]:
                        mobile_value = item.get('MOBILE')
                    mobile_number = _normalize_contact_number(mobile_value)

                    if not vendor_code or not email:
                        skipped_count += 1
                        error_log.append("Row skipped: Missing Vendor Code or Email")
                        continue

                    vendor = Vendor.objects.filter(vendor_code__iexact=vendor_code).first()
                    if not vendor and vendor_name:
                        vendor = Vendor.objects.filter(vendor_name__iexact=vendor_name).first()
                    if not vendor:
                        skipped_count += 1
                        error_log.append(f"Vendor {vendor_code} not found")
                        continue

                    contact_key = (vendor.id, email)
                    if contact_key in seen_contacts:
                        if duplicate_action == "skip":
                            skipped_count += 1
                            continue
                        # If update, allow later row to overwrite previous created/updated entry
                    else:
                        seen_contacts.add(contact_key)

                    if duplicate_action == "update":
                        # Replace vendor contacts with the imported list so Contact Details matches preview exactly.
                        if vendor.id not in cleared_vendor_contacts:
                            VendorContact.objects.filter(vendor_id=vendor.id).delete()
                            cleared_vendor_contacts.add(vendor.id)

                        incoming_primary = _to_bool(item.get('Is Primary'))
                        if incoming_primary:
                            VendorContact.objects.filter(vendor_id=vendor.id, is_primary=True).update(is_primary=False)

                        VendorContact.objects.create(
                            vendor_id=vendor.id,
                            email=email,
                            first_name=first_name or "Unknown",
                            last_name=last_name or "Unknown",
                            department=str(item.get('Department') or '').strip(),
                            phone=phone_number or None,
                            mobile_no=mobile_number or None,
                            description=str(item.get('Description') or '').strip(),
                            role=str(item.get('Role') or 'Contact').strip(),
                            is_primary=incoming_primary,
                            created_by=user_id
                        )
                        updated_count += 1
                    else:
                        existing_contact = None
                        if email:
                            existing_contact = VendorContact.objects.filter(
                                vendor_id=vendor.id,
                                email__iexact=email
                            ).first()
                        if not existing_contact and phone_number:
                            existing_contact = VendorContact.objects.filter(
                                vendor_id=vendor.id,
                                phone=phone_number
                            ).first()
                        if not existing_contact and (first_name or last_name):
                            existing_contact = VendorContact.objects.filter(
                                vendor_id=vendor.id,
                                first_name__iexact=first_name or "Unknown",
                                last_name__iexact=last_name or "Unknown"
                            ).order_by("-is_primary", "-id").first()

                        if existing_contact:
                            skipped_count += 1
                            continue

                        VendorContact.objects.create(
                            vendor_id=vendor.id,
                            email=email,
                            first_name=first_name or "Unknown",
                            last_name=last_name or "Unknown",
                            department=str(item.get('Department') or '').strip(),
                            phone=phone_number or None,
                            mobile_no=mobile_number or None,
                            description=str(item.get('Description') or '').strip(),
                            role=str(item.get('Role') or 'Contact').strip(),
                            is_primary=_to_bool(item.get('Is Primary')),
                            created_by=user_id
                        )
                        created_count += 1

            else:
                return Response(
                    {"status": False, "message": "Invalid import type"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Mark file as imported and delete
        imported_path = file_path.replace("_pending", "_imported")
        try:
            os.rename(file_path, imported_path)
            os.remove(imported_path)
        except Exception as e:
            error_log.append(f"File cleanup warning: {str(e)}")

        return Response({
            "status": True,
            "message": "Import completed successfully",
            "summary": {
                "created": created_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "total_processed": created_count + updated_count + skipped_count
            },
            "errors": error_log
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"status": False, "message": f"Import failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
