from apps.growth_ai.analyzers.marketing import analyze_marketing

def build_recommendations(organization, days=30):
    analysis = analyze_marketing(organization, days)
    return analysis["actions"]
