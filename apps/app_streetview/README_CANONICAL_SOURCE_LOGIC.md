# Street View Publisher — logique canonique Organization → Place → Tour → Scene360

Cette version corrige la logique précédente : elle ne recrée plus les tours, scènes ou images 360.

## Principe

Source officielle de données :

```text
Organization
  └── Place
        └── Tour
              └── Scene360
                    └── Hotspot(type=navigate)
```

`app_streetview` devient seulement une couche de publication Google Street View :

```text
StreetViewSourcePublication
  └── StreetViewSourceSceneState
```

Ces modèles stockent uniquement :

- Google Photo ID
- lien de partage Google Maps
- statut de publication
- GPS/caméra utilisés pour Google
- logs de publication

Ils ne copient pas les fichiers image.

## Nouvelle interface

URL :

```text
/apis/streetview/
```

Flux :

```text
1. Choisir une organisation
2. Choisir un place
3. Choisir un tour existant
4. Voir la liste compacte des images Scene360 existantes
5. Appliquer GPS du place si nécessaire
6. Auto-lier aller/retour avec les Hotspot(type=navigate) existants
7. Publier / continuer
8. Copier les liens Google
```

## Nouveaux endpoints

```text
GET  /apis/streetview/source/organizations/
GET  /apis/streetview/source/organizations/<org_id>/places/
GET  /apis/streetview/source/places/<place_id>/tours/
GET  /apis/streetview/source/tours/<tour_id>/
POST /apis/streetview/source/tours/<tour_id>/apply-place-gps/
POST /apis/streetview/source/tours/<tour_id>/auto-link/
POST /apis/streetview/source/tours/<tour_id>/publish/
POST /apis/streetview/source/tours/<tour_id>/retry-connections/
GET  /apis/streetview/source/tours/<tour_id>/share-links/
POST /apis/streetview/source/scenes/<scene_id>/state/
POST /apis/streetview/source/scenes/<scene_id>/mark-published/
```

## Installation

```bash
python manage.py makemigrations app_streetview
python manage.py migrate app_streetview
python manage.py collectstatic --noinput
```

## Important

L'ancien système `StreetViewTour` / `StreetViewScene` est conservé pour compatibilité, mais la nouvelle interface utilise les modèles existants `apps.tours.Tour` et `apps.tours.Scene360`.
