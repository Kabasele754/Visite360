from django import template

register = template.Library()
CART_KEY = "vendor_cart_v1"


def _cart(context):
    request = context.get("request")
    if not request:
        return {}
    value = request.session.get(CART_KEY, {})
    return value if isinstance(value, dict) else {}


@register.simple_tag(takes_context=True)
def cart_product_count(context):
    """Number of distinct products, not the sum of quantities."""
    return len([key for key, qty in _cart(context).items() if int(qty or 0) > 0])


@register.simple_tag(takes_context=True)
def product_cart_quantity(context, product):
    return int(_cart(context).get(str(product.pk), 0) or 0)


@register.simple_tag(takes_context=True)
def product_is_in_cart(context, product):
    return int(_cart(context).get(str(product.pk), 0) or 0) > 0
