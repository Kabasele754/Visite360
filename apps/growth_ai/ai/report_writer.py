from .gemini_client import generate_text
from .prompt_builder import build_growth_prompt

def write_growth_report(organization, analysis):
    return generate_text(build_growth_prompt(organization, analysis))
