from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.vision_ai.models import VisionAnalysis
from apps.vision_ai.services.insights import rebuild_insights


class Command(BaseCommand):
    help = (
        "Rebuild point-selectable object/text insights from existing YOLO and OCR "
        "results without calling Gemini, OpenAI or rerunning the panorama scan."
    )

    def add_arguments(self, parser):
        parser.add_argument("--scene", action="append", type=int, dest="scene_ids")
        parser.add_argument("--tour", type=int, dest="tour_id")
        parser.add_argument("--analysis", action="append", dest="analysis_ids")
        parser.add_argument(
            "--all",
            action="store_true",
            help="Rebuild the latest completed analysis for every scene.",
        )
        parser.add_argument(
            "--keep-point-cache",
            action="store_true",
            help="Keep dynamically cached point-inspection frames (normally removed).",
        )

    def handle(self, *args, **options):
        queryset = VisionAnalysis.objects.filter(
            status__in=[VisionAnalysis.Status.SUCCEEDED, VisionAnalysis.Status.PARTIAL]
        ).select_related("scene")

        analysis_ids = options.get("analysis_ids") or []
        scene_ids = options.get("scene_ids") or []
        tour_id = options.get("tour_id")
        if analysis_ids:
            queryset = queryset.filter(pk__in=analysis_ids)
        elif scene_ids:
            queryset = queryset.filter(scene_id__in=scene_ids)
        elif tour_id:
            queryset = queryset.filter(scene__tour_id=tour_id)
        elif not options.get("all"):
            raise CommandError("Use --scene, --tour, --analysis or --all.")

        # Keep only the newest completed analysis for each scene unless explicit
        # analysis IDs were requested.
        analyses = list(queryset.order_by("scene_id", "-finished_at", "-created_at"))
        if not analysis_ids:
            latest = {}
            for analysis in analyses:
                latest.setdefault(analysis.scene_id, analysis)
            analyses = list(latest.values())

        total_insights = 0
        for index, analysis in enumerate(analyses, start=1):
            if not options.get("keep_point_cache"):
                dynamic_frames = [
                    frame.pk
                    for frame in analysis.frames.only("pk", "metadata")
                    if (frame.metadata or {}).get("dynamic_point_inspection")
                ]
                if dynamic_frames:
                    analysis.frames.filter(pk__in=dynamic_frames).delete()

            count = rebuild_insights(analysis)
            total_insights += count
            if analysis.scene_id:
                payload = dict(analysis.scene.ai_analysis or {})
                payload["insight_count"] = count
                analysis.scene.ai_analysis = payload
                analysis.scene.save(update_fields=("ai_analysis", "updated_at"))
            self.stdout.write(
                f"[{index}/{len(analyses)}] scene={analysis.scene_id} "
                f"analysis={analysis.pk} insights={count}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Rebuilt {total_insights} point-selectable insight(s) across {len(analyses)} analysis(es)."
            )
        )
