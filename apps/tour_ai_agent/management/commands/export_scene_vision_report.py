from __future__ import annotations

import html
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageDraw

from apps.tours.models import Scene360
from apps.vision_ai.models import VisionAnalysis
from apps.vision_ai.services.insights import latest_scene_analysis


class Command(BaseCommand):
    help = "Export an annotated HTML/JSON report for the latest computer-vision analysis of one 360 scene."

    def add_arguments(self, parser):
        parser.add_argument("scene_id", type=int)
        parser.add_argument("--analysis", default="", help="Optional VisionAnalysis UUID")
        parser.add_argument("--output", default="vision_reports", help="Output directory")

    def handle(self, *args, **options):
        scene = Scene360.objects.select_related("tour", "organization").filter(pk=options["scene_id"]).first()
        if scene is None:
            raise CommandError(f"Scene {options['scene_id']} not found")

        if options["analysis"]:
            analysis = VisionAnalysis.objects.filter(pk=options["analysis"], scene=scene).first()
        else:
            analysis = latest_scene_analysis(scene)
        if analysis is None:
            raise CommandError(
                "No successful/partial Enterprise Vision analysis exists for this scene. "
                f"Run: python manage.py check_ai_stack --scene {scene.pk} --force"
            )

        output_dir = Path(options["output"]).expanduser().resolve() / f"scene-{scene.pk}-{analysis.pk}"
        frames_dir = output_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        report = {
            "scene": {
                "id": scene.pk,
                "title": scene.title,
                "tour_id": scene.tour_id,
                "tour": scene.tour.title,
                "organization": scene.organization.name,
            },
            "analysis": {
                "id": str(analysis.pk),
                "status": analysis.status,
                "scene_type": analysis.scene_type,
                "summary": analysis.summary,
                "features": analysis.features,
                "products": analysis.products,
                "extracted_text": analysis.extracted_text,
                "confidence": analysis.confidence,
                "completed_providers": analysis.completed_providers,
                "failed_providers": analysis.failed_providers,
                "started_at": analysis.started_at.isoformat() if analysis.started_at else None,
                "finished_at": analysis.finished_at.isoformat() if analysis.finished_at else None,
            },
            "frames": [],
        }

        for frame in analysis.frames.prefetch_related("detections", "ocr_blocks", "insights").order_by("frame_index"):
            if not frame.image:
                continue
            frame.image.open("rb")
            try:
                image = Image.open(frame.image).convert("RGB")
            finally:
                frame.image.close()
            draw = ImageDraw.Draw(image)

            detections = []
            for detection in frame.detections.order_by("-confidence"):
                bbox = detection.bbox or []
                if len(bbox) == 4:
                    x1, y1, x2, y2 = [float(value) for value in bbox]
                    draw.rectangle((x1, y1, x2, y2), width=3)
                    draw.text((x1 + 3, max(0, y1 - 16)), f"{detection.label} {detection.confidence:.2f}")
                detections.append({
                    "provider": detection.provider,
                    "label": detection.label,
                    "confidence": detection.confidence,
                    "bbox": detection.bbox,
                    "attributes": detection.attributes,
                })

            ocr_blocks = []
            for block in frame.ocr_blocks.order_by("-confidence"):
                polygon = block.polygon or []
                try:
                    points = [(float(point[0]), float(point[1])) for point in polygon if len(point) >= 2]
                except (TypeError, ValueError):
                    points = []
                if len(points) >= 2:
                    draw.line(points + [points[0]], width=3)
                    draw.text(points[0], f"OCR {block.confidence:.2f}: {block.text[:45]}")
                ocr_blocks.append({
                    "provider": block.provider,
                    "text": block.text,
                    "confidence": block.confidence,
                    "polygon": block.polygon,
                    "language": block.language,
                    "metadata": block.metadata,
                })

            frame_name = f"frame-{frame.frame_index:02d}-annotated.jpg"
            frame_path = frames_dir / frame_name
            image.save(frame_path, format="JPEG", quality=90, optimize=True)
            report["frames"].append({
                "index": frame.frame_index,
                "yaw": frame.yaw,
                "pitch": frame.pitch,
                "metadata": frame.metadata,
                "annotated_image": f"frames/{frame_name}",
                "detections": detections,
                "ocr_blocks": ocr_blocks,
                "insights": [
                    {
                        "kind": insight.kind,
                        "title": insight.title,
                        "description": insight.description,
                        "confidence": insight.confidence,
                        "yaw": insight.yaw,
                        "pitch": insight.pitch,
                        "attributes": insight.attributes,
                        "source_providers": insight.source_providers,
                    }
                    for insight in frame.insights.order_by("-confidence")
                ],
            })

        json_path = output_dir / "report.json"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        html_path = output_dir / "index.html"
        html_path.write_text(self._render_html(report), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(f"Vision report: {html_path}"))
        self.stdout.write(f"JSON report: {json_path}")

    @staticmethod
    def _render_html(report: dict) -> str:
        scene = report["scene"]
        analysis = report["analysis"]
        frame_cards = []
        for frame in report["frames"]:
            objects = "".join(
                f"<li><strong>{html.escape(str(item['label']))}</strong> "
                f"{float(item['confidence']) * 100:.0f}%</li>"
                for item in frame["detections"][:30]
            ) or "<li>No YOLO object recorded</li>"
            texts = "".join(
                f"<li><strong>{html.escape(str(item['text']))}</strong> "
                f"{float(item['confidence']) * 100:.0f}%</li>"
                for item in frame["ocr_blocks"][:30]
            ) or "<li>No OCR text recorded</li>"
            insights = "".join(
                f"<li><strong>{html.escape(str(item['title']))}</strong>: "
                f"{html.escape(str(item['description']))}</li>"
                for item in frame["insights"][:30]
            ) or "<li>No interactive insight generated</li>"
            frame_cards.append(f"""
              <article class="card">
                <header><h2>Frame {frame['index']}</h2><span>yaw {frame['yaw']:.1f}° · pitch {frame['pitch']:.1f}°</span></header>
                <img src="{html.escape(frame['annotated_image'])}" alt="Annotated panorama frame {frame['index']}">
                <div class="grid"><section><h3>Objects</h3><ul>{objects}</ul></section><section><h3>OCR</h3><ul>{texts}</ul></section><section><h3>Insights</h3><ul>{insights}</ul></section></div>
              </article>
            """)

        failed = html.escape(json.dumps(analysis["failed_providers"], ensure_ascii=False, indent=2))
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Twinscopes Vision Report — Scene {scene['id']}</title>
<style>
body{{margin:0;background:#07111d;color:#e9fbff;font:15px/1.55 system-ui,-apple-system,sans-serif}}main{{max-width:1500px;margin:auto;padding:28px}}.hero,.card{{background:#0d1d2d;border:1px solid #17485c;border-radius:22px;box-shadow:0 20px 50px #0007}}.hero{{padding:24px;margin-bottom:24px}}.badge{{display:inline-block;padding:6px 12px;border-radius:99px;background:#0b3b4b;color:#67e8f9}}h1{{margin:.4rem 0}}.summary{{font-size:18px;color:#d8f7ff}}.meta{{display:flex;gap:12px;flex-wrap:wrap;color:#9dcbd7}}.card{{padding:18px;margin:20px 0}}.card header{{display:flex;justify-content:space-between;align-items:center}}.card img{{width:100%;border-radius:14px;border:1px solid #1d5267}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}section{{background:#081522;border-radius:14px;padding:12px}}ul{{padding-left:20px;max-height:320px;overflow:auto}}pre{{white-space:pre-wrap;background:#06101a;padding:14px;border-radius:14px;color:#ffd6a5}}@media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<section class="hero"><span class="badge">Twinscopes Computer Vision</span><h1>{html.escape(scene['title'])}</h1>
<p class="summary">{html.escape(analysis['summary'] or 'No semantic summary')}</p>
<div class="meta"><span>Scene type: {html.escape(analysis['scene_type'] or 'unknown')}</span><span>Status: {html.escape(analysis['status'])}</span><span>Confidence: {float(analysis['confidence'] or 0)*100:.0f}%</span><span>Providers: {html.escape(', '.join(analysis['completed_providers']))}</span></div>
<h3>Provider warnings</h3><pre>{failed}</pre></section>
{''.join(frame_cards)}
</main></body></html>"""
