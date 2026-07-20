from apps.vendors.models import Product

def add_product_to_cart(request, product_id, quantity=1):
    product = Product.objects.filter(pk=product_id, status=Product.Status.ACTIVE).first()
    if not product:
        return {"ok": False, "error": "Product not found"}
    cart = request.session.get("vendor_cart", {})
    key = str(product.id)
    cart[key] = max(1, int(cart.get(key, 0)) + max(1, int(quantity)))
    request.session["vendor_cart"] = cart
    request.session.modified = True
    return {"ok": True, "product_id": product.id, "quantity": cart[key], "cart_count": sum(int(v) for v in cart.values())}
