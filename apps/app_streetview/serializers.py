from django.utils import timezone


def scene_to_dict(scene, absolute_url_builder=None):
    image_url = scene.image.url if scene.image else ""
    if absolute_url_builder and image_url:
        image_url = absolute_url_builder(image_url)

    return {
        "id": scene.id,
        "tour_id": scene.tour_id,
        "title": scene.title,
        "description": scene.description,
        "image_url": image_url,
        "image_width": scene.image_width,
        "image_height": scene.image_height,
        "file_size": scene.file_size,
        "gps": {
            "latitude": float(scene.latitude) if scene.latitude is not None else None,
            "longitude": float(scene.longitude) if scene.longitude is not None else None,
            "altitude": scene.altitude,
        },
        "orientation": {
            "heading": scene.heading,
            "pitch": scene.pitch,
            "roll": scene.roll,
            "initial_yaw": scene.initial_yaw,
            "initial_pitch": scene.initial_pitch,
            "initial_fov": scene.initial_fov,
        },
        "capture_time": scene.capture_time.isoformat() if scene.capture_time else None,
        "xmp_detected": scene.xmp_detected,
        "is_full_360_ratio": scene.is_full_360_ratio,
        "google": {
            "photo_id": scene.google_photo_id,
            "share_link": scene.google_share_link,
            "thumbnail_url": scene.google_thumbnail_url,
            "publish_status": scene.publish_status,
            "last_error": scene.last_error,
            "is_published": bool(scene.google_photo_id),
            "is_connected": scene.publish_status == "connected",
            "share_ready": bool(scene.google_share_link or scene.google_photo_id),
            "maps_publish_status": scene.google_maps_publish_status,
            "transfer_status": scene.google_transfer_status,
            "view_count": scene.google_view_count,
            "last_synced_at": scene.google_last_synced_at.isoformat() if scene.google_last_synced_at else None,
            "connection_sync_status": scene.connection_sync_status,
            "connection_audit": scene.connection_audit,
            "status_payload": scene.google_status_payload,
            "remote_only": scene.remote_only,
        },
        "order": scene.order,
        "created_at": scene.created_at.isoformat() if scene.created_at else None,
        "updated_at": scene.updated_at.isoformat() if scene.updated_at else None,
    }


def connection_to_dict(connection):
    return {
        "id": connection.id,
        "from_scene": connection.from_scene_id,
        "to_scene": connection.to_scene_id,
        "yaw": connection.yaw,
        "pitch": connection.pitch,
        "label": connection.label,
        "order": connection.order,
    }


def hotspot_to_dict(hotspot):
    return {
        "id": hotspot.id,
        "scene": hotspot.scene_id,
        "type": hotspot.type,
        "title": hotspot.title,
        "description": hotspot.description,
        "target_scene": hotspot.target_scene_id,
        "url": hotspot.url,
        "yaw": hotspot.yaw,
        "pitch": hotspot.pitch,
        "icon": hotspot.icon,
        "css_class": hotspot.css_class,
        "order": hotspot.order,
    }


def tour_to_dict(tour, absolute_url_builder=None, include_children=True):
    data = {
        "id": tour.id,
        "public_id": str(tour.public_id),
        "title": tour.title,
        "description": tour.description,
        "project_mode": tour.project_mode,
        "storage_policy": tour.storage_policy,
        "google_place_id": tour.google_place_id,
        "auto_connect": tour.auto_connect,
        "auto_sync_status": tour.auto_sync_status,
        "status": tour.status,
        "last_error": tour.last_error,
        "published_at": tour.published_at.isoformat() if tour.published_at else None,
        "created_at": tour.created_at.isoformat() if tour.created_at else None,
        "updated_at": tour.updated_at.isoformat() if tour.updated_at else None,
    }
    if include_children:
        data["scenes"] = [scene_to_dict(scene, absolute_url_builder) for scene in tour.scenes.all()]
        data["connections"] = [connection_to_dict(conn) for conn in tour.connections.all()]
        data["hotspots"] = [hotspot_to_dict(h) for scene in tour.scenes.all() for h in scene.hotspots.all()]
    return data


def publish_job_to_dict(job):
    return {
        "id": job.id,
        "public_id": str(job.public_id),
        "tour_id": job.tour_id,
        "status": job.status,
        "total_scenes": job.total_scenes,
        "published_scenes": job.published_scenes,
        "failed_scenes": job.failed_scenes,
        "log": job.log,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
