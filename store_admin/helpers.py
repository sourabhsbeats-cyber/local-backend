from decimal import Decimal, InvalidOperation
import re
import math
from datetime import datetime, date, timedelta

#from store_admin.models.product_model import PREP_TYPE_CHOICES
from django.core.exceptions import ValidationError


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


MOBILE_RE = re.compile(r"^[6-9]\d{9}$")


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
