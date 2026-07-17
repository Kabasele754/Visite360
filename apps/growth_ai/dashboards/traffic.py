from apps.growth_ai.analyzers.traffic import analyze_traffic
def traffic_dashboard_context(organization, days=30): return {"organization": organization, "traffic": analyze_traffic(organization, days)}
