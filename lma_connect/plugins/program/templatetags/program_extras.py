from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    """Lookup d[key] in a template — Django dicts only support string keys via dot."""
    if d is None:
        return None
    try:
        return d.get(key)
    except AttributeError:
        return None


@register.filter
def dim_value(rating, dim_key):
    """Return rating.rating_<dim_key> — used by the 4-dim rating template."""
    if rating is None:
        return 0
    return getattr(rating, f"rating_{dim_key}", 0) or 0
