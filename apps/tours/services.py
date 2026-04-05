import os
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

    for index, scene in enumerate(ordered_scenes):
        if index == 0:
            initial_scene_id = scene.id

        scenes_data.append({
            "id": scene.id,
            "scene_id": scene.scene_id,
            "title": scene.title,
            "image_url": scene.image_360.url if scene.image_360 else None,
            "thumbnail_url": scene.thumbnail_image.url if scene.thumbnail_image else None,
            "yaw_default": scene.yaw_default,
            "pitch_default": scene.pitch_default,
            "hfov_default": scene.hfov_default,
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
        })

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


def handle_uploaded_scenes(tour: Tour, files):
    """
    Crée plusieurs Scene360 à partir d'un upload multiple de fichiers.
    Le nom de fichier sert de base pour le titre.
    """
    created_scenes = []

    max_order = (
        tour.scenes.order_by("-order")
        .values_list("order", flat=True)
        .first()
        or 0
    )
    start_order = max_order + 1

    for index, uploaded_file in enumerate(files):
        filename = os.path.splitext(uploaded_file.name)[0]
        title = filename.replace("_", " ").replace("-", " ").strip()
        if not title:
            title = f"Scene {start_order + index}"

        scene = Scene360.objects.create(
            organization=tour.organization,
            tour=tour,
            scene_id=generate_scene_id(tour, title),
            title=title,
            image_360=uploaded_file,
            order=start_order + index,
        )
        created_scenes.append(scene)

    build_tour_manifest(tour)
    return created_scenes


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


def update_scene_properties(
    scene: Scene360,
    *,
    title=None,
    yaw_default=None,
    pitch_default=None,
    hfov_default=None,
    order=None,
):
    """
    Met à jour les propriétés principales d'une scène.
    """
    if title is not None:
        scene.title = title

    if yaw_default is not None:
        scene.yaw_default = yaw_default

    if pitch_default is not None:
        scene.pitch_default = pitch_default

    if hfov_default is not None:
        scene.hfov_default = hfov_default

    if order is not None:
        scene.order = order

    scene.save()
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