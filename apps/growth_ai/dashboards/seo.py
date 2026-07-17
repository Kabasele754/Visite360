from apps.growth_ai.analyzers.seo import analyze_seo
def seo_dashboard_context(organization, days=30): return {"organization": organization, "seo": analyze_seo(organization, days)}
