import os

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from .models import Tour, Scene360, Hotspot


def generate_unique_tour_slug(title: str, model=Tour) -> str:
    """
    Génère un slug unique pour un Tour à partir du titre.
    """
    base_slug = slugify(title) or "untitled-tour"
    slug = base_slug
    counter = 1

    while model.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def generate_scene_id(tour: Tour, title: str) -> str:
    """
    Génère un scene_id unique pour une scène.
    Exemple: 'living-room', 'living-room-1', etc.
    """
    base = slugify(title) or "scene"
    scene_id = base
    counter = 1

    while Scene360.objects.filter(scene_id=scene_id).exists():
        scene_id = f"{base}-{counter}"
        counter += 1

    return scene_id


def generate_hotspot_id(scene: Scene360) -> str:
    """
    Génère un hotspot_id simple et unique dans le contexte de la scène.
    """
    base = f"hs-{scene.id}"
    counter = scene.hotspots.count() + 1
    hotspot_id = f"{base}-{counter}"

    while Hotspot.objects.filter(hotspot_id=hotspot_id).exists():
        counter += 1
        hotspot_id = f"{base}-{counter}"

    return hotspot_id


def model_has_field(model_class, field_name: str) -> bool:
    """
    Vérifie si un champ existe dans le modèle.
    Utile pour garder le service compatible si is_public/status existe ou non.
    """
    try:
        model_class._meta.get_field(field_name)
        return True
    except Exception:
        return False


def get_file_url(file_field):
    """
    Retourne l'URL d'un FileField/ImageField si disponible.
    """
    try:
        if file_field:
            return file_field.url
    except Exception:
        return None
    return None


def build_tour_manifest(tour: Tour) -> dict:
    """
    Reconstruit le manifest JSON du tour à partir des scènes et hotspots.
    C'est ce manifest qui sera utilisé par le builder ou le preview.
    """
    scenes_data = []
    ordered_scenes = (
        tour.scenes.prefetch_related("hotspots")
        .all()
        .order_by("order", "id")
    )

    initial_scene_id = None
    has_is_public = model_has_field(Scene360, "is_public")

    for index, scene in enumerate(ordered_scenes):
        if index == 0:
            initial_scene_id = scene.id

        image_360_original_url = get_file_url(getattr(scene, "image_360_original", None))
        image_360_url = get_file_url(getattr(scene, "image_360", None))
        image_360_mobile_url = get_file_url(getattr(scene, "image_360_mobile", None))
        image_360_preview_url = get_file_url(getattr(scene, "image_360_preview", None))
        thumbnail_url = get_file_url(getattr(scene, "thumbnail_image", None))

        scene_payload = {
            "id": scene.id,
            "scene_id": scene.scene_id,
            "title": scene.title,

            # Ancien champ gardé pour compatibilité.
            "image_url": image_360_url or image_360_original_url,

            # Nouveaux champs utiles pour preview/mobile/Celery.
            "image_360_original_url": image_360_original_url,
            "image_360_url": image_360_url,
            "image_360_mobile_url": image_360_mobile_url,
            "image_360_preview_url": image_360_preview_url,
            "thumbnail_url": thumbnail_url,

            "yaw_default": scene.yaw_default,
            "pitch_default": scene.pitch_default,
            "hfov_default": scene.hfov_default,
            "tripod_logo": {
                "enabled": bool(getattr(scene, "tripod_logo_enabled", False)),
                "size": int(getattr(scene, "tripod_logo_size", 132) or 132),
                "yaw": float(getattr(scene, "tripod_logo_yaw", 0.0) or 0.0),
                "pitch": float(88.5 if getattr(scene, "tripod_logo_pitch", None) is None else scene.tripod_logo_pitch),
                "offset_x": int(getattr(scene, "tripod_logo_offset_x", 0) or 0),
                "offset_y": int(getattr(scene, "tripod_logo_offset_y", 0) or 0),
                "rotation": float(getattr(scene, "tripod_logo_rotation", 0.0) or 0.0),
                "tilt_x": float(getattr(scene, "tripod_logo_tilt_x", 0.0) or 0.0),
                "tilt_y": float(getattr(scene, "tripod_logo_tilt_y", 0.0) or 0.0),
                "radius": int(getattr(scene, "tripod_logo_radius", 900) or 900),
            },

            "hotspots": [
                {
                    "id": hotspot.id,
                    "hotspot_id": hotspot.hotspot_id,
                    "type": hotspot.type,
                    "label": hotspot.label,
                    "tooltip_text": hotspot.tooltip_text,
                    "yaw": hotspot.yaw,
                    "pitch": hotspot.pitch,
                    "target_scene": hotspot.target_scene_id,
                    "title": hotspot.title,
                    "description": hotspot.description,
                    "selected_icon": hotspot.selected_icon,
                    "ad_image_url": hotspot.ad_image.url if hotspot.ad_image else None,
                    "payload": hotspot.payload,
                }
                for hotspot in scene.hotspots.all()
            ],
        }

        if has_is_public:
            scene_payload["is_public"] = scene.is_public

        scenes_data.append(scene_payload)

    manifest = {
        "tour_id": tour.id,
        "slug": tour.slug,
        "title": tour.title,
        "initial_scene": initial_scene_id,
        "scenes": scenes_data,
    }

    tour.manifest = manifest
    tour.save(update_fields=["manifest", "updated_at"])
    return manifest


@transaction.atomic
def handle_uploaded_scenes(tour: Tour, files, is_public=True):
    """
    Crée plusieurs Scene360 à partir d'un upload multiple de fichiers.

    Très important :
    - L'image uploadée doit être enregistrée dans image_360_original.
    - Celery utilise image_360_original comme image source.
    - image_360, image_360_mobile, image_360_preview et thumbnail_image
      seront générés ensuite par la task Celery.
    """
    created_scenes = []

    max_order = (
        tour.scenes.order_by("-order")
        .values_list("order", flat=True)
        .first()
        or 0
    )
    start_order = max_order + 1

    has_is_public = model_has_field(Scene360, "is_public")
    has_status = model_has_field(Scene360, "status")

    for index, uploaded_file in enumerate(files):
        filename = os.path.splitext(uploaded_file.name)[0]
        title = filename.replace("_", " ").replace("-", " ").strip()

        if not title:
            title = f"Scene {start_order + index}"

        try:
            uploaded_file.seek(0)
        except Exception:
            pass

        scene_kwargs = {
            "organization": tour.organization,
            "tour": tour,
            "scene_id": generate_scene_id(tour, title),
            "title": title,
            "order": start_order + index,
        }

        if has_is_public:
            scene_kwargs["is_public"] = bool(is_public)

        if has_status and hasattr(Scene360, "Status"):
            scene_kwargs["status"] = Scene360.Status.DRAFT

        scene = Scene360(**scene_kwargs)

        # Correction principale :
        # avant tu faisais image_360=uploaded_file.
        # Maintenant on garde l'image source originale ici.
        scene.image_360_original.save(
            uploaded_file.name,
            uploaded_file,
            save=False,
        )

        scene.save()
        created_scenes.append(scene)

    build_tour_manifest(tour)
    return created_scenes


def reorder_scenes_for_tour(tour: Tour, ordered_scene_ids: list[int]):
    """
    Réorganise proprement les scènes d'un tour selon l'ordre reçu.
    """
    scenes = list(
        tour.scenes.all().order_by("order", "id")
    )
    existing_ids = {scene.id for scene in scenes}

    cleaned_ids = [
        int(scene_id)
        for scene_id in ordered_scene_ids
        if int(scene_id) in existing_ids
    ]

    remaining_ids = [scene.id for scene in scenes if scene.id not in cleaned_ids]
    final_ids = cleaned_ids + remaining_ids

    id_to_scene = {scene.id: scene for scene in scenes}

    for index, scene_id in enumerate(final_ids, start=1):
        scene = id_to_scene[scene_id]
        if scene.order != index:
            scene.order = index
            scene.save(update_fields=["order", "updated_at"])

    build_tour_manifest(tour)
    return list(tour.scenes.all().order_by("order", "id"))


def create_hotspot(
    scene: Scene360,
    *,
    hotspot_type: str,
    label: str,
    yaw: float,
    pitch: float,
    target_scene=None,
    tooltip_text="",
    title="",
    description="",
    selected_icon="",
    payload=None,
):
    """
    Crée un hotspot dans une scène donnée et reconstruit le manifest.
    """
    payload = payload or {}

    hotspot = Hotspot.objects.create(
        organization=scene.organization,
        scene=scene,
        hotspot_id=generate_hotspot_id(scene),
        type=hotspot_type,
        label=label,
        yaw=yaw,
        pitch=pitch,
        target_scene=target_scene,
        tooltip_text=tooltip_text,
        title=title,
        description=description,
        selected_icon=selected_icon,
        payload=payload,
    )

    build_tour_manifest(scene.tour)
    return hotspot


def update_hotspot(
    hotspot: Hotspot,
    *,
    hotspot_type=None,
    label=None,
    yaw=None,
    pitch=None,
    target_scene=None,
    tooltip_text=None,
    title=None,
    description=None,
    selected_icon=None,
    payload=None,
):
    """
    Met à jour un hotspot existant et reconstruit le manifest.
    """
    if hotspot_type is not None:
        hotspot.type = hotspot_type

    if label is not None:
        hotspot.label = label

    if yaw is not None:
        hotspot.yaw = yaw

    if pitch is not None:
        hotspot.pitch = pitch

    hotspot.target_scene = target_scene

    if tooltip_text is not None:
        hotspot.tooltip_text = tooltip_text

    if title is not None:
        hotspot.title = title

    if description is not None:
        hotspot.description = description

    if selected_icon is not None:
        hotspot.selected_icon = selected_icon

    if payload is not None:
        hotspot.payload = payload

    hotspot.save()
    build_tour_manifest(hotspot.scene.tour)
    return hotspot


def update_scene_properties(
    scene: Scene360,
    *,
    title=None,
    yaw_default=None,
    pitch_default=None,
    hfov_default=None,
    order=None,
    is_public=None,
):
    """
    Met à jour les propriétés principales d'une scène.
    """
    update_fields = []

    if title is not None:
        scene.title = title
        update_fields.append("title")

    if yaw_default is not None:
        scene.yaw_default = yaw_default
        update_fields.append("yaw_default")

    if pitch_default is not None:
        scene.pitch_default = pitch_default
        update_fields.append("pitch_default")

    if hfov_default is not None:
        scene.hfov_default = hfov_default
        update_fields.append("hfov_default")

    if order is not None:
        scene.order = order
        update_fields.append("order")

    if is_public is not None and model_has_field(Scene360, "is_public"):
        scene.is_public = bool(is_public)
        update_fields.append("is_public")

    if update_fields:
        update_fields.append("updated_at")
        scene.save(update_fields=update_fields)
        build_tour_manifest(scene.tour)

    return scene


def delete_hotspot_and_rebuild(hotspot: Hotspot):
    """
    Supprime un hotspot et reconstruit le manifest du tour.
    """
    tour = hotspot.scene.tour
    hotspot.delete()
    build_tour_manifest(tour)
    return True


def publish_tour(tour: Tour) -> Tour:
    """
    Publie un tour.
    """
    tour.status = Tour.Status.PUBLISHED
    tour.version = (tour.version or 0) + 1
    build_tour_manifest(tour)
    tour.save(update_fields=["status", "version", "manifest", "updated_at"])
    return tour


def unpublish_tour(tour: Tour) -> Tour:
    """
    Passe le tour en inactive.
    """
    tour.status = Tour.Status.INACTIVE
    tour.save(update_fields=["status", "updated_at"])
    return tour


def increment_tour_views(tour: Tour) -> Tour:
    """
    Incrémente le compteur de vues d'un tour.
    """
    tour.view_count += 1
    tour.save(update_fields=["view_count", "updated_at"])
    return tour


def prepare_tour_before_create(validated_data: dict) -> dict:
    """
    Prépare les données avant la création d'un tour.
    Génère le slug si nécessaire.
    """
    if not validated_data.get("slug") and validated_data.get("title"):
        validated_data["slug"] = generate_unique_tour_slug(validated_data["title"])
    return validated_data


def create_default_tour_for_place(place, title="Untitled Tour") -> Tour:
    """
    Crée un tour draft par défaut pour un Place.
    """
    tour = Tour.objects.create(
        organization=place.organization,
        place=place,
        title=title,
        slug=generate_unique_tour_slug(title),
        description="",
        status=Tour.Status.DRAFT,
    )
    return tour