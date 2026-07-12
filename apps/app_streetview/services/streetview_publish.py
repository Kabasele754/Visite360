from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Dict, Iterable
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

import requests

from .orientation import normalize_heading, normalize_pitch, normalize_roll


STREETVIEW_BASE_URL = "https://streetviewpublish.googleapis.com"


class StreetViewPublishError(Exception):
    def __init__(self, message, *, status_code=None, response_text="", payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text
        self.payload = payload or {}


class StreetViewPublishClient:
    """Thin REST client for Google Street View Publish API.

    Correct flow for photos:
    1. POST /v1/photo:startUpload with an empty body.
    2. POST binary photo bytes to the returned uploadUrl with Authorization header.
    3. POST /v1/photo with uploadReference + pose metadata.
    4. PUT /v1/photo/{photoId}?updateMask=connections after all photos exist.
    """

    def __init__(self, access_token: str, timeout: int = 120, api_key: str | None = None):
        self.access_token = access_token
        self.timeout = timeout
        self.api_key = api_key or ""
        self.session = requests.Session()

    @property
    def auth_headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    def _url(self, path: str) -> str:
        url = f"{STREETVIEW_BASE_URL}{path}"
        if not self.api_key:
            return url
        return self._append_query(url, {"key": self.api_key})

    @staticmethod
    def _append_query(url: str, params: dict) -> str:
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query.update({k: v for k, v in params.items() if v})
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    @staticmethod
    def _safe_response_text(response: requests.Response, limit: int = 1200) -> str:
        text = response.text or ""
        text = " ".join(text.split())
        return text[:limit] + ("..." if len(text) > limit else "")

    def _raise_for_response(self, response: requests.Response, message: str):
        if response.ok:
            return
        try:
            payload = response.json()
        except Exception:
            payload = {}
        detail = payload.get("error", {}).get("message") or self._safe_response_text(response)
        raise StreetViewPublishError(
            f"{message}: {detail}",
            status_code=response.status_code,
            response_text=response.text,
            payload=payload,
        )

    def start_upload(self) -> str:
        response = self.session.post(
            self._url("/v1/photo:startUpload"),
            headers={**self.auth_headers, "Content-Length": "0"},
            timeout=self.timeout,
        )
        self._raise_for_response(response, "Impossible de créer la session d'upload Street View")
        data = response.json()
        upload_url = data.get("uploadUrl")
        if not upload_url:
            raise StreetViewPublishError("Google n'a pas retourné uploadUrl.", payload=data)
        return upload_url

    def upload_photo_bytes(self, upload_url: str, image_path: str) -> None:
        """Upload raw photo bytes to Google's uploadUrl.

        Google's Street View Publish guide uses POST + --upload-file + Authorization.
        The old implementation used PUT without Authorization, which can return a
        generic Google 400 HTML page.
        """
        image_path_obj = Path(image_path)
        if not image_path_obj.exists():
            raise StreetViewPublishError(f"Fichier introuvable: {image_path_obj}")

        content_type = mimetypes.guess_type(image_path_obj.name)[0] or "image/jpeg"
        file_size = image_path_obj.stat().st_size

        headers = {
            **self.auth_headers,
            "Content-Type": content_type,
            "Content-Length": str(file_size),
        }

        # Main method from Google's documentation: POST binary bytes to uploadUrl.
        with open(image_path_obj, "rb") as fh:
            response = self.session.post(
                upload_url,
                data=fh,
                headers=headers,
                timeout=self.timeout,
            )

        # Some upload endpoints may still accept PUT. Try only as a fallback.
        if response.status_code in (405, 501):
            with open(image_path_obj, "rb") as fh:
                response = self.session.put(
                    upload_url,
                    data=fh,
                    headers=headers,
                    timeout=self.timeout,
                )

        self._raise_for_response(response, "Impossible d'envoyer les octets de l'image vers Street View")

    def create_photo(self, upload_url: str, scene) -> Dict:
        if scene.latitude is None or scene.longitude is None:
            raise StreetViewPublishError(f"La scène {scene.title} n'a pas de coordonnées GPS.")

        payload = {
            "uploadReference": {"uploadUrl": upload_url},
            "pose": {
                "latLngPair": {
                    "latitude": float(scene.latitude),
                    "longitude": float(scene.longitude),
                },
                # Keep heading here for metadata clarity. Google may ignore heading/pitch/roll
                # on create unless Photo Sphere XMP metadata exists in the image bytes.
                "heading": normalize_heading(getattr(scene, "heading", 0)),
            },
        }

        if scene.altitude is not None:
            payload["pose"]["altitude"] = float(scene.altitude)

        if scene.capture_time:
            payload["captureTime"] = {"seconds": int(scene.capture_time.timestamp())}

        response = self.session.post(
            self._url("/v1/photo"),
            json=payload,
            headers={**self.auth_headers, "Content-Type": "application/json"},
            timeout=self.timeout,
        )
        self._raise_for_response(response, "Impossible de créer la photo Street View")
        return response.json()

    def get_photo(self, photo_id: str, view: str = "BASIC") -> Dict:
        response = self.session.get(
            self._url(f"/v1/photo/{photo_id}"),
            params={"view": view},
            headers=self.auth_headers,
            timeout=self.timeout,
        )
        self._raise_for_response(response, "Impossible de récupérer la photo Street View")
        return response.json()

    def update_photo_connections(self, photo_id: str, target_photo_ids: Iterable[str]) -> Dict:
        connections = [
            {"target": {"id": target_id}}
            for target_id in target_photo_ids
            if target_id
        ]
        payload = {
            "photoId": {"id": photo_id},
            "connections": connections,
        }
        response = self.session.put(
            self._url(f"/v1/photo/{photo_id}"),
            params={"updateMask": "connections"},
            json=payload,
            headers={**self.auth_headers, "Content-Type": "application/json"},
            timeout=self.timeout,
        )
        self._raise_for_response(response, "Impossible de mettre à jour les connexions Street View")
        return response.json()

    def update_photo_pose(self, photo_id: str, scene) -> Dict:
        payload = {
            "photoId": {"id": photo_id},
            "pose": {
                "latLngPair": {
                    "latitude": float(scene.latitude),
                    "longitude": float(scene.longitude),
                },
                "heading": normalize_heading(getattr(scene, "heading", 0)),
                "pitch": float(scene.pitch or 0),
                "roll": float(scene.roll or 0),
            },
        }
        if scene.altitude is not None:
            payload["pose"]["altitude"] = float(scene.altitude)

        response = self.session.put(
            self._url(f"/v1/photo/{photo_id}"),
            params={"updateMask": "pose.latLngPair,pose.heading,pose.pitch,pose.roll,pose.altitude"},
            json=payload,
            headers={**self.auth_headers, "Content-Type": "application/json"},
            timeout=self.timeout,
        )
        self._raise_for_response(response, "Impossible de mettre à jour la pose Street View")
        return response.json()

    def delete_photo(self, photo_id: str) -> None:
        response = self.session.delete(
            self._url(f"/v1/photo/{photo_id}"),
            headers=self.auth_headers,
            timeout=self.timeout,
        )
        self._raise_for_response(response, "Impossible de supprimer la photo Street View")


def extract_google_photo_fields(created_payload: Dict) -> Dict[str, str]:
    photo_id = (created_payload.get("photoId") or {}).get("id") or created_payload.get("photoId", {}).get("photo_id")
    return {
        "photo_id": photo_id or "",
        "share_link": created_payload.get("shareLink") or "",
        "thumbnail_url": created_payload.get("thumbnailUrl") or "",
    }
