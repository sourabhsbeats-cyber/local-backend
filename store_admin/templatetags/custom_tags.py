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

@register.filter
def get_item(dictionary, key):
    """
    Safely gets an item from a dictionary in templates.
    Usage: {{ mydict|get_item:"keyname" }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, "")
    return ""