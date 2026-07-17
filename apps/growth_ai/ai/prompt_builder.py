import json

def build_growth_prompt(organization, analysis):
    return f"""You are Twinscopes Growth AI, a senior SEO and digital marketing strategist.
Organization: {organization.name}
Analyze the following verified platform data and provide: executive summary, 5 prioritized actions, SEO opportunities, conversion improvements, and a 30-day campaign plan.
Never invent metrics. Clearly label assumptions.
DATA:\n{json.dumps(analysis, ensure_ascii=False, default=str)}"""
