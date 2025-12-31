from django import template

register = template.Library()

@register.filter
def upper_case(value):
    """Converts string to uppercase"""
    return value.upper()

@register.simple_tag
def format_currency(amount, symbol='$'):
    """Formats number with currency symbol"""
    return f"{symbol}{amount:,.2f}"

from decimal import Decimal, InvalidOperation
@register.filter
def aud(value):
    if value in (None, "",):
        return "$0.00"

    try:
        # remove commas if string
        value = str(value).replace(",", "")
        num = Decimal(value)
    except (InvalidOperation, ValueError):
        return value

    is_negative = num < 0
    num = abs(num)

    # format with commas and 2 decimals
    formatted = f"{num:,.2f}"

    return f"-${formatted}" if is_negative else f"${formatted}"

