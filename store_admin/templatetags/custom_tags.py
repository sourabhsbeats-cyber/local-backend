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

