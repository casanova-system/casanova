from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """Multiplica dois valores."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def sum_peso_total(itens):
    """Soma o peso total (peso * quantidade) de uma lista de itens."""
    try:
        return sum(float(item.peso) * float(item.quantidade) for item in itens)
    except (ValueError, TypeError, AttributeError):
        return 0