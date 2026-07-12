# Street View — suppression d'une photo publiée

Cette version ajoute la suppression propre d'une image déjà publiée sur Google Street View.

## Important

Google Street View Publish API ne publie pas les hotspots Marzipano personnalisés sur Google Maps.
Google reçoit seulement :

- les photos 360 ;
- le GPS / la caméra ;
- les connexions entre photos ;
- l'association éventuelle à un place.

Les hotspots d'information restent donc dans la visite web Marzipano de l'application.

## Nouveau endpoint

```text
POST /apis/streetview/source/scenes/<source_scene_id>/delete-google-photo/
```

Body optionnel :

```json
{
  "delete_from_google": true,
  "clear_local_if_missing": true
}
```

Effet :

1. Supprime la photo côté Google avec `DELETE /v1/photo/{photoId}`.
2. Vide `google_photo_id`, `google_share_link`, `google_thumbnail_url`, `upload_reference_url` dans `StreetViewSourceSceneState`.
3. Ne touche pas à `Scene360` ni à l'image originale du tour.
4. Nettoie les connexions Google restantes pour enlever les liens vers la photo supprimée.

## Frontend

Dans le panneau de préparation de la scène, un bouton apparaît :

```text
Effacer de Google
```

Il est actif uniquement si la scène possède déjà un `google.photo_id`.
