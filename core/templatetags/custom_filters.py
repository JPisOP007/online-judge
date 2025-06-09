from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.filter
def dict_get(d, key):
    return d.get(key)

@register.filter
def split(value, delimiter=","):
    return value.split(delimiter)


from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if dictionary is None:
        return None
    return dictionary.get(str(key))

@register.filter
def split(value, delimiter=','):
    if not value:
        return []
    return value.split(delimiter)

@register.filter
def default_if_none(value, default):
    return default if value is None else value