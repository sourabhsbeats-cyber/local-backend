from decimal import Decimal, InvalidOperation
import re
import math
def to_str(val):
    if val is None:
        return ""
        # ✅ Detect NaN (float or numpy)
    if isinstance(val, float) and math.isnan(val):
        return ""
        # Also covers numpy NaN
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

def convert_to_months(value):
    if not value:
        return None

    v = str(value).strip().lower()

    # Extract numbers as Decimal
    y_match = re.search(r'(\d+(?:\.\d+)?)\s*(year|y)', v)
    m_match = re.search(r'(\d+(?:\.\d+)?)\s*(month|m)', v)
    d_match = re.search(r'(\d+(?:\.\d+)?)\s*(day|d)', v)

    years = Decimal(y_match.group(1)) if y_match else Decimal(0)
    months = Decimal(m_match.group(1)) if m_match else Decimal(0)
    days = Decimal(d_match.group(1)) if d_match else Decimal(0)

    total = years * Decimal(12) + months + (days / Decimal(30))  # ✅ pure Decimal math

    # Return int if whole number, else 2-decimal float for UI readability
    return int(total) if total == int(total) else float(round(total, 2))



def to_boolean_int(value_list):
    if not value_list or not value_list[0]:
        return None  # Or 0, depending on your default logic for an unchecked box

    return 1 if str(value_list[0]).lower() in ['true', '1', 'on'] else 0

def to_int_bool(value_list):
    value = value_list[0] if isinstance(value_list, list) and value_list else None
    if value is None:
        return None
    value_lower = str(value).lower()
    if value_lower in ('true', '1', 'on'):
        return 1
    if value_lower in ('false', '0', 'off'):
        return 0
    return None

from decimal import Decimal, InvalidOperation

def get_decimal(data, key):
    raw = data.get(key)
    if raw is None:
        return None
    try:
        value = raw.strip()
        return Decimal(value) if value else None
    except (InvalidOperation, AttributeError):
        return None


from typing import Optional, List, Union


def get_int(data, key):
    try:
        raw = data.get(key)
        return int(raw.strip()) if raw and raw.strip().lstrip("-").isdigit() else None
    except Exception as e:
        print(e)
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

