from __future__ import annotations

from typing import Any


def classify_provider_error(exc: BaseException | str) -> str:
    """Return a stable, non-sensitive error code for storage and UI decisions."""
    text = str(exc).lower()
    if any(token in text for token in (
        "invalid_credentials", "invalid_api_key", "incorrect api key", "authentication failed",
        "unauthorized", "error code: 401", "status code: 401", " 401 ",
    )):
        return "invalid_credentials"
    if any(token in text for token in (
        "rate_limited", "resource_exhausted", "resource exhausted", "rate limit",
        "too many requests", "error code: 429", "status code: 429", " 429 ",
    )):
        return "rate_limited"
    if any(token in text for token in (
        "misconfigured", "not configured", "missing api key", "api_key is not configured",
        "project is not configured", "credentials",
    )):
        return "misconfigured"
    if any(token in text for token in (
        "timed out", "timeout", "deadline exceeded",
    )):
        return "timeout"
    if any(token in text for token in (
        "temporarily_unavailable", "connection", "temporarily unavailable", "service unavailable",
        "bad gateway", "gateway timeout", "error code: 502",
        "error code: 503", "error code: 504",
    )):
        return "temporarily_unavailable"
    if any(token in text for token in ("model_unavailable", "model_not_found", "does not exist", "unsupported model")):
        return "model_unavailable"
    return "provider_error"


def provider_failure_token(provider: str, operation: str, exc: BaseException | str) -> str:
    return f"{provider}:{operation}:{classify_provider_error(exc)}"


def provider_should_stop_for_analysis(exc: BaseException | str) -> bool:
    return classify_provider_error(exc) in {
        "invalid_credentials",
        "misconfigured",
        "rate_limited",
        "model_unavailable",
    }


def public_error_copy(locale: str = "en", *, kind: str = "temporary") -> tuple[str, str]:
    french = str(locale or "en").lower().startswith("fr")
    if kind == "analyzing":
        return (
            ("Préparation des détails visuels", "Twinscopes examine cette zone. Le résultat apparaîtra automatiquement.")
            if french else
            ("Preparing visual details", "Twinscopes is examining this area. The result will appear automatically.")
        )
    if kind == "not_ready":
        return (
            ("Détails visuels bientôt disponibles", "Cette scène est en cours de préparation. Réessayez dans quelques instants.")
            if french else
            ("Visual details are being prepared", "This scene is still being prepared. Please try again in a moment.")
        )
    if kind == "no_object":
        return (
            ("Aucun élément précis trouvé", "Maintenez votre doigt ou la souris directement sur l’élément visible, sans déplacer l’image.")
            if french else
            ("No specific item found", "Press and hold directly on the visible item without moving the scene.")
        )
    return (
        ("Détails visuels temporairement indisponibles", "Nous ne pouvons pas afficher ces informations maintenant. Réessayez dans un instant.")
        if french else
        ("Visual details temporarily unavailable", "We cannot display this information right now. Please try again shortly.")
    )
