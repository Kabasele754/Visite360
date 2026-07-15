# Street View Publisher — Map + Camera Editor

Cette version garde la logique existante :

- Organisation → Place → Tour existant → Scene360 existantes
- Auto-lier aller/retour
- Connexion manuelle Depuis → Vers
- Publication / continuation sans dupliquer les images
- Réessayer connexions Google

Nouveautés UX :

- Carte Google Maps intégrée dans le publisher.
- Image 360 Marzipano affichée à côté de la carte.
- Marker draggable pour positionner une scène sur la carte.
- Flèche heading en live sur la carte.
- Poignée de heading déplaçable pour orienter la caméra depuis la carte.
- Rotation dans la 360 synchronisée avec la flèche heading.
- Bouton Orienter vers la cible pour aligner automatiquement la caméra vers une liaison manuelle.
- Polylines avec flèches pour visualiser les liaisons Street View.
- Recherche d’adresse dans la carte.

Installation :

```bash
unzip app_streetview_map_camera_editor_patch.zip -d .
python manage.py check
python manage.py runserver 8000
```

Aucune migration n’est nécessaire.

Settings requis pour la carte :

```python
GOOGLE_MAPS_API_KEY = "..."
# ou
GOOGLE_MAPS_BROWSER_KEY = "..."
```

La clé Maps doit autoriser Maps JavaScript API et Places API si tu veux utiliser la recherche d’adresse.
