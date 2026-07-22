from __future__ import annotations

from collections import Counter
from dataclasses import asdict

from apps.vision_ai.services.providers import ProviderVisionOutput


def fuse_outputs(outputs: list[ProviderVisionOutput]) -> dict:
    labels = []
    features = []
    products = []
    summary_candidates = []
    scene_types = []
    confidence_values = []
    for output in outputs:
        labels.extend(item.get("label", "") for item in output.detections)
        features.extend(output.features)
        products.extend(output.products)
        if output.summary and output.provider in {"gemini", "openai", "florence2"}:
            priority = {"gemini": 0, "openai": 1, "florence2": 2}.get(output.provider, 9)
            summary_candidates.append((priority, -float(output.confidence or 0), output.summary))
        if output.scene_type:
            scene_types.append(output.scene_type)
        if output.confidence:
            confidence_values.append(output.confidence)
    feature_counts = Counter(value.strip().lower() for value in features + labels if value)
    scene_type = Counter(scene_types).most_common(1)[0][0] if scene_types else ""
    unique_products = {}
    for product in products:
        key = str(product.get("name", "")).strip().lower()
        if key and (key not in unique_products or float(product.get("confidence", 0)) > float(unique_products[key].get("confidence", 0))):
            unique_products[key] = product
    return {
        "scene_type": scene_type,
        "summary": min(summary_candidates, default=(9, 0, ""))[2],
        "features": [name for name, _ in feature_counts.most_common(40)],
        "products": list(unique_products.values()),
        "confidence": sum(confidence_values) / len(confidence_values) if confidence_values else 0,
        "providers": {output.provider: asdict(output) for output in outputs},
    }
