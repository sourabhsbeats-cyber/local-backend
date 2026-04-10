import glob
import os

import pandas as pd
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from store_admin.AuthHandler import StrictJWTCookieAuthentication
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.vendor_models import Vendor, VendorContact, VendorStatus


def clean_val(v):
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else v


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
def confirm_import_vendor(request):
    import_type = request.data.get('import_type')
    file_id = request.data.get('file_id')
    duplicate_action = normalize_duplicate_action(request.data.get('duplicate_action'))
    user_id = request.user.id

    if not import_type or not file_id:
        return Response({"status": False, "message": "file_id and import_type are required"}, status=status.HTTP_400_BAD_REQUEST)

    if duplicate_action not in ["skip", "update"]:
        return Response({"status": False, "message": "Invalid duplicate_action"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        upload_dir = os.path.join(settings.MEDIA_ROOT, "imports")
        matches = glob.glob(os.path.join(upload_dir, f"{file_id}_pending.*"))

        if not matches:
            return Response({"status": False, "message": "Import file not found"}, status=status.HTTP_400_BAD_REQUEST)

        file_path = matches[0]
        ext = os.path.splitext(file_path)[1].lower()

        df = pd.read_csv(file_path) if ext == ".csv" else pd.read_excel(file_path)
        df.columns = [c.strip() for c in df.columns]
        df = df.where(pd.notnull(df), None)

        import_data = df.to_dict(orient="records")

        if not import_data:
            return Response({"status": False, "message": "No data found in import file"}, status=status.HTTP_400_BAD_REQUEST)

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

                    raw_payment = clean_val(item.get('Payment Term'))
                    payment_term_id = None
                    if raw_payment:
                        payment_term_obj = PaymentTerm.objects.filter(name__iexact=raw_payment).first()
                        if payment_term_obj:
                            payment_term_id = payment_term_obj.id
                        else:
                            skipped_count += 1
                            error_log.append(f"Payment term '{raw_payment}' not found")
                            continue

                    raw_tax = clean_val(item.get('Tax %'))
                    tax_percent = float(raw_tax) if raw_tax is not None else 0.0

                    raw_acct = clean_val(item.get('Bank Account Number'))
                    account_number = None
                    if raw_acct is not None:
                        account_number = str(int(raw_acct)) if isinstance(raw_acct, (int, float)) else str(raw_acct).strip()

                    status_name = (item.get('Status') or '').strip()
                    try:
                        status_id = VendorStatus[status_name.upper().replace(' ', '_')].value if status_name else VendorStatus.PENDING
                    except KeyError:
                        status_id = VendorStatus.PENDING

                    existing_vendor = Vendor.objects.filter(Q(vendor_code=vendor_code) | Q(vendor_name__iexact=vendor_name)).first()

                    if existing_vendor:
                        if duplicate_action == "skip":
                            skipped_count += 1
                            error_log.append(f"Skipped duplicate vendor: {vendor_code}")
                            continue

                        vendor = existing_vendor
                        vendor.payment_term_id = payment_term_id
                        vendor.company_abn = clean_val(item.get('Company ABN'))
                        vendor.company_acn = clean_val(item.get('Company ACN'))
                        vendor.is_taxable = 0 if str(item.get('Taxable', '')).lower() == 'yes' else 1
                        vendor.tax_percent = tax_percent
                        vendor.bank_name = clean_val(item.get('Bank Name'))
                        vendor.bank_branch = clean_val(item.get('Bank Branch'))
                        vendor.account_number = account_number
                        vendor.currency = clean_val(item.get('Currency Code'))
                        vendor.status = status_id
                        vendor.updated_by = user_id
                        vendor.save()
                        updated_count += 1
                    else:
                        Vendor.objects.create(
                            vendor_code=vendor_code,
                            vendor_name=vendor_name,
                            gst_number=clean_val(item.get('GST Number')),
                            payment_term_id=payment_term_id,
                            company_abn=clean_val(item.get('Company ABN')),
                            company_acn=clean_val(item.get('Company ACN')),
                            is_taxable=0 if str(item.get('Taxable', '')).lower() == 'yes' else 1,
                            tax_percent=tax_percent,
                            bank_name=clean_val(item.get('Bank Name')),
                            bank_branch=clean_val(item.get('Bank Branch')),
                            account_number=account_number,
                            currency=clean_val(item.get('Currency Code')),
                            created_by=user_id,
                            updated_by=user_id,
                            status=status_id
                        )
                        created_count += 1

            elif import_type == 'contact':
                for item in import_data:
                    vendor_code = str(item.get('Vendor Code', '')).strip()
                    email = str(item.get('Email', '')).strip().lower()

                    if not vendor_code or not email:
                        skipped_count += 1
                        error_log.append("Row skipped: Missing Vendor Code or Email")
                        continue

                    vendor = Vendor.objects.filter(vendor_code=vendor_code).first()
                    if not vendor:
                        skipped_count += 1
                        error_log.append(f"Vendor {vendor_code} not found")
                        continue

                    existing_contact = VendorContact.objects.filter(vendor_id=vendor.id, email=email).first()
                    if existing_contact:
                        if duplicate_action == "skip":
                            skipped_count += 1
                            error_log.append(f"Skipped duplicate contact: {email}")
                            continue

                        contact = existing_contact
                        contact.first_name = str(item.get('First Name') or '').strip()
                        contact.last_name = str(item.get('Last Name') or '').strip()
                        contact.department = str(item.get('Department') or '').strip()
                        contact.phone = str(item.get('Phone') or '').replace('.0', '')
                        contact.description = str(item.get('Description') or '').strip()
                        contact.role = str(item.get('Role') or 'Contact').strip()
                        contact.save()
                        updated_count += 1
                    else:
                        VendorContact.objects.create(
                            vendor_id=vendor.id,
                            email=email,
                            first_name=str(item.get('First Name') or '').strip(),
                            last_name=str(item.get('Last Name') or '').strip(),
                            department=str(item.get('Department') or '').strip(),
                            phone=str(item.get('Phone') or '').replace('.0', ''),
                            description=str(item.get('Description') or '').strip(),
                            role=str(item.get('Role') or 'Contact').strip(),
                            created_by=user_id
                        )
                        created_count += 1
            else:
                return Response({"status": False, "message": "Invalid import type"}, status=status.HTTP_400_BAD_REQUEST)

        imported_path = file_path.replace("_pending", "_imported")
        try:
            os.rename(file_path, imported_path)
            os.remove(imported_path)
        except Exception as cleanup_error:
            error_log.append(f"Cleanup failed: {cleanup_error}")

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
        return Response({"status": False, "message": f"Import failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
