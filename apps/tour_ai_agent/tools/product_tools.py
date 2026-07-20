from apps.vendors.models import Product

def get_product_details(product_id, organization_id=None):
    qs = Product.objects.filter(pk=product_id, status=Product.Status.ACTIVE)
    if organization_id:
        qs = qs.filter(organization_id=organization_id)
    product = qs.select_related("category").first()
    if not product:
        return {"ok": False, "error": "Product not found"}
    return {"ok": True, "product": {"id": product.id, "name": product.name, "price": str(product.price), "currency": product.currency, "in_stock": product.in_stock, "description": product.short_description}}
