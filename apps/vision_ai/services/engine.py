from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import asdict
from typing import Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.vision_ai.models import OCRTextBlock, VisionAnalysis, VisionDetection, VisionFrame
from apps.tours.models import PipelineStatus
from apps.vision_ai.services.fusion import fuse_outputs
from apps.vision_ai.services.insights import rebuild_insights
from apps.vision_ai.services.panorama import (
    InvalidPanoramaImageError,
    PanoramaFrameData,
    extract_panorama_frames,
    prepare_image_bytes,
)
from apps.vision_ai.services.providers import (
    ProviderVisionOutput,
    build_provider,
    enabled_provider_names,
    semantic_provider_order,
)

logger = logging.getLogger(__name__)

LOCAL_PROVIDERS = ("yolo", "paddleocr", "florence2")
SEMANTIC_PROVIDERS = ("gemini", "openai")


def _analysis_image_candidates(analysis: VisionAnalysis):
    """Yield every possible image source in quality order without duplicates."""
    seen: set[str] = set()
    if analysis.uploaded_image:
        name = str(getattr(analysis.uploaded_image, "name", "") or "uploaded_image")
        seen.add(name)
        yield "uploaded_image", analysis.uploaded_image
    if analysis.scene_id:
        scene = analysis.scene
        for field_name in (
            "image_360_original",
            "image_360",
            "image_360_mobile",
            "image_360_preview",
            "thumbnail_image",
        ):
            image_field = getattr(scene, field_name, None)
            if not image_field:
                continue
            name = str(getattr(image_field, "name", "") or field_name)
            if name in seen:
                continue
            seen.add(name)
            yield field_name, image_field


def resolve_analysis_image(analysis: VisionAnalysis) -> bytes:
    """Return the first decodable panorama, falling back across scene assets.

    A scene can contain an invalid original upload while its generated desktop,
    mobile or preview asset remains valid. Older code stopped at the first
    truthy field and failed the whole analysis. We now validate every candidate
    and only fail when none can be decoded.
    """
    errors: list[str] = []
    for field_name, image_field in _analysis_image_candidates(analysis):
        source_name = str(getattr(image_field, "name", "") or field_name)
        try:
            image_field.open("rb")
            try:
                raw = image_field.read()
            finally:
                image_field.close()
            prepared = prepare_image_bytes(raw, source_name=source_name)
            if field_name != "image_360_original" or prepared.repaired:
                logger.warning(
                    "Vision analysis %s is using %s (%s, %sx%s, decoder=%s, repaired=%s)",
                    analysis.pk,
                    field_name,
                    prepared.format,
                    prepared.width,
                    prepared.height,
                    prepared.decoder,
                    prepared.repaired,
                )
            return prepared.image_bytes
        except Exception as exc:
            errors.append(f"{field_name}={source_name}: {exc}")
            logger.warning(
                "Vision image candidate %s failed for analysis %s: %s",
                field_name,
                analysis.pk,
                exc,
            )

    details = " | ".join(errors)[:5000]
    raise InvalidPanoramaImageError(
        "No decodable panorama image is available for this analysis. " + details
    )


def _merge_provider_frame_outputs(
    provider_name: str,
    frame_outputs: list[tuple[VisionFrame, ProviderVisionOutput]],
) -> ProviderVisionOutput:
    if not frame_outputs:
        return ProviderVisionOutput(provider=provider_name)
    outputs = [item[1] for item in frame_outputs]
    best = max(outputs, key=lambda item: item.confidence)
    summaries = [output for output in outputs if output.summary]
    scene_types = [output.scene_type for output in outputs if output.scene_type]
    best_summary = max(summaries, key=lambda item: item.confidence).summary if summaries else ""
    # OCR output and dozens of frame captions must not be concatenated into a
    # public visual card. Raw per-frame details remain available in ``raw``.
    if provider_name in {"yolo", "paddleocr"}:
        best_summary = ""
    merged = ProviderVisionOutput(
        provider=provider_name,
        summary=best_summary,
        scene_type=scene_types[0] if scene_types else best.scene_type,
        features=list(dict.fromkeys(value for output in outputs for value in output.features if value)),
        products=[item for output in outputs for item in output.products],
        detections=[item for output in outputs for item in output.detections],
        ocr_blocks=[item for output in outputs for item in output.ocr_blocks],
        confidence=max((output.confidence for output in outputs), default=0.0),
        raw={
            "frames": [
                {
                    "frame_index": frame.frame_index,
                    "yaw": frame.yaw,
                    "pitch": frame.pitch,
                    "summary": output.summary,
                    "scene_type": output.scene_type,
                    "confidence": output.confidence,
                    "raw": output.raw,
                }
                for frame, output in frame_outputs
            ]
        },
    )
    return merged


def _frame_context(
    frame: VisionFrame,
    local_outputs: dict[str, ProviderVisionOutput],
) -> dict[str, Any]:
    yolo = local_outputs.get("yolo")
    ocr = local_outputs.get("paddleocr")
    florence = local_outputs.get("florence2")
    return {
        "frame": {
            "index": frame.frame_index,
            "yaw_degrees": frame.yaw,
            "pitch_degrees": frame.pitch,
            "fov_degrees": (frame.metadata or {}).get("fov", 82),
        },
        "yolo_detections": (yolo.detections if yolo else []),
        "ocr_blocks": (ocr.ocr_blocks if ocr else []),
        "florence_caption": (florence.summary if florence else ""),
    }


def _select_semantic_frames(
    frame_models: list[tuple[VisionFrame, PanoramaFrameData]],
    local_by_frame: dict[int, dict[str, ProviderVisionOutput]],
) -> list[tuple[VisionFrame, PanoramaFrameData]]:
    configured_max = max(1, int(getattr(settings, "VISION_SEMANTIC_MAX_FRAMES", 4)))
    cloud_call_cap = max(
        1,
        int(getattr(settings, "VISION_SEMANTIC_MAX_CLOUD_CALLS_PER_SCENE", 4)),
    )
    max_frames = min(configured_max, cloud_call_cap)
    scored: list[tuple[float, VisionFrame, PanoramaFrameData]] = []
    for frame, frame_data in frame_models:
        outputs = local_by_frame.get(frame.frame_index, {})
        yolo_count = len((outputs.get("yolo") or ProviderVisionOutput("yolo")).detections)
        ocr_count = len((outputs.get("paddleocr") or ProviderVisionOutput("paddleocr")).ocr_blocks)
        florence_bonus = 1.5 if (outputs.get("florence2") and outputs["florence2"].summary) else 0.0
        horizon_bonus = 1.0 if abs(frame.pitch) < 1 else 0.0
        score = yolo_count * 2.0 + ocr_count * 3.0 + florence_bonus + horizon_bonus
        scored.append((score, frame, frame_data))

    scored.sort(key=lambda item: (item[0], -abs(item[1].pitch), -item[1].frame_index), reverse=True)
    selected = [(frame, frame_data) for _, frame, frame_data in scored[:max_frames]]
    if frame_models and not any(frame.frame_index == 0 for frame, _ in selected):
        selected[-1:] = [frame_models[0]]
    # Stable visual order is easier to debug and keeps raw output deterministic.
    selected.sort(key=lambda item: item[0].frame_index)
    return selected


def _persist_local_output(
    analysis: VisionAnalysis,
    frame: VisionFrame,
    provider_name: str,
    output: ProviderVisionOutput,
) -> None:
    detections = []
    for index, item in enumerate(output.detections):
        attributes = {
            key: value
            for key, value in item.items()
            if key not in {"label", "confidence", "bbox"}
        }
        attributes.setdefault("local_index", item.get("local_index", index))
        detections.append(VisionDetection(
            analysis=analysis,
            frame=frame,
            provider=provider_name,
            label=str(item.get("label", "unknown"))[:160],
            confidence=float(item.get("confidence", 0) or 0),
            bbox=item.get("bbox", []),
            attributes=attributes,
        ))
    if detections:
        VisionDetection.objects.bulk_create(detections, batch_size=500)

    text_blocks = []
    for index, item in enumerate(output.ocr_blocks):
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        metadata = dict(item.get("metadata") or {})
        metadata.setdefault("local_index", item.get("local_index", index))
        text_blocks.append(OCRTextBlock(
            analysis=analysis,
            frame=frame,
            provider=provider_name,
            text=text,
            confidence=float(item.get("confidence", 0) or 0),
            polygon=item.get("polygon", []),
            language=str(metadata.get("language") or "")[:16],
            metadata=metadata,
        ))
    if text_blocks:
        OCRTextBlock.objects.bulk_create(text_blocks, batch_size=500)


def _safe_scene_type(outputs: list[ProviderVisionOutput]) -> str:
    for preferred in ("gemini", "openai", "florence2"):
        for output in outputs:
            if output.provider == preferred and output.scene_type:
                return output.scene_type
    return ""


def execute_analysis(analysis: VisionAnalysis) -> VisionAnalysis:
    analysis.status = VisionAnalysis.Status.RUNNING
    analysis.started_at = timezone.now()
    analysis.finished_at = None
    analysis.error_message = ""
    analysis.completed_providers = []
    analysis.failed_providers = {}
    analysis.save(update_fields=(
        "status", "started_at", "finished_at", "error_message",
        "completed_providers", "failed_providers", "updated_at",
    ))
    if analysis.scene_id:
        analysis.scene.ai_analysis_status = PipelineStatus.PROCESSING
        analysis.scene.ai_analysis_error = ""
        analysis.scene.save(update_fields=(
            "ai_analysis_status", "ai_analysis_error", "updated_at",
        ))

    try:
        image_bytes = resolve_analysis_image(analysis)
        frames = extract_panorama_frames(
            image_bytes,
            max_frames=int(getattr(settings, "VISION_MAX_PANORAMA_FRAMES", 12)),
        )
        provider_names = enabled_provider_names(analysis.requested_providers or None)

        analysis.frames.all().delete()
        analysis.detections.all().delete()
        analysis.ocr_blocks.all().delete()
        analysis.insights.all().delete()

        frame_models: list[tuple[VisionFrame, PanoramaFrameData]] = []
        for frame_data in frames:
            frame = VisionFrame(
                analysis=analysis,
                frame_index=frame_data.index,
                yaw=frame_data.yaw,
                pitch=frame_data.pitch,
                metadata={
                    "width": frame_data.width,
                    "height": frame_data.height,
                    "fov": frame_data.fov,
                },
            )
            frame.image.save(
                f"frame-{frame_data.index:02d}.jpg",
                ContentFile(frame_data.image_bytes),
                save=False,
            )
            frame.save()
            frame_models.append((frame, frame_data))

        failures: dict[str, Any] = {}
        completed: list[str] = []
        provider_outputs: list[ProviderVisionOutput] = []
        local_by_frame: dict[int, dict[str, ProviderVisionOutput]] = defaultdict(dict)

        # Stage 1: deterministic/local evidence on every perspective frame.
        for provider_name in [name for name in LOCAL_PROVIDERS if name in provider_names]:
            try:
                provider = build_provider(provider_name, organization=analysis.organization)
            except Exception as exc:
                failures[provider_name] = str(exc)
                logger.exception("Vision provider %s could not initialize", provider_name)
                continue

            frame_outputs: list[tuple[VisionFrame, ProviderVisionOutput]] = []
            frame_errors: list[str] = []
            for frame, frame_data in frame_models:
                try:
                    output = provider.analyze(frame_data.image_bytes)
                    local_by_frame[frame.frame_index][provider_name] = output
                    frame_outputs.append((frame, output))
                    _persist_local_output(analysis, frame, provider_name, output)
                except Exception as exc:
                    frame_errors.append(f"frame {frame.frame_index}: {exc}")
                    logger.exception(
                        "Vision provider %s failed on frame %s for analysis %s",
                        provider_name,
                        frame.frame_index,
                        analysis.pk,
                    )
            if frame_outputs:
                completed.append(provider_name)
                provider_outputs.append(_merge_provider_frame_outputs(provider_name, frame_outputs))
            if frame_errors:
                failures[provider_name] = frame_errors

        # Stage 2: Gemini has a precise role—semantic fusion of selected frames,
        # using YOLO boxes and PaddleOCR text as grounded evidence. OpenAI is a
        # fallback, not a duplicate paid call when Gemini succeeds.
        semantic_names = semantic_provider_order([
            name for name in SEMANTIC_PROVIDERS if name in provider_names
        ])
        semantic_frame_outputs: dict[str, list[tuple[VisionFrame, ProviderVisionOutput]]] = defaultdict(list)
        semantic_errors: dict[str, list[str]] = defaultdict(list)
        semantic_clients: dict[str, Any] = {}
        semantic_disabled_for_analysis: set[str] = set()

        if semantic_names:
            selected_frames = _select_semantic_frames(frame_models, local_by_frame)
            request_interval = max(
                0.0,
                float(getattr(settings, "VISION_SEMANTIC_REQUEST_INTERVAL_SECONDS", 1.0)),
            )
            last_cloud_call_at = 0.0
            for frame, frame_data in selected_frames:
                local_context = _frame_context(frame, local_by_frame.get(frame.frame_index, {}))
                succeeded = False
                for provider_name in semantic_names:
                    if provider_name in semantic_disabled_for_analysis:
                        continue
                    try:
                        if last_cloud_call_at and request_interval:
                            remaining = request_interval - (time.monotonic() - last_cloud_call_at)
                            if remaining > 0:
                                time.sleep(remaining)
                        provider = semantic_clients.get(provider_name)
                        if provider is None:
                            provider = build_provider(provider_name, organization=analysis.organization)
                            semantic_clients[provider_name] = provider
                        output = provider.analyze(frame_data.image_bytes, context=local_context)
                        last_cloud_call_at = time.monotonic()
                        semantic_frame_outputs[provider_name].append((frame, output))
                        succeeded = True
                        break
                    except Exception as exc:
                        last_cloud_call_at = time.monotonic()
                        semantic_errors[provider_name].append(f"frame {frame.frame_index}: {exc}")
                        error_text = str(exc).lower()
                        is_throttled = any(token in error_text for token in (
                            "429",
                            "resource_exhausted",
                            "resource exhausted",
                            "rate limit",
                            "temporarily bypassed",
                        ))
                        if is_throttled:
                            semantic_disabled_for_analysis.add(provider_name)
                            logger.warning(
                                "Semantic provider %s is disabled for the remainder of analysis %s "
                                "after quota throttling; the fallback provider will be used: %s",
                                provider_name,
                                analysis.pk,
                                exc,
                            )
                        else:
                            logger.warning(
                                "Semantic provider %s failed on frame %s for analysis %s: %s",
                                provider_name,
                                frame.frame_index,
                                analysis.pk,
                                exc,
                            )
                if not succeeded:
                    logger.error(
                        "No semantic vision provider succeeded on frame %s for analysis %s",
                        frame.frame_index,
                        analysis.pk,
                    )

        for provider_name, frame_outputs in semantic_frame_outputs.items():
            if frame_outputs:
                completed.append(provider_name)
                provider_outputs.append(_merge_provider_frame_outputs(provider_name, frame_outputs))
        for provider_name, errors in semantic_errors.items():
            # A provider that succeeded on at least one selected frame remains
            # completed, while its per-frame failures stay visible for monitoring.
            if errors:
                failures[provider_name] = errors

        fused = fuse_outputs(provider_outputs)
        semantic_scene_type = _safe_scene_type(provider_outputs)
        extracted_text = "\n".join(
            analysis.ocr_blocks.filter(provider="paddleocr")
            .order_by("frame_id", "id")
            .values_list("text", flat=True)
        )

        analysis.completed_providers = list(dict.fromkeys(completed))
        analysis.failed_providers = failures
        analysis.scene_type = semantic_scene_type or fused["scene_type"]
        analysis.summary = fused["summary"]
        analysis.features = fused["features"]
        analysis.products = fused["products"]
        analysis.extracted_text = extracted_text
        analysis.confidence = fused["confidence"]
        analysis.raw_results = fused["providers"]
        analysis.finished_at = timezone.now()

        if completed and failures:
            analysis.status = VisionAnalysis.Status.PARTIAL
        elif completed:
            analysis.status = VisionAnalysis.Status.SUCCEEDED
        else:
            analysis.status = VisionAnalysis.Status.FAILED
            analysis.error_message = "; ".join(
                f"{name}: {message}" for name, message in failures.items()
            ) or "No vision provider is enabled."
        analysis.save()

        insight_count = 0
        if analysis.status in {VisionAnalysis.Status.SUCCEEDED, VisionAnalysis.Status.PARTIAL}:
            insight_count = rebuild_insights(analysis)

        if analysis.scene_id:
            scene = analysis.scene
            scene.ai_analysis_status = (
                PipelineStatus.READY
                if analysis.status in {VisionAnalysis.Status.SUCCEEDED, VisionAnalysis.Status.PARTIAL}
                else PipelineStatus.FAILED
            )
            scene.ai_analysis = {
                "enterprise_analysis_id": str(analysis.pk),
                "scene_type": analysis.scene_type,
                "summary": analysis.summary,
                "features": analysis.features,
                "products": analysis.products,
                "extracted_text": analysis.extracted_text,
                "confidence": analysis.confidence,
                "providers": analysis.completed_providers,
                "insight_count": insight_count,
                "pipeline": {
                    "object_detection": "yolo" if "yolo" in analysis.completed_providers else None,
                    "ocr": "paddleocr" if "paddleocr" in analysis.completed_providers else None,
                    "semantic_fusion": next(
                        (name for name in ("gemini", "openai") if name in analysis.completed_providers),
                        None,
                    ),
                },
            }
            scene.ai_analysis_error = analysis.error_message
            scene.ai_analyzed_at = analysis.finished_at
            scene.save(update_fields=(
                "ai_analysis_status", "ai_analysis", "ai_analysis_error",
                "ai_analyzed_at", "updated_at",
            ))
        return analysis

    except Exception as exc:
        logger.exception("Vision analysis %s failed", analysis.pk)
        analysis.status = VisionAnalysis.Status.FAILED
        analysis.error_message = str(exc)
        analysis.finished_at = timezone.now()
        analysis.save(update_fields=("status", "error_message", "finished_at", "updated_at"))
        if analysis.scene_id:
            scene = analysis.scene
            scene.ai_analysis_status = PipelineStatus.FAILED
            scene.ai_analysis_error = str(exc)
            scene.ai_analyzed_at = analysis.finished_at
            scene.save(update_fields=(
                "ai_analysis_status", "ai_analysis_error", "ai_analyzed_at", "updated_at",
            ))
        raise
