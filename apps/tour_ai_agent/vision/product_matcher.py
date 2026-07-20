from apps.vendors.models import Product
from apps.tour_ai_agent.models import ProductVisualProfile,SceneProductMatch
from .embeddings import cosine_similarity
def match_scene_products(scene,labels,scene_embedding=None,limit=8):
    matches=[]; labels={str(x).lower() for x in labels}
    qs=Product.objects.filter(organization=scene.organization,status=Product.Status.ACTIVE).select_related('category')
    for p in qs:
        text=' '.join([p.name,p.short_description,p.category.name if p.category else '']).lower()
        lexical=sum(1 for x in labels if x in text)/max(1,len(labels))
        visual=0
        try: visual=cosine_similarity(scene_embedding,p.tour_ai_visual_profile.visual_embedding)
        except ProductVisualProfile.DoesNotExist: pass
        score=.65*lexical+.35*visual
        if score>.16: matches.append((score,p))
    for score,p in sorted(matches,reverse=True,key=lambda x:x[0])[:limit]:
        SceneProductMatch.objects.update_or_create(scene=scene,product=p,defaults={'confidence':score,'match_reason':'Local label and visual similarity'})
    return matches[:limit]
