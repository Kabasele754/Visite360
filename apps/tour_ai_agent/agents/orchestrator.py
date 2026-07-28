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




def _trusted_urls(context: dict) -> set[str]:
    trusted: set[str] = set()

    def visit(value):
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                visit(item)
        elif isinstance(value, str):
            candidate = value.strip().rstrip(".,;:!?)\"'")
            if candidate.startswith(("https://", "http://")):
                trusted.add(candidate)

    for key in ("business", "contact", "services", "knowledge_sources", "domain_intelligence"):
        visit(context.get(key))
    return trusted


def _sanitize_links(text: str, context: dict) -> str:
    trusted = _trusted_urls(context)
    value = str(text or "")

    def markdown_link(match):
        label, url = match.group(1).strip(), match.group(2).strip()
        return match.group(0) if url in trusted else label

    value = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", markdown_link, value)

    def bare_link(match):
        raw = match.group(0)
        suffix = ""
        while raw and raw[-1] in ".,;:!?)":
            suffix = raw[-1] + suffix
            raw = raw[:-1]
        return (raw if raw in trusted else "") + suffix

    value = re.sub(r"https?://[^\s<]+", bare_link, value)
    return re.sub(r"[ \t]+(?=[.,;:!?])", "", value).strip()



def _is_french(text: str, context: dict) -> bool:
    locale = str(context.get("locale") or "").lower()
    if locale.startswith("fr"):
        return True
    value = f" {str(text or '').lower()} "
    return any(token in value for token in (" bonjour ", " bonsoir ", " salut ", " rendez-vous ", " contacter ", " téléphone ", " devis ", " merci "))


def _simple_request(text: str, *, limit: int = 18) -> bool:
    return len(str(text or "").split()) <= limit


def _fast_local_reply(text: str, context: dict, intent: str) -> dict | None:
    """Answer common structured requests without an embedding or text-model call."""
    normalized = " ".join(str(text or "").lower().split()).strip(" !?.")
    french = _is_french(text, context)
    greetings = {
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
        "bonjour", "bonsoir", "salut", "coucou", "merci", "thank you",
    }
    business = context.get("business") or context.get("organization") or {}
    name = str(business.get("name") or (context.get("tour") or {}).get("organization") or "the organization")
    contact = context.get("contact") or {}

    if normalized in greetings:
        copy = (
            f"Bonjour ! Bienvenue chez **{name}**. Je peux vous aider à explorer la visite, consulter les services, contacter l’entreprise ou demander un rendez-vous."
            if french else
            f"Hello! Welcome to **{name}**. I can help you explore the tour, review services, contact the business, or request an appointment."
        )
        return {"text": copy, "quick_actions": ["view_products", "book_appointment", "contact_business"]}

    if intent == "contact" and _simple_request(text):
        lines = []
        phone = str(contact.get("phone") or business.get("public_phone") or "").strip()
        email = str(contact.get("email") or business.get("public_email") or "").strip()
        website = str(contact.get("website") or business.get("website_url") or "").strip()
        booking = str(contact.get("booking_url") or business.get("booking_url") or "").strip()
        if phone: lines.append(f"- **Téléphone :** {phone}" if french else f"- **Phone:** {phone}")
        if email: lines.append(f"- **E-mail :** {email}" if french else f"- **Email:** {email}")
        if website: lines.append(f"- **Site officiel :** [Ouvrir le site]({website})" if french else f"- **Official website:** [Open website]({website})")
        if booking: lines.append(f"- **Réservation :** [Ouvrir le formulaire]({booking})" if french else f"- **Booking:** [Open booking form]({booking})")
        if lines:
            heading = f"Voici les coordonnées publiques vérifiées de **{name}** :" if french else f"Here are the verified public contact details for **{name}**:"
            return {"text": heading + "\n\n" + "\n".join(lines), "quick_actions": ["contact_business", "book_appointment"]}
        copy = (
            "Aucune coordonnée publique n’est configurée pour le moment. Vous pouvez utiliser l’action de contact sécurisée."
            if french else
            "No public contact details are configured yet. You can use the secure contact action."
        )
        return {"text": copy, "quick_actions": ["contact_business"]}

    if intent == "booking" and _simple_request(text) and not any(word in normalized for word in ("doctor", "médecin", "specialist", "spécialiste", "available", "disponible", "service")):
        copy = (
            f"Je peux enregistrer une demande de rendez-vous auprès de **{name}**. Indiquez votre nom, votre téléphone, la date et l’heure souhaitées dans le formulaire. Le rendez-vous reste en attente jusqu’à confirmation de l’organisation."
            if french else
            f"I can submit an appointment request to **{name}**. Add your name, phone number, preferred date, and time in the form. The appointment remains pending until the organization confirms it."
        )
        return {"text": copy, "quick_actions": ["book_appointment", "contact_business"]}

    if intent == "quote" and _simple_request(text):
        copy = (
            f"Je peux préparer une demande de devis pour **{name}**. Décrivez brièvement le besoin et ajoutez vos coordonnées dans le formulaire."
            if french else
            f"I can prepare a quotation request for **{name}**. Briefly describe what you need and add your contact details in the form."
        )
        return {"text": copy, "quick_actions": ["request_quote", "contact_business"]}

    return None


def run_agent(*, text: str, context: dict) -> dict:
    intent = detect_intent(text)
    public_steps = _public_reasoning_steps(context)
    local = _fast_local_reply(text, context, intent)
    if local is not None:
        return {
            **local,
            "text": _sanitize_links(_sanitize_citations(local.get("text", ""), context), context),
            "intent": intent,
            "provider": "local",
            "response_id": None,
            "degraded": False,
            "reasoning_steps": [{"key": "answer", "label": "Using verified organization information"}],
        }
    try:
        result = AIProviderRouter().generate(
            instructions=build_sales_instructions(context),
            input_text=build_input(text, context),
        )
        return {
            "text": _sanitize_links(_sanitize_citations(result.text, context), context),
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
