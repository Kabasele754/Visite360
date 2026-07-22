from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from celery import shared_task

from apps.tours.models import (
    DeliveryStatus,
    Hotspot,
    PipelineStatus,
    Scene360,
    Scene360Tile,
    Tour,
    TourEmailLog,
)
from apps.tours.utils_compress_image import (
    compress_image,
    generate_panorama_preview,
    generate_panorama_thumbnail,
)
from apps.tours.utils_tiles_360 import (
    generate_multires_cube_tiles_from_equirectangular,
)


def _content_file_from_bytes(data, name="file.bin"):
    content = ContentFile(data)
    content.name = name
    return content


def _read_field_bytes(file_field):
    if not file_field:
        return None

    try:
        file_field.open("rb")
        return file_field.read()
    finally:
        try:
            file_field.close()
        except Exception:
            pass


def _build_scene_tiles_url_template(scene):
    return (
        f"tours/panoramas/tiles/"
        f"{scene.scene_id}/"
        f"l{{z}}/"
        f"{{f}}/"
        f"{{x}}_{{y}}.webp"
    )


def _generate_scene_assets(scene):
    source_bytes = _read_field_bytes(scene.image_360_original)
    if not source_bytes:
        raise ValueError("Aucune image source trouvée pour la scène.")

    base_name = scene.title.lower().replace(" ", "-") or f"scene-{scene.pk}"

    preview_content, preview_size_kb = generate_panorama_preview(
        _content_file_from_bytes(source_bytes, scene.image_360_original.name),
        size=(512, 256),
        quality=38,
        target_max_kb=28,
        blur_radius=1.15,
    )
    scene.image_360_preview.save(
        f"{base_name}-preview.webp",
        preview_content,
        save=False,
    )

    desktop_content, desktop_size_kb = compress_image(
        _content_file_from_bytes(source_bytes, scene.image_360_original.name),
        add_watermark=False,
        max_width=3000,
        max_height=1500,
        initial_quality=80,
        min_quality=60,
        target_max_kb=900,
    )
    scene.image_360.save(
        f"{base_name}-desktop.webp",
        desktop_content,
        save=False,
    )

    mobile_content, mobile_size_kb = compress_image(
        _content_file_from_bytes(source_bytes, scene.image_360_original.name),
        add_watermark=False,
        max_width=1600,
        max_height=800,
        initial_quality=74,
        min_quality=54,
        target_max_kb=350,
    )
    scene.image_360_mobile.save(
        f"{base_name}-mobile.webp",
        mobile_content,
        save=False,
    )

    thumb_content, thumb_size_kb = generate_panorama_thumbnail(
        _content_file_from_bytes(source_bytes, scene.image_360_original.name),
        size=(1200, 600),
        quality=70,
        target_max_kb=160,
    )
    scene.thumbnail_image.save(
        f"{base_name}-thumb.webp",
        thumb_content,
        save=False,
    )

    scene.assets_status = PipelineStatus.READY
    scene.assets_error = ""
    scene.assets_generated_at = timezone.now()

    return {
        "preview_kb": preview_size_kb,
        "desktop_kb": desktop_size_kb,
        "mobile_kb": mobile_size_kb,
        "thumb_kb": thumb_size_kb,
    }


def _generate_scene_tiles(scene):
    if not scene.tiles_enabled:
        scene.tiles_status = PipelineStatus.NONE
        scene.tiles_error = ""
        return {"tiles_enabled": False}

    source_bytes = _read_field_bytes(scene.image_360_original)
    if not source_bytes:
        raise ValueError("Aucune image source trouvée pour générer les tiles.")

    manifest, tiles = generate_multires_cube_tiles_from_equirectangular(
        _content_file_from_bytes(source_bytes, scene.image_360_original.name),
        tile_size=scene.tile_size,
        max_cube_size=scene.max_tile_cube_size,
        min_cube_size=512,
        initial_quality=76,
        min_quality=54,
        target_tile_max_kb=180,
    )

    manifest["urlTemplate"] = _build_scene_tiles_url_template(scene)
    manifest["sceneId"] = scene.scene_id
    manifest["storage"] = "relative-media-path"
    manifest["generatedAt"] = timezone.now().isoformat()

    existing_tiles = scene.tiles.all()
    for tile in existing_tiles:
        if tile.image:
            tile.image.delete(save=False)
    existing_tiles.delete()

    created_count = 0

    with transaction.atomic():
        for item in tiles:
            tile = Scene360Tile(
                organization=scene.organization,
                scene=scene,
                level=item["level"],
                cube_size=item["cube_size"],
                face=item["face"],
                x=item["x"],
                y=item["y"],
                width=item["width"],
                height=item["height"],
                size_kb=item["size_kb"],
                quality=item["quality"],
            )
            tile.image.save(
                f'{item["x"]}_{item["y"]}.webp',
                item["content"],
                save=False,
            )
            tile.save()
            created_count += 1

    scene.tiles_manifest = manifest
    scene.tiles_status = PipelineStatus.READY
    scene.tiles_generated_at = timezone.now()
    scene.tiles_error = ""

    return {"tiles_count": created_count}



def _real_ai_analysis(scene):
    """Run the real Twinscopes Vision pipeline (YOLO + optional Gemini Vision)."""
    from apps.tour_ai_agent.vision.scene_analyzer import analyze_scene

    profile = analyze_scene(scene, force=True)
    detections = profile.local_detections or []
    recommended_hotspots = []
    for index, detection in enumerate(detections[:8]):
        yaw = float(detection.get("yaw", 0.0))
        pitch = float(detection.get("pitch", 0.0)) / 90.0
        label = str(detection.get("label", "Object")).replace("_", " ").title()
        recommended_hotspots.append({
            "type": "info",
            "label": label,
            "title": label,
            "description": f"Detected by Twinscopes Vision ({float(detection.get('confidence', 0)):.0%} confidence).",
            "selected_icon": "info",
            "yaw": yaw,
            "pitch": pitch,
        })

    return {
        "scene_title": scene.title,
        "scene_type": profile.final_scene_type or profile.local_scene_type or "general",
        "confidence": float(profile.analysis_confidence or profile.local_scene_confidence or 0),
        "summary": profile.final_summary,
        "detected_features": profile.final_features or profile.local_features or [],
        "detections": detections,
        "analysis_source": profile.analysis_source,
        "gemini": profile.gemini_payload or {},
        "recommended_hotspots": recommended_hotspots,
    }

def _mock_ai_analysis(scene):
    title = (scene.title or "").lower()

    room_type = "general"
    if "salon" in title or "living" in title:
        room_type = "living_room"
    elif "chambre" in title or "bedroom" in title:
        room_type = "bedroom"
    elif "kitchen" in title or "cuisine" in title:
        room_type = "kitchen"
    elif "bath" in title or "salle de bain" in title:
        room_type = "bathroom"
    elif "balcon" in title or "terrace" in title:
        room_type = "balcony"

    features = []
    if scene.tour.parking:
        features.append("parking")
    if scene.tour.balcon:
        features.append("balcony")
    if scene.tour.ascenseur:
        features.append("elevator")

    analysis = {
        "scene_title": scene.title,
        "scene_type": room_type,
        "confidence": 0.72,
        "detected_features": features,
        "recommended_hotspots": [
            {
                "type": "info",
                "label": "Informations",
                "title": f"Espace : {scene.title}",
                "description": f"Découvrez les points forts de {scene.title}.",
                "selected_icon": "info",
                "yaw": 0.0,
                "pitch": -0.1,
            },
            {
                "type": "product",
                "label": "Découvrir",
                "title": "Détails de cet espace",
                "description": "Voir davantage de détails sur cet espace.",
                "selected_icon": "product",
                "yaw": 0.6,
                "pitch": -0.05,
            },
        ],
    }

    return analysis


def _generate_ai_hotspots(scene, analysis):
    suggestions = analysis.get("recommended_hotspots", [])
    created_ids = []

    # Supprimer anciens hotspots IA
    scene.hotspots.filter(is_ai_generated=True).delete()

    for item in suggestions:
        payload = {
            "ai_generated": True,
            "content": {
                "title": item.get("title") or item.get("label"),
                "description": item.get("description", ""),
            },
            "source": "mock-ai",
        }

        hotspot = Hotspot.objects.create(
            organization=scene.organization,
            scene=scene,
            type=item.get("type", Hotspot.Type.INFO),
            label=item.get("label", "AI Hotspot"),
            title=item.get("title", ""),
            description=item.get("description", ""),
            tooltip_text=item.get("label", ""),
            selected_icon=item.get("selected_icon", "info"),
            yaw=item.get("yaw", 0),
            pitch=item.get("pitch", 0),
            payload=payload,
            is_ai_generated=True,
        )
        created_ids.append(hotspot.id)

    return created_ids


def _build_prefetch_manifest_for_tour(tour):
    scenes = list(
        tour.scenes.filter(status=Scene360.Status.PUBLISHED)
        .order_by("order", "id")
    )

    for index, scene in enumerate(scenes):
        previous_scene = scenes[index - 1] if index - 1 >= 0 else None
        next_scene = scenes[index + 1] if index + 1 < len(scenes) else None

        neighbors = []
        if previous_scene:
            neighbors.append(
                {
                    "scene_id": previous_scene.scene_id,
                    "preview": previous_scene.image_360_preview_url,
                    "mobile": previous_scene.image_360_mobile_url,
                    "desktop": previous_scene.image_360_url,
                }
            )
        if next_scene:
            neighbors.append(
                {
                    "scene_id": next_scene.scene_id,
                    "preview": next_scene.image_360_preview_url,
                    "mobile": next_scene.image_360_mobile_url,
                    "desktop": next_scene.image_360_url,
                }
            )

        scene.prefetch_manifest = {
            "current_scene_id": scene.scene_id,
            "previous_scene_id": previous_scene.scene_id if previous_scene else None,
            "next_scene_id": next_scene.scene_id if next_scene else None,
            "neighbors": neighbors,
        }
        scene.prefetch_generated_at = timezone.now()
        scene.save(update_fields=["prefetch_manifest", "prefetch_generated_at", "updated_at"])


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def generate_tour_thumbnail_assets_task(self, tour_id):
    from apps.tours.utils_compress_image import compress_image

    tour = Tour.objects.filter(pk=tour_id).first()
    if not tour:
        return {"ok": False, "message": "Tour introuvable"}

    source_bytes = _read_field_bytes(tour.thumbnail_source)
    if not source_bytes:
        return {"ok": False, "message": "Aucune image source tour"}

    Tour.objects.filter(pk=tour.pk).update(
        thumbnail_status=PipelineStatus.PROCESSING,
        thumbnail_error="",
        updated_at=timezone.now(),
    )

    try:
        base_name = slugify(tour.title) or f"tour-{tour.pk}"

        desktop_content, desktop_size_kb = compress_image(
            _content_file_from_bytes(source_bytes, tour.thumbnail_source.name),
            add_watermark=False,
            max_width=1400,
            max_height=800,
            initial_quality=72,
            min_quality=52,
            target_max_kb=180,
        )
        tour.thumbnail_image.save(f"{base_name}-home.webp", desktop_content, save=False)

        mobile_content, mobile_size_kb = compress_image(
            _content_file_from_bytes(source_bytes, tour.thumbnail_source.name),
            add_watermark=False,
            max_width=900,
            max_height=560,
            initial_quality=66,
            min_quality=46,
            target_max_kb=95,
        )
        tour.thumbnail_image_mobile.save(f"{base_name}-home-mobile.webp", mobile_content, save=False)

        tour.thumbnail_status = PipelineStatus.READY
        tour.thumbnail_error = ""
        tour.thumbnail_generated_at = timezone.now()
        tour.save(
            update_fields=[
                "thumbnail_image",
                "thumbnail_image_mobile",
                "thumbnail_status",
                "thumbnail_error",
                "thumbnail_generated_at",
                "updated_at",
            ]
        )

        return {
            "ok": True,
            "desktop_kb": desktop_size_kb,
            "mobile_kb": mobile_size_kb,
        }

    except Exception as exc:
        Tour.objects.filter(pk=tour.pk).update(
            thumbnail_status=PipelineStatus.FAILED,
            thumbnail_error=str(exc),
            updated_at=timezone.now(),
        )
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def generate_scene_assets_task(self, scene_id):
    scene = Scene360.objects.select_related("organization", "tour").filter(pk=scene_id).first()
    if not scene:
        return {"ok": False, "message": "Scene introuvable"}

    Scene360.objects.filter(pk=scene.pk).update(
        assets_status=PipelineStatus.PROCESSING,
        assets_error="",
        updated_at=timezone.now(),
    )

    try:
        scene.refresh_from_db()
        stats = _generate_scene_assets(scene)
        scene.save(
            update_fields=[
                "image_360_preview",
                "image_360",
                "image_360_mobile",
                "thumbnail_image",
                "assets_status",
                "assets_error",
                "assets_generated_at",
                "updated_at",
            ]
        )
        return {"ok": True, "stats": stats}
    except Exception as exc:
        Scene360.objects.filter(pk=scene.pk).update(
            assets_status=PipelineStatus.FAILED,
            assets_error=str(exc),
            updated_at=timezone.now(),
        )
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def generate_scene_tiles_task(self, scene_id):
    scene = Scene360.objects.select_related("organization", "tour").filter(pk=scene_id).first()
    if not scene:
        return {"ok": False, "message": "Scene introuvable"}

    if not scene.tiles_enabled:
        return {"ok": True, "message": "Tiles désactivées"}

    Scene360.objects.filter(pk=scene.pk).update(
        tiles_status=PipelineStatus.PROCESSING,
        tiles_error="",
        updated_at=timezone.now(),
    )

    try:
        scene.refresh_from_db()
        stats = _generate_scene_tiles(scene)
        scene.save(
            update_fields=[
                "tiles_status",
                "tiles_manifest",
                "tiles_generated_at",
                "tiles_error",
                "updated_at",
            ]
        )
        return {"ok": True, "stats": stats}
    except Exception as exc:
        Scene360.objects.filter(pk=scene.pk).update(
            tiles_status=PipelineStatus.FAILED,
            tiles_error=str(exc),
            updated_at=timezone.now(),
        )
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def analyze_scene_ai_task(self, scene_id):
    scene = Scene360.objects.select_related("organization", "tour").filter(pk=scene_id).first()
    if not scene:
        return {"ok": False, "message": "Scene introuvable"}

    Scene360.objects.filter(pk=scene.pk).update(
        ai_analysis_status=PipelineStatus.PROCESSING,
        ai_analysis_error="",
        updated_at=timezone.now(),
    )

    try:
        analysis = _real_ai_analysis(scene)

        scene.ai_analysis = analysis
        scene.ai_analysis_status = PipelineStatus.READY
        scene.ai_analysis_error = ""
        scene.ai_analyzed_at = timezone.now()
        scene.ai_hotspot_suggestions = analysis.get("recommended_hotspots", [])

        scene.save(
            update_fields=[
                "ai_analysis",
                "ai_analysis_status",
                "ai_analysis_error",
                "ai_analyzed_at",
                "ai_hotspot_suggestions",
                "updated_at",
            ]
        )

        return {"ok": True, "analysis": analysis}
    except Exception as exc:
        Scene360.objects.filter(pk=scene.pk).update(
            ai_analysis_status=PipelineStatus.FAILED,
            ai_analysis_error=str(exc),
            updated_at=timezone.now(),
        )
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def generate_ai_hotspots_task(self, scene_id):
    scene = Scene360.objects.select_related("organization", "tour").filter(pk=scene_id).first()
    if not scene:
        return {"ok": False, "message": "Scene introuvable"}

    Scene360.objects.filter(pk=scene.pk).update(
        ai_hotspots_status=PipelineStatus.PROCESSING,
        ai_hotspot_error="",
        updated_at=timezone.now(),
    )

    try:
        analysis = scene.ai_analysis or _real_ai_analysis(scene)
        created_ids = _generate_ai_hotspots(scene, analysis)

        scene.ai_hotspots_status = PipelineStatus.READY
        scene.ai_hotspot_error = ""
        scene.ai_hotspots_generated_at = timezone.now()
        scene.save(
            update_fields=[
                "ai_hotspots_status",
                "ai_hotspot_error",
                "ai_hotspots_generated_at",
                "updated_at",
            ]
        )

        return {"ok": True, "created_hotspots": created_ids}
    except Exception as exc:
        Scene360.objects.filter(pk=scene.pk).update(
            ai_hotspots_status=PipelineStatus.FAILED,
            ai_hotspot_error=str(exc),
            updated_at=timezone.now(),
        )
        raise


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def build_tour_prefetch_manifest_task(self, tour_id):
    tour = Tour.objects.filter(pk=tour_id).first()
    if not tour:
        return {"ok": False, "message": "Tour introuvable"}

    _build_prefetch_manifest_for_tour(tour)
    return {"ok": True}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def send_tour_published_email_task(self, tour_id):
    tour = Tour.objects.select_related("organization", "place").filter(pk=tour_id).first()
    if not tour:
        return {"ok": False, "message": "Tour introuvable"}

    recipients = []
    if tour.contact_email:
        recipients.append(tour.contact_email)

    recipients = list(dict.fromkeys([email for email in recipients if email]))

    if not recipients:
        Tour.objects.filter(pk=tour.pk).update(
            publish_email_status=DeliveryStatus.FAILED,
            publish_email_error="Aucun destinataire email trouvé.",
            updated_at=timezone.now(),
        )
        return {"ok": False, "message": "No recipients"}

    subject = f"Votre visite virtuelle est publiée : {tour.title}"
    body = (
        f"Bonjour,\n\n"
        f"Votre visite virtuelle « {tour.title} » est maintenant publiée.\n"
        f"Lieu : {tour.place}\n"
        f"Description : {tour.description or '—'}\n\n"
        f"Cordialement,\n"
        f"L'équipe"
    )

    sent_count = 0

    for recipient in recipients:
        log = TourEmailLog.objects.create(
            tour=tour,
            recipient=recipient,
            subject=subject,
            body=body,
            status=DeliveryStatus.PENDING,
        )

        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[recipient],
                fail_silently=False,
            )

            log.status = DeliveryStatus.SENT
            log.error = ""
            log.provider_response = {"provider": "django_send_mail"}
            log.save(update_fields=["status", "error", "provider_response", "updated_at"])

            sent_count += 1

        except Exception as exc:
            log.status = DeliveryStatus.FAILED
            log.error = str(exc)
            log.save(update_fields=["status", "error", "updated_at"])

    if sent_count > 0:
        Tour.objects.filter(pk=tour.pk).update(
            publish_email_status=DeliveryStatus.SENT,
            publish_email_error="",
            updated_at=timezone.now(),
        )
    else:
        Tour.objects.filter(pk=tour.pk).update(
            publish_email_status=DeliveryStatus.FAILED,
            publish_email_error="Échec d'envoi des emails.",
            updated_at=timezone.now(),
        )

    return {"ok": sent_count > 0, "sent_count": sent_count}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def run_scene_pipeline_task(self, scene_id):
    """
    Pipeline complet d'une scène.

    Cette version exécute vraiment les étapes dans l'ordre :
    1. génération preview/mobile/desktop/thumbnail
    2. génération tiles si activées
    3. analyse IA
    4. génération hotspots IA
    5. prefetch manifest du tour

    Avantage :
    - plus de sous-tâches perdues ;
    - plus de problème d'ordre ;
    - le statut change correctement ;
    - les fichiers sont réellement créés quand cette tâche démarre.
    """

    scene = (
        Scene360.objects
        .select_related("organization", "tour")
        .filter(pk=scene_id)
        .first()
    )

    if not scene:
        return {
            "ok": False,
            "message": "Scene introuvable",
            "scene_id": scene_id,
        }

    if not scene.image_360_original:
        Scene360.objects.filter(pk=scene.pk).update(
            assets_status=PipelineStatus.FAILED,
            assets_error="Aucune image source trouvée pour la scène.",
            tiles_status=PipelineStatus.FAILED if scene.tiles_enabled else PipelineStatus.NONE,
            tiles_error="Aucune image source trouvée pour générer les tiles." if scene.tiles_enabled else "",
            ai_analysis_status=PipelineStatus.FAILED,
            ai_analysis_error="Pipeline arrêté : aucune image source.",
            ai_hotspots_status=PipelineStatus.FAILED,
            ai_hotspot_error="Pipeline arrêté : aucune image source.",
            updated_at=timezone.now(),
        )

        return {
            "ok": False,
            "message": "Aucune image source trouvée pour la scène.",
            "scene_id": scene.pk,
        }

    result = {
        "ok": True,
        "scene_id": scene.pk,
        "tour_id": scene.tour_id,
        "assets": None,
        "tiles": None,
        "ai_analysis": None,
        "ai_hotspots": None,
        "prefetch": None,
    }

    # ============================================================
    # 1. ASSETS : preview + desktop + mobile + thumbnail
    # ============================================================
    Scene360.objects.filter(pk=scene.pk).update(
        assets_status=PipelineStatus.PROCESSING,
        assets_error="",
        updated_at=timezone.now(),
    )

    try:
        scene.refresh_from_db()
        assets_stats = _generate_scene_assets(scene)

        scene.save(
            update_fields=[
                "image_360_preview",
                "image_360",
                "image_360_mobile",
                "thumbnail_image",
                "assets_status",
                "assets_error",
                "assets_generated_at",
                "updated_at",
            ]
        )

        result["assets"] = {
            "ok": True,
            "stats": assets_stats,
        }

    except Exception as exc:
        Scene360.objects.filter(pk=scene.pk).update(
            assets_status=PipelineStatus.FAILED,
            assets_error=str(exc),
            updated_at=timezone.now(),
        )
        raise

    # ============================================================
    # 2. TILES
    # ============================================================
    scene.refresh_from_db()

    if scene.tiles_enabled:
        Scene360.objects.filter(pk=scene.pk).update(
            tiles_status=PipelineStatus.PROCESSING,
            tiles_error="",
            updated_at=timezone.now(),
        )

        try:
            scene.refresh_from_db()
            tiles_stats = _generate_scene_tiles(scene)

            scene.save(
                update_fields=[
                    "tiles_status",
                    "tiles_manifest",
                    "tiles_generated_at",
                    "tiles_error",
                    "updated_at",
                ]
            )

            result["tiles"] = {
                "ok": True,
                "stats": tiles_stats,
            }

        except Exception as exc:
            Scene360.objects.filter(pk=scene.pk).update(
                tiles_status=PipelineStatus.FAILED,
                tiles_error=str(exc),
                updated_at=timezone.now(),
            )
            raise

    else:
        Scene360.objects.filter(pk=scene.pk).update(
            tiles_status=PipelineStatus.NONE,
            tiles_error="",
            updated_at=timezone.now(),
        )

        result["tiles"] = {
            "ok": True,
            "message": "Tiles désactivées",
        }

    # ============================================================
    # 3. ANALYSE IA
    # ============================================================
    Scene360.objects.filter(pk=scene.pk).update(
        ai_analysis_status=PipelineStatus.PROCESSING,
        ai_analysis_error="",
        updated_at=timezone.now(),
    )

    try:
        scene.refresh_from_db()
        analysis = _real_ai_analysis(scene)

        scene.ai_analysis = analysis
        scene.ai_analysis_status = PipelineStatus.READY
        scene.ai_analysis_error = ""
        scene.ai_analyzed_at = timezone.now()
        scene.ai_hotspot_suggestions = analysis.get("recommended_hotspots", [])

        scene.save(
            update_fields=[
                "ai_analysis",
                "ai_analysis_status",
                "ai_analysis_error",
                "ai_analyzed_at",
                "ai_hotspot_suggestions",
                "updated_at",
            ]
        )

        result["ai_analysis"] = {
            "ok": True,
            "analysis": analysis,
        }

    except Exception as exc:
        Scene360.objects.filter(pk=scene.pk).update(
            ai_analysis_status=PipelineStatus.FAILED,
            ai_analysis_error=str(exc),
            updated_at=timezone.now(),
        )
        raise

    # ============================================================
    # 4. HOTSPOTS IA
    # ============================================================
    Scene360.objects.filter(pk=scene.pk).update(
        ai_hotspots_status=PipelineStatus.PROCESSING,
        ai_hotspot_error="",
        updated_at=timezone.now(),
    )

    try:
        scene.refresh_from_db()
        analysis = scene.ai_analysis or _real_ai_analysis(scene)
        created_ids = _generate_ai_hotspots(scene, analysis)

        scene.ai_hotspots_status = PipelineStatus.READY
        scene.ai_hotspot_error = ""
        scene.ai_hotspots_generated_at = timezone.now()

        scene.save(
            update_fields=[
                "ai_hotspots_status",
                "ai_hotspot_error",
                "ai_hotspots_generated_at",
                "updated_at",
            ]
        )

        result["ai_hotspots"] = {
            "ok": True,
            "created_hotspots": created_ids,
        }

    except Exception as exc:
        Scene360.objects.filter(pk=scene.pk).update(
            ai_hotspots_status=PipelineStatus.FAILED,
            ai_hotspot_error=str(exc),
            updated_at=timezone.now(),
        )
        raise

    # ============================================================
    # 5. PREFETCH TOUR
    # ============================================================
    try:
        tour = Tour.objects.filter(pk=scene.tour_id).first()

        if tour:
            _build_prefetch_manifest_for_tour(tour)
            result["prefetch"] = {
                "ok": True,
                "tour_id": tour.id,
            }
        else:
            result["prefetch"] = {
                "ok": False,
                "message": "Tour introuvable",
            }

    except Exception as exc:
        result["prefetch"] = {
            "ok": False,
            "error": str(exc),
        }
        raise

    return result