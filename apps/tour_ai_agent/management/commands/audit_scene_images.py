from __future__ import annotations

import json
from datetime import datetime

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.tours.models import PipelineStatus, Scene360
from apps.vision_ai.services.panorama import prepare_image_bytes


IMAGE_FIELDS = (
    "image_360_original",
    "image_360",
    "image_360_mobile",
    "image_360_preview",
    "thumbnail_image",
)


class Command(BaseCommand):
    help = (
        "Audit every stored image candidate for 360 scenes. Optionally replace "
        "an invalid original with a canonical JPEG made from the best valid fallback."
    )

    def add_arguments(self, parser):
        parser.add_argument("--scene", type=int, action="append")
        parser.add_argument("--tour", type=int)
        parser.add_argument("--organization", type=int)
        parser.add_argument("--repair-original", action="store_true")
        parser.add_argument("--json", dest="json_output", action="store_true")

    def _read_field(self, image_field) -> bytes:
        image_field.open("rb")
        try:
            return image_field.read()
        finally:
            image_field.close()

    def handle(self, *args, **options):
        queryset = Scene360.objects.select_related("tour", "organization").order_by("id")
        if options["scene"]:
            queryset = queryset.filter(pk__in=options["scene"])
        if options["tour"]:
            queryset = queryset.filter(tour_id=options["tour"])
        if options["organization"]:
            queryset = queryset.filter(organization_id=options["organization"])

        total = valid_scenes = repaired_scenes = invalid_scenes = 0
        for scene in queryset:
            total += 1
            candidates = []
            best = None
            original_valid = False
            for field_name in IMAGE_FIELDS:
                image_field = getattr(scene, field_name, None)
                if not image_field:
                    continue
                name = str(getattr(image_field, "name", "") or field_name)
                try:
                    raw = self._read_field(image_field)
                    prepared = prepare_image_bytes(raw, source_name=name)
                    item = {
                        "field": field_name,
                        "name": name,
                        "ok": True,
                        "format": prepared.format,
                        "width": prepared.width,
                        "height": prepared.height,
                        "bytes": len(raw),
                        "decoder": prepared.decoder,
                        "recoverable": prepared.repaired,
                    }
                    if best is None:
                        best = (field_name, prepared)
                    if field_name == "image_360_original":
                        original_valid = True
                except Exception as exc:
                    item = {
                        "field": field_name,
                        "name": name,
                        "ok": False,
                        "error": str(exc),
                    }
                candidates.append(item)

            repaired = False
            if options["repair_original"] and best and not original_valid:
                source_field, prepared = best
                filename = (
                    f"scene-{scene.pk}-repaired-"
                    f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.jpg"
                )
                scene.image_360_original.save(
                    filename,
                    ContentFile(prepared.image_bytes),
                    save=False,
                )
                Scene360.objects.filter(pk=scene.pk).update(
                    image_360_original=scene.image_360_original.name,
                    assets_status=PipelineStatus.PENDING,
                    assets_error="",
                    tiles_status=PipelineStatus.PENDING if scene.tiles_enabled else PipelineStatus.NONE,
                    tiles_error="",
                    ai_analysis_status=PipelineStatus.PENDING,
                    ai_analysis_error="",
                )
                repaired = True
                repaired_scenes += 1

            if best:
                valid_scenes += 1
            else:
                invalid_scenes += 1

            payload = {
                "scene_id": scene.pk,
                "tour_id": scene.tour_id,
                "title": scene.title,
                "valid": bool(best),
                "selected_field": best[0] if best else None,
                "original_valid": original_valid,
                "repaired_original": repaired,
                "candidates": candidates,
            }
            if options["json_output"]:
                self.stdout.write(json.dumps(payload, ensure_ascii=False))
            else:
                status = self.style.SUCCESS("OK") if best else self.style.ERROR("INVALID")
                selected = best[0] if best else "none"
                self.stdout.write(
                    f"scene={scene.pk} tour={scene.tour_id} {status} selected={selected} "
                    f"original_valid={original_valid} repaired={repaired}"
                )
                for item in candidates:
                    if item["ok"]:
                        self.stdout.write(
                            f"  ✓ {item['field']}: {item['format']} "
                            f"{item['width']}x{item['height']} decoder={item['decoder']} "
                            f"recoverable={item['recoverable']}"
                        )
                    else:
                        self.stdout.write(self.style.WARNING(
                            f"  ✗ {item['field']}: {item['error']}"
                        ))

        summary = (
            f"Audited {total} scene(s): {valid_scenes} with a decodable image, "
            f"{invalid_scenes} without one, {repaired_scenes} original(s) repaired."
        )
        self.stdout.write(self.style.SUCCESS(summary) if not invalid_scenes else self.style.WARNING(summary))
