
from django import template

register = template.Library()

@register.filter
def replace(value, arg):
    old, new = arg.split(',')
    return value.replace(old, new)


@register.filter(name='get_item')
def get_item(dictionary, key):
    """Allows dictionary key access using a variable key (e.g., {{ row|get_item:h }})."""
    return dictionary.get(key)
