from .conversion import analyze_conversion
from .seo import analyze_seo
from .traffic import analyze_traffic

def analyze_marketing(organization, days=30):
    traffic = analyze_traffic(organization, days); seo = analyze_seo(organization, days); conversion = analyze_conversion(organization, days)
    actions = []
    if seo["opportunities"]: actions.append({"priority": "high", "action": "Optimize high-impression keywords with weak CTR", "count": len(seo["opportunities"])})
    if conversion["rates"]["view_to_cart"] < 3: actions.append({"priority": "high", "action": "Improve product cards, price clarity and calls to action"})
    if conversion["rates"]["checkout_to_purchase"] < 40: actions.append({"priority": "high", "action": "Audit checkout friction, payment errors and delivery costs"})
    if not actions: actions.append({"priority": "medium", "action": "Continue collecting data and test one campaign at a time"})
    return {"period_days": days, "traffic": traffic, "seo": seo, "conversion": conversion, "actions": actions}
