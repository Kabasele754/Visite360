# Frontend Street View simplifié

Cette version remplace l’ancien écran complexe par une publication guidée en 4 étapes :

1. **Images** : créer/choisir un projet et uploader les panoramas.
2. **Préparer** : corriger une scène sélectionnée, GPS, caméra et statut Google.
3. **Navigation** : auto-lier les scènes en aller-retour ou créer un lien manuel.
4. **Publier** : publier/continuer, réessayer les connexions et copier les liens Google.

## Objectif UX

L’utilisateur ne doit plus comprendre la différence technique entre projet, scène, lien, hotspot, publish job et Google Photo ID. L’écran met l’accent sur :

- le projet actif ;
- les images visibles ;
- le statut GPS et Google ;
- l’auto-liaison Street View ;
- la publication continue sans republier les scènes déjà publiées ;
- le partage des liens.

## Endpoints utilisés

La version frontend utilise les endpoints déjà présents :

- `GET /apis/streetview/config/`
- `GET /apis/streetview/tours/`
- `POST /apis/streetview/tours/create/`
- `GET /apis/streetview/tours/<id>/`
- `POST /apis/streetview/tours/<id>/upload-scenes/`
- `POST /apis/streetview/scenes/<id>/update/`
- `POST /apis/streetview/tours/<id>/auto-connect/`
- `POST /apis/streetview/tours/<id>/save-project/`
- `POST /apis/streetview/tours/<id>/publish/`
- `POST /apis/streetview/tours/<id>/retry-connections/`
- `GET /apis/streetview/tours/<id>/share-links/`
- `POST /apis/streetview/scenes/<id>/mark-published/`
- `GET /apis/streetview/scenes/<id>/google-status/`
- `POST /apis/streetview/scenes/<id>/update-google-camera/`

## Installation

Dézipper à la racine du projet, puis :

```bash
python manage.py check
python manage.py collectstatic --noinput
```

En local :

```bash
python manage.py runserver 8000
```

Puis ouvrir :

```text
http://localhost:8000/apis/streetview/
```
