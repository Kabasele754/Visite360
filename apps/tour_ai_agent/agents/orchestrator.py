from __future__ import annotations

import logging
import re

from apps.tour_ai_agent.providers import AIProviderRouter

from .intent_router import detect_intent
from .prompt_builder import build_input, build_sales_instructions
from .sales_agent import fallback_reply

logger = logging.getLogger(__name__)


def _public_reasoning_steps(context: dict) -> list[dict]:
    """High-level progress labels for UI. Never exposes private chain-of-thought."""
    products = context.get("products") or []
    detected = (context.get("scene") or {}).get("detected_objects") or []
    steps = [
        {"key": "scene", "label": "Understanding the current scene"},
        {"key": "business", "label": "Checking the business and place context"},
    ]
    if detected:
        steps.append({"key": "vision", "label": f"Reviewing {len(detected)} visually detected object types"})
    if products:
        steps.append({"key": "catalogue", "label": f"Comparing {len(products)} catalogue matches"})
    else:
        steps.append({"key": "catalogue", "label": "Checking visual alternatives because no catalogue match is confirmed"})
    steps.append({"key": "answer", "label": "Preparing a grounded recommendation"})
    return steps


def _sanitize_citations(text: str, context: dict) -> str:
    valid = {str(item.get("citation")) for item in context.get("knowledge_sources", []) if item.get("citation")}
    def replace(match):
        label = match.group(1)
        return match.group(0) if label in valid else ""
    cleaned = re.sub(r"\[(K(?:#|\d+))\]", replace, str(text or ""))
    return re.sub(r"[ \t]+(?=[.,;:!?])", "", cleaned).strip()


def run_agent(*, text: str, context: dict) -> dict:
    intent = detect_intent(text)
    public_steps = _public_reasoning_steps(context)
    try:
        result = AIProviderRouter().generate(
            instructions=build_sales_instructions(context),
            input_text=build_input(text, context),
        )
        return {
            "text": _sanitize_citations(result.text, context),
            "intent": intent,
            "quick_actions": ["book_appointment", "view_products", "contact_business"],
            "provider": result.provider,
            "response_id": result.response_id,
            "degraded": False,
            "reasoning_steps": public_steps,
        }
    except Exception:
        logger.exception("All configured AI providers failed; using local fallback")
        result = fallback_reply(text, context)
        result.update({
            "provider": "local",
            "degraded": True,
            "intent": intent,
            "reasoning_steps": public_steps,
        })
        return result
