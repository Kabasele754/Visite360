from __future__ import annotations

import io
import json
import logging
import math
from collections import defaultdict, deque
from typing import Any

from PIL import Image, ImageOps
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.ai_core.services.providers import parse_json_object
from apps.tours.models import (
    Hotspot,
    Scene360,
    SceneLinkProposal,
    SceneObjectCandidate,
    Tour,
    TourArchitectureRun,
)

logger = logging.getLogger(__name__)


def _clamp(value: Any, minimum: float, maximum: float, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    return max(minimum, min(maximum, numeric))


def _scene_image_bytes(scene: Scene360) -> bytes | None:
    for field_name in ("thumbnail_image", "image_360_preview", "image_360_mobile", "image_360"):
        field = getattr(scene, field_name, None)
        if not field:
            continue
        try:
            field.open("rb")
            try:
                payload = field.read()
            finally:
                field.close()
            with Image.open(io.BytesIO(payload)) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
                image.thumbnail((1000, 500), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                image.save(output, "JPEG", quality=84, optimize=True)
                return output.getvalue()
        except Exception:
            logger.warning("Could not read architect image for scene %s", scene.pk, exc_info=True)
    return None


def _candidate_image_bytes(candidate: SceneObjectCandidate) -> bytes | None:
    field = candidate.enhanced_crop_image or candidate.crop_image
    if not field:
        return None
    try:
        field.open("rb")
        try:
            payload = field.read()
        finally:
            field.close()
        with Image.open(io.BytesIO(payload)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.thumbnail((480, 480), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, "JPEG", quality=82, optimize=True)
            return output.getvalue()
    except Exception:
        return None


def _build_scene_manifest(scenes: list[Scene360]) -> tuple[list[dict[str, Any]], dict[int, SceneObjectCandidate]]:
    anchor_lookup: dict[int, SceneObjectCandidate] = {}
    manifest: list[dict[str, Any]] = []
    max_anchors = max(1, int(getattr(settings, "TOUR_ARCHITECT_MAX_ANCHORS_PER_SCENE", 6)))
    for scene in scenes:
        quality = getattr(scene, "visual_quality", None)
        anchors = list(
            scene.object_candidates.filter(
                is_navigation_anchor=True,
                review_status__in=[
                    SceneObjectCandidate.ReviewStatus.SUGGESTED,
                    SceneObjectCandidate.ReviewStatus.APPROVED,
                ],
            )
            .order_by("-confidence", "-quality_score")[:max_anchors]
        )
        for anchor in anchors:
            anchor_lookup[anchor.pk] = anchor
        manifest.append({
            "scene_id": scene.pk,
            "scene_key": scene.scene_id,
            "title": scene.title,
            "order": scene.order,
            "summary": str((scene.ai_analysis or {}).get("summary") or "")[:500],
            "scene_type": str((scene.ai_analysis or {}).get("scene_type") or "")[:120],
            "quality_score": round(float(getattr(quality, "overall_score", 0) or 0), 4),
            "existing_navigation_links": [
                {
                    "target_scene_id": hotspot.target_scene_id,
                    "yaw": round(float(hotspot.yaw), 6),
                    "pitch": round(float(hotspot.pitch), 6),
                    "source": "ai" if hotspot.is_ai_generated else "manual",
                }
                for hotspot in scene.hotspots.all()
                if hotspot.target_scene_id
                and hotspot.type in {Hotspot.Type.NAVIGATE, Hotspot.Type.FLOOR, Hotspot.Type.DOOR}
            ],
            "navigation_anchors": [
                {
                    "candidate_id": anchor.pk,
                    "title": anchor.title,
                    "label": anchor.label,
                    "yaw": round(float(anchor.yaw), 6),
                    "pitch": round(float(anchor.pitch), 6),
                    "confidence": round(float(anchor.confidence), 4),
                    "quality": round(float(anchor.quality_score), 4),
                }
                for anchor in anchors
            ],
        })
    return manifest, anchor_lookup


def _response_schema() -> dict[str, Any]:
    return {
        "type": "OBJECT",
        "properties": {
            "layout_summary": {"type": "STRING"},
            "warnings": {"type": "ARRAY", "items": {"type": "STRING"}},
            "links": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "from_scene_id": {"type": "INTEGER"},
                        "to_scene_id": {"type": "INTEGER"},
                        "from_anchor_candidate_id": {"type": "INTEGER"},
                        "to_anchor_candidate_id": {"type": "INTEGER"},
                        "from_yaw": {"type": "NUMBER"},
                        "from_pitch": {"type": "NUMBER"},
                        "to_yaw": {"type": "NUMBER"},
                        "to_pitch": {"type": "NUMBER"},
                        "confidence": {"type": "NUMBER"},
                        "bidirectional": {"type": "BOOLEAN"},
                        "rationale": {"type": "STRING"},
                        "visual_evidence": {"type": "ARRAY", "items": {"type": "STRING"}},
                    },
                    "required": [
                        "from_scene_id", "to_scene_id", "from_anchor_candidate_id",
                        "to_anchor_candidate_id", "from_yaw", "from_pitch", "to_yaw",
                        "to_pitch", "confidence", "bidirectional", "rationale", "visual_evidence",
                    ],
                },
            },
        },
        "required": ["layout_summary", "warnings", "links"],
    }


def _gemini_plan(tour: Tour, scenes: list[Scene360], manifest: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("google_genai_unavailable") from exc

    model = str(
        getattr(settings, "TOUR_ARCHITECT_GEMINI_MODEL", "")
        or getattr(settings, "GOOGLE_TEXT_MODEL", "gemini-2.5-flash")
    )
    prompt = f"""You are Twinscopes Tour Architect, a specialist in 360-degree indoor navigation.
Build a conservative navigation graph for the virtual tour named {tour.title!r}.

You receive one panorama preview for every scene and optional close crops of detected doors,
entrances, corridors, stairs, lifts or passages. Return only links that are visually plausible.
The output is a PROPOSAL for human review, not a claim about the real building layout.

Rules:
- Use only scene IDs and candidate IDs from SCENE_MANIFEST.
- Never connect a scene to itself.
- Prefer reciprocal/bidirectional navigation when the reverse transition is visually plausible.
- Prefer a detected navigation anchor. Use anchor id 0 only when no portal candidate is available.
- yaw and pitch are Marzipano radians. yaw must be in [-3.14159, 3.14159], pitch in [-1.2, 1.2].
- When an anchor candidate is selected, copy its yaw and pitch exactly.
- A scene should normally have no more than four outgoing links.
- Treat existing_navigation_links as fixed edges. Do not propose a duplicate edge in the same direction.
- Use existing links to understand the current graph and propose only missing transitions.
- Do not infer a link only because two scenes are adjacent in upload order.
- Calibrate confidence: >=0.90 requires strong matching visual evidence; 0.65-0.89 is plausible;
  below 0.65 needs careful review.
- Explain the visible evidence briefly. Do not invent doors, room names or geometry.
- Try to connect all scenes into one usable graph, but put uncertain assumptions in warnings.

SCENE_MANIFEST:
{json.dumps(manifest, ensure_ascii=False, indent=2)}
"""

    http_options = types.HttpOptions(
        api_version="v1",
        timeout=int(getattr(settings, "TOUR_ARCHITECT_TIMEOUT_SECONDS", 150) * 1000),
    )
    if getattr(settings, "GOOGLE_GENAI_USE_VERTEXAI", False):
        client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_LOCATION,
            http_options=http_options,
        )
    else:
        api_key = getattr(settings, "GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("gemini_credentials_unavailable")
        client = genai.Client(api_key=api_key, http_options=http_options)

    contents: list[Any] = [prompt]
    include_anchor_crops = bool(getattr(settings, "TOUR_ARCHITECT_INCLUDE_ANCHOR_CROPS", True))
    for scene in scenes:
        image_bytes = _scene_image_bytes(scene)
        contents.append(f"SCENE {scene.pk} — {scene.title}")
        if image_bytes:
            contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
        if include_anchor_crops:
            anchors = list(
                scene.object_candidates.filter(is_navigation_anchor=True)
                .exclude(review_status=SceneObjectCandidate.ReviewStatus.REJECTED)
                .order_by("-confidence")[:3]
            )
            for anchor in anchors:
                crop = _candidate_image_bytes(anchor)
                if crop:
                    contents.append(
                        f"SCENE {scene.pk} NAVIGATION CANDIDATE {anchor.pk} — {anchor.title}; "
                        f"yaw={anchor.yaw:.6f}, pitch={anchor.pitch:.6f}"
                    )
                    contents.append(types.Part.from_bytes(data=crop, mime_type="image/jpeg"))

    try:
        config_kwargs = {
            "temperature": 0.08,
            "max_output_tokens": int(getattr(settings, "TOUR_ARCHITECT_MAX_OUTPUT_TOKENS", 5000)),
            "response_mime_type": "application/json",
            "response_schema": _response_schema(),
        }
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as exc:
            # Older Google GenAI SDK/model combinations may reject a schema
            # even though JSON mode itself is supported. Retry only that
            # compatibility failure; rate limits and provider failures must be
            # handled by the normal fallback path without a duplicate request.
            message = str(exc).lower()
            status_code = getattr(exc, "status_code", None)
            schema_compatibility_error = (
                isinstance(exc, (TypeError, ValueError))
                or (status_code == 400 and any(token in message for token in ("schema", "response_schema", "invalid argument")))
            )
            if not schema_compatibility_error:
                raise
            logger.warning(
                "Gemini structured schema was rejected for Tour Architect; retrying with JSON mode only."
            )
            config_kwargs.pop("response_schema", None)
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )

        parsed = parse_json_object(getattr(response, "text", "") or "")
        return parsed, model
    finally:
        try:
            client.close()
        except Exception:
            pass


def _deterministic_backbone(scenes: list[Scene360]) -> dict[str, Any]:
    links: list[dict[str, Any]] = []
    for index in range(len(scenes) - 1):
        source = scenes[index]
        target = scenes[index + 1]
        source_anchor = source.object_candidates.filter(is_navigation_anchor=True).order_by("-confidence").first()
        target_anchor = target.object_candidates.filter(is_navigation_anchor=True).order_by("-confidence").first()
        links.append({
            "from_scene_id": source.pk,
            "to_scene_id": target.pk,
            "from_anchor_candidate_id": source_anchor.pk if source_anchor else 0,
            "to_anchor_candidate_id": target_anchor.pk if target_anchor else 0,
            "from_yaw": source_anchor.yaw if source_anchor else source.yaw_default,
            "from_pitch": source_anchor.pitch if source_anchor else source.pitch_default,
            "to_yaw": target_anchor.yaw if target_anchor else target.yaw_default,
            "to_pitch": target_anchor.pitch if target_anchor else target.pitch_default,
            "confidence": 0.40 if source_anchor and target_anchor else 0.28,
            "bidirectional": True,
            "rationale": "Connectivity fallback generated for human review because Gemini did not return a complete graph.",
            "visual_evidence": ["upload-order fallback", "requires manual confirmation"],
            "fallback": True,
        })
    return {
        "layout_summary": "A conservative sequential fallback graph was prepared for manual review.",
        "warnings": ["Gemini topology planning was unavailable or incomplete."],
        "links": links,
    }


def _connected_scene_ids(links: list[dict[str, Any]], scene_ids: set[int]) -> set[int]:
    if not scene_ids:
        return set()
    adjacency: dict[int, set[int]] = defaultdict(set)
    for item in links:
        try:
            source = int(item["from_scene_id"])
            target = int(item["to_scene_id"])
        except Exception:
            continue
        if source in scene_ids and target in scene_ids and source != target:
            adjacency[source].add(target)
            adjacency[target].add(source)
    start = next(iter(scene_ids))
    visited = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in adjacency[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return visited


def _normalized_links(
    raw: dict[str, Any],
    scenes: list[Scene360],
    anchor_lookup: dict[int, SceneObjectCandidate],
) -> tuple[list[dict[str, Any]], list[str]]:
    scene_lookup = {scene.pk: scene for scene in scenes}
    allowed_ids = set(scene_lookup)
    links: list[dict[str, Any]] = []
    warnings = [str(value)[:400] for value in raw.get("warnings", []) if str(value).strip()]
    existing_links = list(
        Hotspot.objects.filter(
            scene_id__in=allowed_ids,
            target_scene_id__in=allowed_ids,
            type__in=[Hotspot.Type.NAVIGATE, Hotspot.Type.FLOOR, Hotspot.Type.DOOR],
        ).values("scene_id", "target_scene_id")
    )
    existing_pairs = {(int(item["scene_id"]), int(item["target_scene_id"])) for item in existing_links}
    seen_pairs: set[tuple[int, int]] = set(existing_pairs)
    seen_bidirectional_pairs: set[frozenset[int]] = set()
    outgoing_count: dict[int, int] = defaultdict(int)
    for source_id, _target_id in existing_pairs:
        outgoing_count[source_id] += 1
    max_outgoing = max(1, int(getattr(settings, "TOUR_ARCHITECT_MAX_OUTGOING_LINKS", 4)))

    for item in raw.get("links", []) or []:
        if not isinstance(item, dict):
            continue
        try:
            source_id = int(item.get("from_scene_id"))
            target_id = int(item.get("to_scene_id"))
        except (TypeError, ValueError):
            continue
        if source_id not in allowed_ids or target_id not in allowed_ids or source_id == target_id:
            continue
        bidirectional = bool(item.get("bidirectional", True))
        undirected_pair = frozenset((source_id, target_id))
        if (source_id, target_id) in seen_pairs or outgoing_count[source_id] >= max_outgoing:
            continue
        if bidirectional and undirected_pair in seen_bidirectional_pairs:
            continue
        from_anchor = anchor_lookup.get(int(item.get("from_anchor_candidate_id") or 0))
        to_anchor = anchor_lookup.get(int(item.get("to_anchor_candidate_id") or 0))
        if from_anchor and from_anchor.scene_id != source_id:
            from_anchor = None
        if to_anchor and to_anchor.scene_id != target_id:
            to_anchor = None
        from_yaw = from_anchor.yaw if from_anchor else _clamp(item.get("from_yaw"), -math.pi, math.pi, scene_lookup[source_id].yaw_default)
        from_pitch = from_anchor.pitch if from_anchor else _clamp(item.get("from_pitch"), -1.2, 1.2, scene_lookup[source_id].pitch_default)
        to_yaw = to_anchor.yaw if to_anchor else _clamp(item.get("to_yaw"), -math.pi, math.pi, scene_lookup[target_id].yaw_default)
        to_pitch = to_anchor.pitch if to_anchor else _clamp(item.get("to_pitch"), -1.2, 1.2, scene_lookup[target_id].pitch_default)
        confidence = _clamp(item.get("confidence"), 0.0, 1.0, 0.35)
        evidence = [str(value)[:300] for value in item.get("visual_evidence", []) if str(value).strip()]
        links.append({
            "from_scene_id": source_id,
            "to_scene_id": target_id,
            "from_anchor": from_anchor,
            "to_anchor": to_anchor,
            "from_yaw": float(from_yaw),
            "from_pitch": float(from_pitch),
            "to_yaw": float(to_yaw),
            "to_pitch": float(to_pitch),
            "confidence": confidence,
            "bidirectional": bidirectional,
            "rationale": str(item.get("rationale") or "Visual transition proposal.")[:900],
            "visual_evidence": evidence,
            "fallback": bool(item.get("fallback")),
        })
        seen_pairs.add((source_id, target_id))
        if bidirectional:
            seen_bidirectional_pairs.add(undirected_pair)
        outgoing_count[source_id] += 1

    connectivity_links = links + [
        {"from_scene_id": source_id, "to_scene_id": target_id}
        for source_id, target_id in existing_pairs
    ]
    visited = _connected_scene_ids(connectivity_links, allowed_ids)
    if len(visited) < len(allowed_ids):
        warnings.append("The Gemini graph did not connect every scene; low-confidence review links were added.")
        ordered = sorted(scenes, key=lambda scene: (scene.order, scene.pk))
        fallback = _deterministic_backbone(ordered)["links"]
        for item in fallback:
            source_id = int(item["from_scene_id"])
            target_id = int(item["to_scene_id"])
            if source_id in visited and target_id in visited:
                continue
            if (source_id, target_id) in seen_pairs:
                visited.update({source_id, target_id})
                continue
            from_anchor = anchor_lookup.get(int(item.get("from_anchor_candidate_id") or 0))
            to_anchor = anchor_lookup.get(int(item.get("to_anchor_candidate_id") or 0))
            links.append({
                "from_scene_id": source_id,
                "to_scene_id": target_id,
                "from_anchor": from_anchor,
                "to_anchor": to_anchor,
                "from_yaw": float(item["from_yaw"]),
                "from_pitch": float(item["from_pitch"]),
                "to_yaw": float(item["to_yaw"]),
                "to_pitch": float(item["to_pitch"]),
                "confidence": float(item["confidence"]),
                "bidirectional": True,
                "rationale": item["rationale"],
                "visual_evidence": item["visual_evidence"],
                "fallback": True,
            })
            seen_pairs.add((source_id, target_id))
            visited.update({source_id, target_id})
    return links, warnings


@transaction.atomic
def apply_link_proposal(proposal: SceneLinkProposal, *, user=None) -> SceneLinkProposal:
    proposal = (
        SceneLinkProposal.objects.select_for_update()
        .select_related("tour", "from_scene", "to_scene", "run")
        .get(pk=proposal.pk)
    )
    if proposal.status == SceneLinkProposal.Status.APPLIED:
        return proposal

    existing = Hotspot.objects.filter(
        scene=proposal.from_scene,
        type=Hotspot.Type.NAVIGATE,
        target_scene=proposal.to_scene,
    ).first()
    if existing and not existing.is_ai_generated:
        proposal.status = SceneLinkProposal.Status.CONFLICT
        proposal.evidence = {
            **(proposal.evidence or {}),
            "conflict": "A manual navigation hotspot already connects these scenes.",
        }
        proposal.reviewed_by = user if getattr(user, "is_authenticated", False) else None
        proposal.reviewed_at = timezone.now()
        proposal.save()
        return proposal

    payload = {
        "architect_generated": True,
        "architect_run_id": str(proposal.run_id),
        "proposal_id": proposal.pk,
        "confidence": proposal.confidence,
        "rationale": proposal.rationale,
        "source": proposal.source,
    }
    primary_defaults = {
        "organization": proposal.tour.organization,
        "label": f"Go to {proposal.to_scene.title}",
        "title": proposal.to_scene.title,
        "description": "Continue the virtual tour.",
        "tooltip_text": f"Open {proposal.to_scene.title}",
        "selected_icon": "chevronforward",
        "yaw": proposal.from_yaw,
        "pitch": proposal.from_pitch,
        "payload": payload,
        "is_ai_generated": True,
    }
    if existing:
        for field, value in primary_defaults.items():
            setattr(existing, field, value)
        existing.save()
        primary = existing
    else:
        primary = Hotspot.objects.create(
            scene=proposal.from_scene,
            target_scene=proposal.to_scene,
            type=Hotspot.Type.NAVIGATE,
            **primary_defaults,
        )

    reverse = None
    if proposal.is_bidirectional:
        reverse_existing = Hotspot.objects.filter(
            scene=proposal.to_scene,
            type=Hotspot.Type.NAVIGATE,
            target_scene=proposal.from_scene,
        ).first()
        if not reverse_existing or reverse_existing.is_ai_generated:
            reverse_defaults = {
                "organization": proposal.tour.organization,
                "label": f"Return to {proposal.from_scene.title}",
                "title": proposal.from_scene.title,
                "description": "Return to the previous part of the virtual tour.",
                "tooltip_text": f"Return to {proposal.from_scene.title}",
                "selected_icon": "chevronleft",
                "yaw": proposal.to_yaw,
                "pitch": proposal.to_pitch,
                "payload": {**payload, "reverse": True},
                "is_ai_generated": True,
            }
            if reverse_existing:
                for field, value in reverse_defaults.items():
                    setattr(reverse_existing, field, value)
                reverse_existing.save()
                reverse = reverse_existing
            else:
                reverse = Hotspot.objects.create(
                    scene=proposal.to_scene,
                    target_scene=proposal.from_scene,
                    type=Hotspot.Type.NAVIGATE,
                    **reverse_defaults,
                )

    proposal.applied_from_hotspot = primary
    proposal.applied_reverse_hotspot = reverse
    proposal.status = SceneLinkProposal.Status.APPLIED
    proposal.reviewed_by = user if getattr(user, "is_authenticated", False) else None
    proposal.reviewed_at = timezone.now()
    proposal.save()
    run = proposal.run
    run.applied_count = run.proposals.filter(status=SceneLinkProposal.Status.APPLIED).count()
    if run.applied_count and run.applied_count == run.proposal_count:
        run.status = TourArchitectureRun.Status.APPLIED
    run.save(update_fields=("applied_count", "status", "updated_at"))
    return proposal


def build_tour_architecture(tour: Tour, *, run: TourArchitectureRun | None = None, force: bool = False) -> TourArchitectureRun:
    scenes = list(
        Scene360.objects.filter(tour=tour)
        .select_related("visual_quality")
        .prefetch_related("object_candidates", "hotspots")
        .order_by("order", "pk")
    )
    if run is None:
        run = TourArchitectureRun.objects.create(
            organization=tour.organization,
            tour=tour,
            provider="gemini",
        )
    run.status = TourArchitectureRun.Status.RUNNING
    run.stage = "preparing_scene_graph"
    run.started_at = timezone.now()
    run.finished_at = None
    run.error_code = ""
    run.scene_count = len(scenes)
    run.object_count = SceneObjectCandidate.objects.filter(scene__tour=tour).exclude(
        review_status=SceneObjectCandidate.ReviewStatus.HIDDEN
    ).count()
    run.save()

    if len(scenes) < 2:
        run.status = TourArchitectureRun.Status.FAILED
        run.stage = "insufficient_scenes"
        run.error_code = "at_least_two_scenes_required"
        run.finished_at = timezone.now()
        run.save()
        return run

    try:
        manifest, anchor_lookup = _build_scene_manifest(scenes)
        run.stage = "gemini_topology_reasoning"
        run.save(update_fields=("stage", "updated_at"))
        source = SceneLinkProposal.Source.GEMINI
        try:
            raw, model = _gemini_plan(tour, scenes, manifest)
        except Exception as exc:
            logger.warning("Gemini tour architecture failed for tour %s: %s", tour.pk, exc, exc_info=True)
            raw = _deterministic_backbone(scenes)
            model = str(getattr(settings, "TOUR_ARCHITECT_GEMINI_MODEL", "gemini"))
            source = SceneLinkProposal.Source.DETERMINISTIC
            raw.setdefault("warnings", []).append("Gemini was unavailable; fallback links require manual review.")

        links, warnings = _normalized_links(raw, scenes, anchor_lookup)
        run.model_name = model
        run.stage = "staging_review_proposals"
        run.save(update_fields=("model_name", "stage", "updated_at"))

        for item in links:
            proposal_source = SceneLinkProposal.Source.DETERMINISTIC if item.get("fallback") else source
            SceneLinkProposal.objects.update_or_create(
                run=run,
                from_scene_id=item["from_scene_id"],
                to_scene_id=item["to_scene_id"],
                defaults={
                    "tour": tour,
                    "from_anchor": item.get("from_anchor"),
                    "to_anchor": item.get("to_anchor"),
                    "from_yaw": item["from_yaw"],
                    "from_pitch": item["from_pitch"],
                    "to_yaw": item["to_yaw"],
                    "to_pitch": item["to_pitch"],
                    "confidence": item["confidence"],
                    "rationale": item["rationale"],
                    "evidence": {
                        "visual_evidence": item["visual_evidence"],
                        "fallback": bool(item.get("fallback")),
                    },
                    "source": proposal_source,
                    "status": SceneLinkProposal.Status.SUGGESTED,
                    "is_bidirectional": item["bidirectional"],
                },
            )

        run.proposal_count = run.proposals.count()
        run.summary = {
            "layout_summary": str(raw.get("layout_summary") or "")[:1500],
            "warnings": warnings,
            "scene_manifest": manifest,
            "gemini_used": source == SceneLinkProposal.Source.GEMINI,
            "human_review_required": True,
        }
        run.status = TourArchitectureRun.Status.REVIEW
        run.stage = "ready_for_review" if run.proposal_count else "no_new_links_required"
        run.error_code = ""
        if not run.proposal_count:
            run.summary["warnings"] = list(run.summary.get("warnings") or []) + [
                "No additional navigation links were required or confidently identified. Existing links were preserved."
            ]
        run.finished_at = timezone.now()
        run.save()

        if bool(getattr(settings, "TOUR_ARCHITECT_AUTO_APPLY_SAFE_LINKS", False)):
            threshold = float(getattr(settings, "TOUR_ARCHITECT_AUTO_APPLY_MIN_CONFIDENCE", 0.94))
            for proposal in run.proposals.filter(
                confidence__gte=threshold,
                source=SceneLinkProposal.Source.GEMINI,
                from_anchor__isnull=False,
                to_anchor__isnull=False,
            ):
                apply_link_proposal(proposal)
        return run
    except Exception as exc:
        logger.exception("Tour architecture failed for tour %s", tour.pk)
        run.status = TourArchitectureRun.Status.FAILED
        run.stage = "failed"
        run.error_code = "tour_architecture_failed"
        run.summary = {"technical_detail": str(exc)[:1000]}
        run.finished_at = timezone.now()
        run.save()
        return run
