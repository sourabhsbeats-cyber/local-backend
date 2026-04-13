from decimal import Decimal, InvalidOperation

import pandas as pd
from django.db.models import Count, Q

from store_admin.models.payment_terms_model import PaymentTerm
from store_admin.models.vendor_models import Vendor, VendorAddress, VendorBank, VendorContact


CORE_REQUIRED_COLUMNS = ["Vendor Code", "Vendor Name", "Company Name"]

BASE_VENDOR_COLUMNS = [
    "Vendor Code",
    "Vendor Name",
    "Company Name",
    "GST Number",
    "Status",
    "Payment Term",
    "Currency Code",
    "Taxable",
    "Tax %",
    "Min Order Value",
    "Company ABN",
    "Company ACN",
    "Company Account No",
    "Company Website",
    "Company Locality",
    "Vendor Locality",
    "Preferred Shipping Provider",
    "Auto Detect Invoice",
    "Allow Negative Balance",
    "Minimum Wallet Balance",
    "Low Balance Email",
    "Wallet Type",
    "Wallet Notes",
    "Credit Card Notes",
    "PayPal Notes",
    "Accepted Card",
    "Payment Gateway",
    "Processing Fee",
    "Three D Secure",
    "Cardholder Name",
    "Card Type",
    "Card Last Four",
    "Card Expiry",
    "PayPal Email",
    "PayPal Merchant ID",
    "PayPal Environment",
    "PayPal Transaction Fee",
    "Billing Attention",
    "Billing Address Line 1",
    "Billing Address Line 2",
    "Billing City",
    "Billing State",
    "Billing Post Code",
    "Billing Country",
    "Billing Phone",
    "Billing Fax",
    "Shipping Attention",
    "Shipping Address Line 1",
    "Shipping Address Line 2",
    "Shipping City",
    "Shipping State",
    "Shipping Post Code",
    "Shipping Country",
    "Shipping Phone",
    "Shipping Fax",
]

CONTACT_FIELD_SUFFIXES = [
    "First Name",
    "Last Name",
    "Email",
    "Phone",
    "Mobile",
    "Department",
    "Role",
    "Description",
    "Is Primary",
]

BANK_FIELD_SUFFIXES = [
    "Account Holder",
    "Bank Name",
    "Account Number",
    "BIC",
    "Branch",
    "Country",
]


def normalize_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def normalize_email(value):
    return normalize_text(value).lower()


def truthy_to_yes_no(value):
    text = normalize_text(value).lower()
    return "Yes" if text in {"1", "true", "yes", "y"} else "No"


def parse_bool(value, default=False):
    text = normalize_text(value).lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "y"}


def parse_decimal(value, default="0"):
    text = normalize_text(value)
    if not text:
        return Decimal(default)
    try:
        return Decimal(text)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def get_payment_term_name(payment_term_id):
    if payment_term_id in [None, ""]:
        return ""
    term = PaymentTerm.objects.filter(id=payment_term_id).first()
    return term.name if term else ""


def get_dynamic_vendor_columns(contact_count=1, bank_count=1):
    columns = list(BASE_VENDOR_COLUMNS)

    for index in range(1, max(contact_count, 1) + 1):
        for suffix in CONTACT_FIELD_SUFFIXES:
            columns.append(f"Contact {index} {suffix}")

    for index in range(1, max(bank_count, 1) + 1):
        for suffix in BANK_FIELD_SUFFIXES:
            columns.append(f"Bank {index} {suffix}")

    return columns


def get_dynamic_counts():
    max_contacts = max(
        list(Vendor.objects.annotate(total_contacts=Count("contacts")).values_list("total_contacts", flat=True)) or [0]
    )
    max_banks = max(
        list(Vendor.objects.annotate(total_banks=Count("banks")).values_list("total_banks", flat=True)) or [0]
    )
    return max(max_contacts, 1), max(max_banks, 1)


def get_address_map(vendor):
    addresses = {}
    for address in VendorAddress.objects.filter(vendor_id=vendor.id):
        addresses[address.address_type.strip().lower()] = address
    return addresses


def build_vendor_export_row(vendor, contact_slots, bank_slots):
    addresses = get_address_map(vendor)
    billing = addresses.get("billing")
    shipping = addresses.get("shipping")

    row = {
        "Vendor Code": vendor.vendor_code or "",
        "Vendor Name": vendor.vendor_name or "",
        "Company Name": vendor.vendor_company_name or "",
        "GST Number": vendor.gst_number or "",
        "Status": vendor.get_status_display() if vendor.status is not None else "",
        "Payment Term": get_payment_term_name(vendor.payment_term),
        "Currency Code": vendor.currency or "",
        "Taxable": "Yes" if vendor.is_taxable else "No",
        "Tax %": vendor.tax_percent,
        "Min Order Value": vendor.min_order_value,
        "Company ABN": vendor.company_abn or "",
        "Company ACN": vendor.company_acn or "",
        "Company Account No": vendor.company_acc_no or "",
        "Company Website": vendor.company_website or "",
        "Company Locality": vendor.company_locality or "",
        "Vendor Locality": vendor.vendor_locality or "",
        "Preferred Shipping Provider": vendor.preferred_shipping_provider or "",
        "Auto Detect Invoice": truthy_to_yes_no(vendor.auto_detect_invoice),
        "Allow Negative Balance": truthy_to_yes_no(vendor.allow_negative_balance),
        "Minimum Wallet Balance": vendor.minimum_wallet_balance,
        "Low Balance Email": vendor.low_balance_email or "",
        "Wallet Type": vendor.wallet_type or "",
        "Wallet Notes": vendor.wallet_notes or "",
        "Credit Card Notes": vendor.credit_card_notes or "",
        "PayPal Notes": vendor.paypal_notes or "",
        "Accepted Card": vendor.accepted_card or "",
        "Payment Gateway": vendor.payment_gateway or "",
        "Processing Fee": vendor.processing_fee,
        "Three D Secure": vendor.three_d_secure or "",
        "Cardholder Name": vendor.cardholder_name or "",
        "Card Type": vendor.card_type or "",
        "Card Last Four": vendor.card_last_four or "",
        "Card Expiry": vendor.card_expiry or "",
        "PayPal Email": vendor.paypal_email or "",
        "PayPal Merchant ID": vendor.paypal_merchant_id or "",
        "PayPal Environment": vendor.paypal_environment or "",
        "PayPal Transaction Fee": vendor.paypal_transaction_fee,
        "Billing Attention": getattr(billing, "attention", "") or "",
        "Billing Address Line 1": getattr(billing, "address_line1", "") or "",
        "Billing Address Line 2": getattr(billing, "address_line2", "") or "",
        "Billing City": getattr(billing, "suburb", "") or "",
        "Billing State": getattr(billing, "state", "") or "",
        "Billing Post Code": getattr(billing, "post_code", "") or "",
        "Billing Country": getattr(billing, "country", "") or "",
        "Billing Phone": getattr(billing, "phone", "") or "",
        "Billing Fax": getattr(billing, "fax", "") or "",
        "Shipping Attention": getattr(shipping, "attention", "") or "",
        "Shipping Address Line 1": getattr(shipping, "address_line1", "") or "",
        "Shipping Address Line 2": getattr(shipping, "address_line2", "") or "",
        "Shipping City": getattr(shipping, "suburb", "") or "",
        "Shipping State": getattr(shipping, "state", "") or "",
        "Shipping Post Code": getattr(shipping, "post_code", "") or "",
        "Shipping Country": getattr(shipping, "country", "") or "",
        "Shipping Phone": getattr(shipping, "phone", "") or "",
        "Shipping Fax": getattr(shipping, "fax", "") or "",
    }

    contacts = list(VendorContact.objects.filter(vendor_id=vendor.id).order_by("-is_primary", "id"))
    for index in range(1, contact_slots + 1):
        contact = contacts[index - 1] if index - 1 < len(contacts) else None
        row.update({
            f"Contact {index} First Name": getattr(contact, "first_name", "") or "",
            f"Contact {index} Last Name": getattr(contact, "last_name", "") or "",
            f"Contact {index} Email": getattr(contact, "email", "") or "",
            f"Contact {index} Phone": getattr(contact, "phone", "") or "",
            f"Contact {index} Mobile": getattr(contact, "mobile_no", "") or "",
            f"Contact {index} Department": getattr(contact, "department", "") or "",
            f"Contact {index} Role": getattr(contact, "role", "") or "",
            f"Contact {index} Description": getattr(contact, "description", "") or "",
            f"Contact {index} Is Primary": "Yes" if getattr(contact, "is_primary", False) else "No",
        })

    banks = list(VendorBank.objects.filter(vendor_id=vendor.id).order_by("id"))
    for index in range(1, bank_slots + 1):
        bank = banks[index - 1] if index - 1 < len(banks) else None
        row.update({
            f"Bank {index} Account Holder": getattr(bank, "account_holder", "") or "",
            f"Bank {index} Bank Name": getattr(bank, "bank_name", "") or "",
            f"Bank {index} Account Number": getattr(bank, "account_number", "") or "",
            f"Bank {index} BIC": getattr(bank, "bic", "") or "",
            f"Bank {index} Branch": getattr(bank, "bank_branch", "") or "",
            f"Bank {index} Country": getattr(bank, "bank_country", "") or "",
        })

    return row


def find_existing_vendor(vendor_code, vendor_name, company_name):
    filters = Q()
    if vendor_code:
        filters |= Q(vendor_code__iexact=vendor_code)
    if vendor_name:
        filters |= Q(vendor_name__iexact=vendor_name)
    if company_name:
        filters |= Q(vendor_company_name__iexact=company_name)

    if not filters:
        return None, False

    matches = list(Vendor.objects.filter(filters).order_by("id"))
    if not matches:
        return None, False

    unique_ids = {match.id for match in matches}
    if len(unique_ids) > 1:
        return None, True

    return matches[0], False


def validate_vendor_row(row, row_num, seen_codes, seen_names, seen_companies):
    errors = []
    vendor_code = normalize_text(row.get("Vendor Code"))
    vendor_name = normalize_text(row.get("Vendor Name"))
    company_name = normalize_text(row.get("Company Name"))

    if not vendor_code:
        errors.append({"row": row_num, "column": "Vendor Code", "message": "Vendor Code is required"})
    if not vendor_name:
        errors.append({"row": row_num, "column": "Vendor Name", "message": "Vendor Name is required"})
    if not company_name:
        errors.append({"row": row_num, "column": "Company Name", "message": "Company Name is required"})

    code_key = vendor_code.lower()
    name_key = vendor_name.lower()
    company_key = company_name.lower()

    if code_key:
        if code_key in seen_codes:
            errors.append({"row": row_num, "column": "Vendor Code", "message": "Duplicate vendor code in file"})
        else:
            seen_codes.add(code_key)
    if name_key:
        if name_key in seen_names:
            errors.append({"row": row_num, "column": "Vendor Name", "message": "Duplicate vendor name in file"})
        else:
            seen_names.add(name_key)
    if company_key:
        if company_key in seen_companies:
            errors.append({"row": row_num, "column": "Company Name", "message": "Duplicate company name in file"})
        else:
            seen_companies.add(company_key)

    raw_payment_term = normalize_text(row.get("Payment Term"))
    if raw_payment_term and not PaymentTerm.objects.filter(name__iexact=raw_payment_term).exists():
        errors.append({"row": row_num, "column": "Payment Term", "message": f"Payment term '{raw_payment_term}' not found"})

    existing_vendor, ambiguous = find_existing_vendor(vendor_code, vendor_name, company_name)
    if ambiguous:
        errors.append({
            "row": row_num,
            "column": "Vendor Code / Vendor Name / Company Name",
            "message": "These references match multiple existing vendors. Please correct the row before importing.",
        })
    elif existing_vendor:
        if vendor_code and existing_vendor.vendor_code.lower() != vendor_code.lower():
            errors.append({"row": row_num, "column": "Vendor Code", "message": "Vendor Code conflicts with an existing vendor"})
        if vendor_name and existing_vendor.vendor_name.lower() != vendor_name.lower():
            errors.append({"row": row_num, "column": "Vendor Name", "message": "Vendor Name conflicts with an existing vendor"})
        if company_name and existing_vendor.vendor_company_name.lower() != company_name.lower():
            errors.append({"row": row_num, "column": "Company Name", "message": "Company Name conflicts with an existing vendor"})

    return errors


def extract_contact_records(row):
    contacts = []
    index = 1
    while f"Contact {index} First Name" in row or f"Contact {index} Email" in row:
        contact = {
            "first_name": normalize_text(row.get(f"Contact {index} First Name")),
            "last_name": normalize_text(row.get(f"Contact {index} Last Name")),
            "email": normalize_email(row.get(f"Contact {index} Email")),
            "phone": normalize_text(row.get(f"Contact {index} Phone")),
            "mobile_no": normalize_text(row.get(f"Contact {index} Mobile")),
            "department": normalize_text(row.get(f"Contact {index} Department")),
            "role": normalize_text(row.get(f"Contact {index} Role")),
            "description": normalize_text(row.get(f"Contact {index} Description")),
            "is_primary": parse_bool(row.get(f"Contact {index} Is Primary")),
        }
        if any(contact.values()):
            contacts.append(contact)
        index += 1
    return contacts


def extract_bank_records(row):
    banks = []
    index = 1
    while f"Bank {index} Account Holder" in row or f"Bank {index} Account Number" in row:
        bank = {
            "account_holder": normalize_text(row.get(f"Bank {index} Account Holder")),
            "bank_name": normalize_text(row.get(f"Bank {index} Bank Name")),
            "account_number": normalize_text(row.get(f"Bank {index} Account Number")),
            "bic": normalize_text(row.get(f"Bank {index} BIC")),
            "bank_branch": normalize_text(row.get(f"Bank {index} Branch")),
            "bank_country": normalize_text(row.get(f"Bank {index} Country")),
        }
        if any(bank.values()):
            banks.append(bank)
        index += 1
    return banks
