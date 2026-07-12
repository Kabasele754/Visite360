from __future__ import annotations

from django.utils import timezone

from apps.app_streetview.serializers import connection_to_dict, hotspot_to_dict, scene_to_dict, tour_to_dict


def build_project_export(tour, absolute_url_builder=None):
    scenes = list(tour.scenes.all().prefetch_related("hotspots"))
    connections = list(tour.connections.all())
    return {
        "version": "1.0",
        "generator": "apps.app_streetview",
        "generated_at": timezone.now().isoformat(),
        "tour": tour_to_dict(tour, absolute_url_builder=absolute_url_builder, include_children=False),
        "scenes": [scene_to_dict(scene, absolute_url_builder=absolute_url_builder) for scene in scenes],
        "connections": [connection_to_dict(connection) for connection in connections],
        "hotspots": [hotspot_to_dict(hotspot) for scene in scenes for hotspot in scene.hotspots.all()],
        "notes": {
            "marzipano": "Hotspots info/url/link are used by the web viewer.",
            "google_street_view": "Google Street View Publish receives image, GPS, pose metadata and scene-to-scene connections only.",
        },
    }
