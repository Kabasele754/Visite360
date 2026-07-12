# App Street View — version finale simplifiée

Cette version est prévue pour `apps/app_streetview/`.

## Nouveautés incluses

- OAuth Google Street View Publish API avec PKCE corrigé.
- Upload Street View corrigé avec POST binaire vers `uploadUrl`.
- Publication intelligente : les scènes déjà publiées ne sont pas ré-uploadées.
- Auto-connexion des scènes : `Scene 1 ↔ Scene 2 ↔ Scene 3`.
- Les hotspots Marzipano de type `link` deviennent aussi des connexions Google Street View.
- Bouton `Réessayer connexions` pour envoyer les connexions sans republier les images.
- Partage des liens Google Maps publiés.
- Marquer une scène comme déjà publiée avec un Google Photo ID.
- Injection Photo Sphere XMP avant upload pour mieux gérer la caméra Street View.
- Bouton `Définir comme vue principale` dans Marzipano.
- Endpoint `update-google-camera` pour corriger heading/pitch/roll sur Google après publication.

## Installation

```bash
unzip apps_app_streetview_final_camera_publish.zip -d .
python manage.py check
python manage.py migrate app_streetview
python manage.py runserver 8000
```

## URLs importantes

```text
/apis/streetview/
/apis/streetview/oauth/start/
/apis/streetview/tours/<id>/publish/
/apis/streetview/tours/<id>/retry-connections/
/apis/streetview/scenes/<id>/update-google-camera/
```

## Workflow recommandé

1. Créer une visite.
2. Importer les images 360.
3. Corriger GPS sur la carte.
4. Ouvrir chaque scène en 360.
5. Orienter la caméra et cliquer `Définir comme vue principale`.
6. Créer des hotspots de type `Lien scène` ou cliquer `Auto-lier`.
7. Publier / continuer.
8. Réessayer connexions si Google ne montre pas encore la navigation.
9. Copier et partager les liens Google.
