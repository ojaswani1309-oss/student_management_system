from django import template

register = template.Library()


@register.filter
def grade_class(grade):
    """'A+' -> 'aplus', 'B' -> 'b' (used for CSS colour classes)."""
    return str(grade).replace('+', 'plus').replace('-', 'none').lower()


@register.filter
def pct_class(value):
    """Colour class for an attendance percentage."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 'low'
    return 'good' if value >= 85 else 'mid' if value >= 75 else 'low'
