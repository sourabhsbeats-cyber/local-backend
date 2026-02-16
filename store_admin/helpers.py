from decimal import Decimal, InvalidOperation
import re
import math
from datetime import datetime, date, timedelta

#from store_admin.models.product_model import PREP_TYPE_CHOICES
from django.core.exceptions import ValidationError

from store_admin.models import StoreUser
from store_admin.models.po_models.po_models import PurchaseOrder


# -------------------------------------------------
# Basic sanitizers
# -------------------------------------------------

def to_str(val):
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    if str(val).lower() == "nan":
        return ""
    return str(val).strip()


def safe_int(val, default=None):
    s = to_str(val)
    try:
        return int(float(s))
    except:
        return default

def getUserName(user_id):
    return StoreUser.objects.get(id=user_id).name

def to_int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

from django.utils.dateformat import format as df
def safe_df(value, fmt):
    return df(value, fmt) if value else "-"

def safe_decimal(val, default=None):
    s = to_str(val)
    if not s:
        return default
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError, TypeError):
        return default


def bool_from_str(val):
    return to_str(val).lower() in ["1", "yes", "true", "y"]


# -------------------------------------------------
# Duration conversion
# -------------------------------------------------

def convert_to_months(value):
    if not value:
        return None

    v = str(value).strip().lower()

    y_match = re.search(r'(\d+(?:\.\d+)?)\s*(year|y)', v)
    m_match = re.search(r'(\d+(?:\.\d+)?)\s*(month|m)', v)
    d_match = re.search(r'(\d+(?:\.\d+)?)\s*(day|d)', v)

    years = Decimal(y_match.group(1)) if y_match else Decimal(0)
    months = Decimal(m_match.group(1)) if m_match else Decimal(0)
    days = Decimal(d_match.group(1)) if d_match else Decimal(0)

    total = years * Decimal(12) + months + (days / Decimal(30))

    return int(total) if total == int(total) else float(round(total, 2))


# -------------------------------------------------
# Boolean conversions
# -------------------------------------------------

def to_boolean_int(value_list):
    if not value_list or not value_list[0]:
        return None
    return 1 if str(value_list[0]).lower() in ['true', '1', 'on'] else 0


def to_int_bool(value_list):
    value = value_list[0] if isinstance(value_list, list) and value_list else None
    if value is None:
        return None
    v = str(value).lower()
    if v in ('true', '1', 'on'):
        return 1
    if v in ('false', '0', 'off'):
        return 0
    return None


# -------------------------------------------------
# Safe getters
# -------------------------------------------------

def get_decimal(data, key):
    raw = data.get(key)
    if raw is None:
        return None
    try:
        value = raw.strip()
        return Decimal(value) if value else None
    except (InvalidOperation, AttributeError):
        return None


def get_int(data, key):
    try:
        raw = data.get(key)
        return int(raw.strip()) if raw and raw.strip().lstrip("-").isdigit() else None
    except:
        return None


def get_bool_int(data, key):
    raw = data.get(key) if hasattr(data, "get") else data[key] if key in data else None
    if raw is None:
        return None

    raw = str(raw).strip().lower()
    if raw in ("true", "1", "yes", "y"):
        return 1
    if raw in ("false", "0", "no", "n"):
        return 0
    return None


# -------------------------------------------------
# Validators
# -------------------------------------------------

NAME_RE = re.compile(r"^(?:[A-Za-z\.]{2,}\s+)*[A-Za-z]{2,}(?:\s*,\s*[A-Za-z]{2,})?(?:\s+[A-Za-z]{2,})*$")


def name_validator_none(value):
    if value is None or str(value).strip() == "":
        return value

    _NAME_RE = re.compile(r'^[A-Za-z0-9 ,/.\&-]{4,}$')
    v = str(value).strip()

    if len(v) < 4:
        raise ValidationError("Must be at least 4 characters long.")

    if not _NAME_RE.match(v):
        raise ValidationError(
            "Invalid format. Allowed: letters, numbers, spaces, commas(,), slash(/), dot(.), ampersand(&), hyphen(-)."
        )
    return v


def zip_validator(value):
    if value is None:
        return value
    v = str(value).strip()
    if not v.isdigit():
        raise ValidationError("ZIP code must be numeric")
    return v


def reference_validator(value):
    if value is None or str(value).strip() == "":
        return value
    v = str(value).strip()
    if not re.match(r'^[A-Za-z0-9-]{3,}$', v):
        raise ValidationError("Invalid reference format")
    return v


def date_validator(value, allowed_past_days=0):
    if value is None or value == "":
        return value

    if isinstance(value, str):
        try:
            value = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError("Invalid date format (expected YYYY-MM-DD).")

    min_allowed_date = date.today() - timedelta(days=allowed_past_days)

    if value < min_allowed_date:
        raise ValidationError(
            f"Date cannot be older than {allowed_past_days} days before today."
        )
    return value

from datetime import datetime
def parse_date_or_none(value):
    if not value:
        return None

        # Pandas Timestamp or datetime
    if hasattr(value, "date"):
        return value.date()

    value = str(value).strip()

    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    return None

def name_validator(value):
    if value is None or value.strip() == "":
        return
    value = value.strip()
    if not NAME_RE.fullmatch(value):
        raise ValidationError("Invalid Name.")


EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}$")


def email_validator(value):
    if value is None or value.strip() == "":
        return
    value = value.strip()
    if not EMAIL_RE.fullmatch(value):
        raise ValidationError("Enter a valid email address.")


MOBILE_RE = re.compile(r"^[0-9]\d{9}$")


def mobile_validator(value):
    if value is None or value.strip() == "":
        return
    value = value.strip()
    if not MOBILE_RE.fullmatch(value):
        raise ValidationError("Enter a valid 10-digit mobile number.")


SKU_RE = re.compile(r'^(?=.{3,}$)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$')


def validate_sku(value):
    if value is None or str(value).strip() == "":
        raise ValidationError("SKU is required.")

    v = value.strip()

    if not SKU_RE.fullmatch(v):
        raise ValidationError(
            "Invalid SKU. Use letters, digits and '-' only. "
            "Minimum 3 characters. Cannot start/end with '-' or contain consecutive '-'."
        )


def validate_title_like_name(value: str):
    NAME_RE2 = re.compile(
        r'^(?:[A-Za-z\.]{2,}\s+)*'
        r'[A-Za-z]{2,}'
        r'(?:\s*,\s*[A-Za-z]{2,}|\s+[A-Za-z]{2,})*$'
    )

    if value is None or str(value).strip() == "":
        raise ValidationError("This field cannot be blank.")

    v = value.strip()

    if not NAME_RE2.fullmatch(v):
        raise ValidationError("Invalid format. Use letters (min 2 letters per part), optional '.' or one comma.")


def get_prep_label(code):
    from store_admin.models.product_model import PREP_TYPE_CHOICES
    return dict(PREP_TYPE_CHOICES).get(code, "")


from decimal import ROUND_HALF_UP
def format_tax_percentage(value):
    if value in (None, "", 0, "0", "0.0", "0.00"):
        return ""
    val = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if val == val.to_integral():
        return f"{int(val)}%"
    return f"{val}%"


''' Purchase Helper Function '''

def validate_purchase_order_model(po, line_items):
    rules = [
        ("vendor_id",       "Vendor is required"),
        #("vendor_name",     "Vendor Name is required"),
        ("po_number",       "PO Number is required."),
        ("currency_code",   "Currency Code is required"),
        #("vendor_reference","Vendor Reference is required"),
        ("warehouse_id",    "Warehouse is required"),
        ("order_date",      "Order Date is required"),
        #("delivery_date",   "Delivery Date is required"),
        #("payment_term_id", "Payment Term is required"),
       # ("delivery_name",   "Delivery Name is required"),
        ("address_line1",   "Address Line 1 is required"),
        ("state",           "State is required"),
        ("post_code",       "Postcode is required"),
        ("country_id",      "Country is required"),
       # ("tax_percentage",  "Tax Percentage is required"),
    ]

    # Loop the model fields
    for field, err_msg in rules:
        value = getattr(po, field, None)
        if value is None or str(value).strip() == "":
            return False, err_msg

    # Line items check
    if not line_items or len(line_items) == 0:
        return False, "Please add at least one product line item"

    #if PurchaseOrder.objects.filter(vendor_reference=po.vendor_reference).exclude(po_id=po.po_id).exists():
    #    return False, "Can not duplicate Vendor Reference#."

    if PurchaseOrder.objects.filter(po_number=po.po_number).exclude(po_id=po.po_id).exists():
        return False, "Can not duplicate Purchase Order Number."

    if po.vendor_reference and len(po.vendor_reference) >= 1:
        if len(po.vendor_reference) < 4:
            return False, "Invalid Vendor Reference1."
    #try:
    #    name_validator_none(po.vendor_name)
   #except ValidationError as e:
    #    return False, "Invalid vendor name."

    try:
        name_validator_none(po.delivery_name)
    except ValidationError as e:
        return False, "Invalid delivery name."

    try:
        name_validator_none(po.address_line1)
        #name_validator_none(po.address_line2)
    except ValidationError as e:
        return False, "Invalid address line."

    try:
        name_validator_none(po.state)
    except ValueError:
        return False, "Invalid state name."

    try:
        zip_validator(po.post_code)
    except ValueError:
        return False, "Postcode must be numeric."

        # Reference format
    try:
        reference_validator(po.vendor_reference)
    except ValueError:
        return False, "Invalid Vendor Reference# format."

        # Delivery date >= today
    #validate date now its not needed temporarily
    '''
    try:
        date_validator(po.delivery_date, 10)
        date_validator(po.order_date, 10)
    except ValueError as e:
        return False, str(e)
    '''

    return True, ""