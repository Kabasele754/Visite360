def analyze_competitors(organization, competitors=None):
    competitors = competitors or []
    return {"organization": organization.name, "competitors": competitors, "status": "ready_for_external_competitor_sources", "message": "Add competitor domains, Google Business locations or imported benchmark data to activate comparisons."}
