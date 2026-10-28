"""
Custom template filters for facilities app.
"""

from django import template

register = template.Library()


@register.filter
def split(value, delimiter):
    """
    Split a string by delimiter.
    
    Usage: {{ "a,b,c"|split:"," }}
    
    Args:
        value: String to split
        delimiter: Delimiter to split by
        
    Returns:
        List of split strings
    """
    if not value:
        return []
    return value.split(delimiter)
