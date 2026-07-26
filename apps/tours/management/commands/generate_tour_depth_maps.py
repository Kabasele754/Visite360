from django.core.management.base import BaseCommand, CommandError

from apps.tours.intelligence.depth import (
    DepthGenerationUnavailable,
    generate_scene_depth_map,
)
from apps.tours.models import Scene360


class Command(BaseCommand):
    help = "Generate optional depth maps used by the Preview Spatial 3D mode."

    def add_arguments(self, parser):
        parser.add_argument("--tour", type=int)
        parser.add_argument("--scene", type=int)
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        queryset = Scene360.objects.select_related("tour").order_by("tour_id", "order", "id")
        if options.get("tour"):
            queryset = queryset.filter(tour_id=options["tour"])
        if options.get("scene"):
            queryset = queryset.filter(pk=options["scene"])
        if options.get("limit"):
            queryset = queryset[: options["limit"]]

        scenes = list(queryset)
        if not scenes:
            self.stdout.write(self.style.WARNING("No matching scenes were found."))
            return

        succeeded = 0
        for index, scene in enumerate(scenes, start=1):
            self.stdout.write(f"[{index}/{len(scenes)}] Scene {scene.pk}: {scene.title}")
            try:
                payload = generate_scene_depth_map(scene, force=options["force"])
            except DepthGenerationUnavailable as exc:
                raise CommandError(str(exc)) from exc
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"  Failed: {exc}"))
                continue
            succeeded += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Ready: {payload.get('width')}x{payload.get('height')} {payload.get('url')}"
                )
            )

        self.stdout.write(self.style.SUCCESS(f"Generated {succeeded}/{len(scenes)} depth map(s)."))
