
from django import template

register = template.Library()

@register.filter
def replace(value, arg):
    if ',' not in arg:
        return value
    bits = arg.split(',')
    return value.replace(bits[0], bits[1])

import math
@register.filter(name='get_item')
def get_item(row, key):
    """Allows dictionary key access using a variable key (e.g., {{ row|get_item:h }})."""
    #return dictionary.get(key)
    if not row or not hasattr(row, 'get'):
        return ""
    value = row.get(key)

    # Handle NaN
    if isinstance(value, float) and math.isnan(value):
        return ""

    # Special handling for EAN / UPC
    if str(key).upper() in ["EAN", "UPC"]:
        if value is None:
            return ""
        value_str = str(value)

        # Convert float strings like "9421910000000.0" → "9421910000000"
        if value_str.endswith(".0"):
            value_str = value_str[:-2]

        return value_str

    return value


@register.filter
def hide_none(value):
    """Replaces None with an empty string."""
    return '' if value is None else value

#<p>Email: {{ vendor.email_address | hide_none }}</p>

@register.filter
def aud(value):
    try:
        num = float(value)
    except (ValueError, TypeError):
        return value

    return "${:,.2f}".format(num)