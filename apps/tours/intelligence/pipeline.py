from __future__ import annotations

import logging

from apps.tours.intelligence.dispatch import maybe_dispatch_tour_architecture
from apps.tours.intelligence.object_catalog import synchronize_scene_object_catalog
from apps.tours.intelligence.quality import assess_scene_quality

logger = logging.getLogger(__name__)


def postprocess_completed_analysis(analysis) -> dict:
    """Build reusable object crops and quality guidance after enterprise vision.

    This stage never creates public info hotspots. It prepares reviewable data
    for the Tour Architect dashboard, then schedules topology planning only
    after the tour has enough completed scene analyses.
    """
    if not analysis.scene_id:
        return {"objects": 0, "quality": None, "architect": None}
    scene = analysis.scene
    quality = assess_scene_quality(scene, analysis=analysis)
    object_count = synchronize_scene_object_catalog(analysis)
    dispatch = maybe_dispatch_tour_architecture(scene.tour)
    return {
        "objects": object_count,
        "quality": quality.overall_score,
        "architect": str(dispatch.run.pk) if dispatch else None,
    }
