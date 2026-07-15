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


    def list_photos(self, page_size: int = 50, page_token: str = "", view: str = "INCLUDE_DOWNLOAD_URL") -> Dict:
        """List photos that belong to the connected Google account.

        Street View Publish API returns recently indexed photos only; just-created
        photos can be absent for a short time, so the frontend also merges local
        StreetViewSourceSceneState records when available.
        """
        try:
            page_size = int(page_size)
        except (TypeError, ValueError):
            page_size = 50
        page_size = max(1, min(page_size, 100))
        params = {"pageSize": page_size, "view": view or "INCLUDE_DOWNLOAD_URL"}
        if page_token:
            params["pageToken"] = page_token
        response = self.session.get(
            self._url("/v1/photos"),
            params=params,
            headers=self.auth_headers,
            timeout=self.timeout,
        )
        self._raise_for_response(response, "Impossible de récupérer les photos publiées Street View")
        return response.json()

    def list_all_photos(self, *, page_size: int = 100, max_pages: int = 20, view: str = "INCLUDE_DOWNLOAD_URL") -> Dict:
        photos = []
        next_token = ""
        pages = 0
        while pages < max_pages:
            data = self.list_photos(page_size=page_size, page_token=next_token, view=view)
            photos.extend(data.get("photos") or [])
            next_token = data.get("nextPageToken") or ""
            pages += 1
            if not next_token:
                break
        return {"photos": photos, "nextPageToken": next_token, "pages": pages}


    def list_photo_sequences(self, page_size: int = 100, page_token: str = "", filter_expr: str = "") -> Dict:
        """List photo sequences that belong to the connected Google account.

        Street View Studio/video uploads can appear as photo sequences. This
        complements photos.list, which returns individual photo resources.
        """
        try:
            page_size = int(page_size)
        except (TypeError, ValueError):
            page_size = 100
        page_size = max(1, min(page_size, 100))
        params = {"pageSize": page_size}
        if page_token:
            params["pageToken"] = page_token
        if filter_expr:
            params["filter"] = filter_expr
        response = self.session.get(
            self._url("/v1/photoSequences"),
            params=params,
            headers=self.auth_headers,
            timeout=self.timeout,
        )
        self._raise_for_response(response, "Impossible de récupérer les séquences Street View")
        return response.json()

    def list_all_photo_sequences(self, *, page_size: int = 100, max_pages: int = 20, filter_expr: str = "") -> Dict:
        sequences = []
        next_token = ""
        pages = 0
        while pages < max_pages:
            data = self.list_photo_sequences(page_size=page_size, page_token=next_token, filter_expr=filter_expr)
            sequences.extend(data.get("photoSequences") or data.get("photo_sequences") or [])
            next_token = data.get("nextPageToken") or data.get("next_page_token") or ""
            pages += 1
            if not next_token:
                break
        return {"photoSequences": sequences, "nextPageToken": next_token, "pages": pages}

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
