from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Safely get an item from a dictionary by key."""
    if dictionary is None:
        return None
    if isinstance(dictionary, dict):
        return dictionary.get(str(key))
    return None

@register.filter
def dict_get(d, key):
    """Alias for get_item."""
    if d is None:
        return None
    return d.get(key)

@register.filter
def split(value, delimiter=','):
    """Split a string by delimiter."""
    if not value:
        return []
    return value.split(delimiter)

@register.filter
def default_if_none(value, default):
    """Return default if value is None."""
    return default if value is None else value