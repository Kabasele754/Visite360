from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.tours.models import PipelineStatus, Scene360
from apps.vision_ai.models import VisionAnalysis
from apps.vision_ai.services.queueing import (
    analysis_status_payload,
    dispatch_scene_analysis,
    scene_has_readable_panorama,
)


class Command(BaseCommand):
    help = (
        "Analyze existing 360 scenes with YOLO, PaddleOCR and semantic vision. "
        "Runs synchronously by default in local DEBUG mode and through Celery in production."
    )

    def add_arguments(self, parser):
        parser.add_argument("--organization", type=int, help="Limit to one organization ID")
        parser.add_argument("--tour", type=int, help="Limit to one tour ID")
        parser.add_argument("--scene", type=int, action="append", help="Analyze a scene ID; repeat for several scenes")
        parser.add_argument("--force", action="store_true", help="Create a fresh analysis even when a successful one exists")
        parser.add_argument("--retry-failed", action="store_true", help="Only retry scenes whose latest analysis failed")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument(
            "--mode",
            choices=("auto", "sync", "thread", "celery"),
            default="auto",
            help="auto=thread locally and Celery in production; sync is best for CLI tests",
        )
        parser.add_argument("--sync", action="store_true", help="Compatibility alias for --mode=sync")
        parser.add_argument(
            "--providers",
            default="yolo,paddleocr,gemini,openai",
            help="Comma-separated providers; disabled or unconfigured providers are skipped",
        )
        parser.add_argument("--status-only", action="store_true", help="Show current status without starting work")
        parser.add_argument("--fail-fast", action="store_true")
        parser.add_argument("--json-report", default="", help="Optional path for a machine-readable report")

    def handle(self, *args, **options):
        mode = "sync" if options["sync"] else options["mode"]
        providers = [value.strip() for value in options["providers"].split(",") if value.strip()]

        qs = Scene360.objects.select_related("tour__organization", "organization").order_by("id")
        if options["organization"]:
            qs = qs.filter(organization_id=options["organization"])
        if options["tour"]:
            qs = qs.filter(tour_id=options["tour"])
        if options["scene"]:
            qs = qs.filter(pk__in=options["scene"])
        if options["retry_failed"]:
            qs = qs.filter(ai_analysis_status__in=[PipelineStatus.FAILED, "error"])
        elif not options["force"] and not options["status_only"]:
            qs = qs.exclude(ai_analysis_status__in=[PipelineStatus.READY, "done"])
        if options["limit"]:
            qs = qs[: options["limit"]]

        scenes = list(qs)
        if not scenes:
            self.stdout.write(self.style.WARNING("No matching scenes were found."))
            return

        effective_mode = mode
        if effective_mode == "auto":
            effective_mode = "thread" if settings.DEBUG else "celery"
        self.stdout.write(
            f"Runtime={'local DEBUG' if settings.DEBUG else 'production'} "
            f"mode={effective_mode} scenes={len(scenes)} providers={','.join(providers)}"
        )

        report: list[dict] = []
        errors = 0
        for index, scene in enumerate(scenes, start=1):
            prefix = f"[{index}/{len(scenes)}] scene={scene.pk} tour={scene.tour_id} {scene.title!r}"
            if not scene_has_readable_panorama(scene):
                item = {"scene_id": scene.pk, "ok": False, "error": "No readable panorama image"}
                report.append(item)
                errors += 1
                self.stdout.write(self.style.ERROR(f"{prefix}: skipped — no panorama image"))
                if options["fail_fast"]:
                    raise CommandError(item["error"])
                continue

            if options["status_only"]:
                item = analysis_status_payload(scene)
                item["ok"] = True
                report.append(item)
                self.stdout.write(json.dumps(item, ensure_ascii=False))
                continue

            self.stdout.write(f"{prefix}: starting...")
            try:
                dispatch = dispatch_scene_analysis(
                    scene,
                    force=options["force"] or options["retry_failed"],
                    requested_providers=providers,
                    mode=mode,
                )
                scene.refresh_from_db()
                item = analysis_status_payload(scene)
                item.update({
                    "ok": True,
                    "created": dispatch.created,
                    "dispatch_mode": dispatch.mode,
                    "task_id": dispatch.task_id,
                })
                report.append(item)
                if dispatch.mode == "sync":
                    style = self.style.SUCCESS if item["status"] in {
                        VisionAnalysis.Status.SUCCEEDED,
                        VisionAnalysis.Status.PARTIAL,
                    } else self.style.ERROR
                    self.stdout.write(style(
                        f"{prefix}: {item['status']} — frames={item['frame_count']} "
                        f"objects={item['detection_count']} text={item['ocr_count']} "
                        f"insights={item['insight_count']} providers={item['completed_providers']}"
                    ))
                    if item["status"] == VisionAnalysis.Status.FAILED:
                        item["ok"] = False
                        errors += 1
                    if item.get("failed_providers"):
                        self.stdout.write(self.style.WARNING(
                            f"{prefix}: provider warnings={json.dumps(item['failed_providers'], ensure_ascii=False)}"
                        ))
                elif dispatch.mode == "existing":
                    self.stdout.write(self.style.WARNING(f"{prefix}: existing analysis reused ({item['status']})"))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f"{prefix}: queued analysis={item['analysis_id']} task={dispatch.task_id}"
                    ))
            except Exception as exc:
                errors += 1
                item = {"scene_id": scene.pk, "ok": False, "error": str(exc)}
                report.append(item)
                self.stdout.write(self.style.ERROR(f"{prefix}: failed — {exc}"))
                if options["fail_fast"]:
                    raise CommandError(str(exc)) from exc

        if options["json_report"]:
            path = Path(options["json_report"]).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(f"Report written to {path.resolve()}")

        successful = len(report) - errors
        message = f"Processed {len(report)} scene(s): {successful} successful, {errors} error(s)."
        if errors:
            self.stdout.write(self.style.WARNING(message))
        else:
            self.stdout.write(self.style.SUCCESS(message))
