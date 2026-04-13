import glob
import os

import pandas as pd
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from store_admin.AuthHandler import StrictJWTCookieAuthentication
from django.conf import settings
from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.vendor_models import Vendor, VendorAddress, VendorBank, VendorContact, VendorStatus
from store_admin.views.vendors.vendor_import_utils import (
    extract_bank_records,
    extract_contact_records,
    find_existing_vendor,
    normalize_text,
    parse_bool,
    parse_decimal,
)


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

        if import_type != 'vendor':
            return Response({"status": False, "message": "Only vendor import is supported"}, status=status.HTTP_400_BAD_REQUEST)

        def upsert_address(vendor, prefix):
            address_line1 = normalize_text(item.get(f"{prefix} Address Line 1"))
            address_line2 = normalize_text(item.get(f"{prefix} Address Line 2"))
            city = normalize_text(item.get(f"{prefix} City"))
            state_value = normalize_text(item.get(f"{prefix} State"))
            post_code = normalize_text(item.get(f"{prefix} Post Code"))
            country = normalize_text(item.get(f"{prefix} Country"))
            attention = normalize_text(item.get(f"{prefix} Attention"))
            phone = normalize_text(item.get(f"{prefix} Phone"))
            fax = normalize_text(item.get(f"{prefix} Fax"))

            if not any([address_line1, address_line2, city, state_value, post_code, country, attention, phone, fax]):
                return

            address_obj = VendorAddress.objects.filter(vendor_id=vendor.id, address_type__iexact=prefix).first()
            if not address_obj:
                address_obj = VendorAddress(vendor_id=vendor.id, address_type=prefix.lower(), created_by=user_id)

            address_obj.attention = attention or None
            address_obj.address_line1 = address_line1 or None
            address_obj.address_line2 = address_line2 or None
            address_obj.suburb = city or None
            address_obj.state = state_value or None
            address_obj.post_code = post_code or None
            address_obj.country = country or None
            address_obj.phone = phone or None
            address_obj.fax = fax or None
            address_obj.save()

        def sync_contacts(vendor, contacts):
            if not contacts:
                return

            existing_contacts = list(VendorContact.objects.filter(vendor_id=vendor.id).order_by("-is_primary", "id"))
            for index, payload in enumerate(contacts):
                contact_obj = None
                if payload["email"]:
                    contact_obj = VendorContact.objects.filter(vendor_id=vendor.id, email__iexact=payload["email"]).first()
                if not contact_obj and index < len(existing_contacts):
                    contact_obj = existing_contacts[index]
                if not contact_obj:
                    contact_obj = VendorContact(vendor_id=vendor.id, created_by=user_id)

                contact_obj.first_name = payload["first_name"] or "Unknown"
                contact_obj.last_name = payload["last_name"] or "Unknown"
                contact_obj.email = payload["email"] or None
                contact_obj.phone = payload["phone"] or None
                contact_obj.mobile_no = payload["mobile_no"] or None
                contact_obj.department = payload["department"] or "Unknown"
                contact_obj.role = payload["role"] or "Contact"
                contact_obj.description = payload["description"] or None
                contact_obj.is_primary = payload["is_primary"]
                contact_obj.save()

        def sync_banks(vendor, banks):
            if not banks:
                return

            existing_banks = list(VendorBank.objects.filter(vendor_id=vendor.id).order_by("id"))
            for index, payload in enumerate(banks):
                bank_obj = None
                if payload["account_number"]:
                    bank_obj = VendorBank.objects.filter(vendor_id=vendor.id, account_number=payload["account_number"]).first()
                if not bank_obj and index < len(existing_banks):
                    bank_obj = existing_banks[index]
                if not bank_obj:
                    bank_obj = VendorBank(vendor_id=vendor.id, created_by=user_id)

                bank_obj.account_holder = payload["account_holder"] or "Unknown"
                bank_obj.bank_name = payload["bank_name"] or "Unknown"
                bank_obj.account_number = payload["account_number"] or "Unknown"
                bank_obj.bic = payload["bic"] or "Unknown"
                bank_obj.bank_branch = payload["bank_branch"] or None
                bank_obj.bank_country = payload["bank_country"] or None
                bank_obj.save()

        with transaction.atomic():
            for item in import_data:
                vendor_code = normalize_text(item.get('Vendor Code'))
                vendor_name = normalize_text(item.get('Vendor Name'))
                company_name = normalize_text(item.get('Company Name'))

                if not vendor_code or not vendor_name or not company_name:
                    skipped_count += 1
                    error_log.append("Row skipped: Vendor Code, Vendor Name and Company Name are required")
                    continue

                existing_vendor, ambiguous = find_existing_vendor(vendor_code, vendor_name, company_name)
                if ambiguous:
                    skipped_count += 1
                    error_log.append(f"Skipped vendor {vendor_code}: row matches multiple existing vendors")
                    continue

                if existing_vendor and duplicate_action == "skip":
                    skipped_count += 1
                    error_log.append(f"Skipped duplicate vendor: {vendor_code}")
                    continue

                raw_payment = normalize_text(item.get('Payment Term'))
                payment_term_id = None
                if raw_payment:
                    payment_term_obj = PaymentTerm.objects.filter(name__iexact=raw_payment).first()
                    if not payment_term_obj:
                        skipped_count += 1
                        error_log.append(f"Skipped vendor {vendor_code}: payment term '{raw_payment}' not found")
                        continue
                    payment_term_id = payment_term_obj.id

                status_name = normalize_text(item.get('Status'))
                try:
                    status_id = VendorStatus[status_name.upper().replace(' ', '_')].value if status_name else VendorStatus.PENDING
                except KeyError:
                    status_id = VendorStatus.PENDING

                vendor = existing_vendor or Vendor(created_by=user_id)
                vendor.vendor_code = vendor_code
                vendor.vendor_name = vendor_name
                vendor.vendor_company_name = company_name
                vendor.gst_number = normalize_text(item.get('GST Number')) or None
                vendor.payment_term = payment_term_id
                vendor.company_abn = normalize_text(item.get('Company ABN')) or None
                vendor.company_acn = normalize_text(item.get('Company ACN')) or None
                vendor.company_acc_no = normalize_text(item.get('Company Account No')) or None
                vendor.company_website = normalize_text(item.get('Company Website')) or None
                vendor.company_locality = normalize_text(item.get('Company Locality')) or None
                vendor.vendor_locality = normalize_text(item.get('Vendor Locality')) or None
                vendor.preferred_shipping_provider = normalize_text(item.get('Preferred Shipping Provider')) or None
                vendor.currency = normalize_text(item.get('Currency Code')) or None
                vendor.is_taxable = parse_bool(item.get('Taxable'))
                vendor.tax_percent = parse_decimal(item.get('Tax %'))
                vendor.min_order_value = parse_decimal(item.get('Min Order Value'))
                vendor.auto_detect_invoice = 'yes' if parse_bool(item.get('Auto Detect Invoice')) else 'no'
                vendor.allow_negative_balance = 'yes' if parse_bool(item.get('Allow Negative Balance')) else 'no'
                vendor.minimum_wallet_balance = parse_decimal(item.get('Minimum Wallet Balance'))
                vendor.low_balance_email = normalize_text(item.get('Low Balance Email')) or None
                vendor.wallet_type = normalize_text(item.get('Wallet Type')) or None
                vendor.wallet_notes = normalize_text(item.get('Wallet Notes')) or None
                vendor.credit_card_notes = normalize_text(item.get('Credit Card Notes')) or None
                vendor.paypal_notes = normalize_text(item.get('PayPal Notes')) or None
                vendor.accepted_card = normalize_text(item.get('Accepted Card')) or None
                vendor.payment_gateway = normalize_text(item.get('Payment Gateway')) or None
                vendor.processing_fee = parse_decimal(item.get('Processing Fee'))
                vendor.three_d_secure = normalize_text(item.get('Three D Secure')) or 'no'
                vendor.cardholder_name = normalize_text(item.get('Cardholder Name')) or None
                vendor.card_type = normalize_text(item.get('Card Type')) or None
                vendor.card_last_four = normalize_text(item.get('Card Last Four')) or None
                vendor.card_expiry = normalize_text(item.get('Card Expiry')) or None
                vendor.paypal_email = normalize_text(item.get('PayPal Email')) or None
                vendor.paypal_merchant_id = normalize_text(item.get('PayPal Merchant ID')) or None
                vendor.paypal_environment = normalize_text(item.get('PayPal Environment')) or 'sandbox'
                vendor.paypal_transaction_fee = parse_decimal(item.get('PayPal Transaction Fee'))
                vendor.status = status_id
                vendor.updated_by = user_id
                vendor.save()

                upsert_address(vendor, "Billing")
                upsert_address(vendor, "Shipping")
                sync_contacts(vendor, extract_contact_records(item))
                sync_banks(vendor, extract_bank_records(item))

                if existing_vendor:
                    updated_count += 1
                else:
                    created_count += 1

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
