from celery import shared_task

@shared_task
def index_product_visual(product_id):
    from django.utils import timezone
    from apps.vendors.models import Product
    from apps.tour_ai_agent.models import ProductVisualProfile
    from apps.tour_ai_agent.vision.preprocessing import sha256_file
    from apps.tour_ai_agent.vision.embeddings import image_embedding
    product = Product.objects.select_related("category").get(pk=product_id)
    if not product.cover_image:
        return {"ok": False, "reason": "no_image"}
    profile, _ = ProductVisualProfile.objects.get_or_create(product=product)
    profile.image_hash = sha256_file(product.cover_image.path)
    profile.visual_embedding = image_embedding(product.cover_image.path)
    profile.primary_category = product.category.name if product.category else ""
    profile.dominant_features = [product.name, product.short_description]
    profile.indexed_at = timezone.now()
    profile.save()
    return {"ok": True, "product_id": product.id}
