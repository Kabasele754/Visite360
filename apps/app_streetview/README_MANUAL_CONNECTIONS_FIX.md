# app_streetview — fix Auto-lier + connexions manuelles

Cette version corrige l’erreur `_ensure_navigation_hotspot() missing request` en retirant les décorateurs Django placés par erreur sur une fonction helper interne.

Elle ajoute aussi une gestion manuelle des connexions :

- Ajouter une liaison `Scene A → Scene B` depuis l’interface.
- Supprimer une liaison.
- Réessayer l’envoi des connexions Google sans republier les images.

Endpoints ajoutés :

- `GET /apis/streetview/source/tours/<tour_id>/connections/`
- `POST /apis/streetview/source/tours/<tour_id>/connections/add/`
- `POST /apis/streetview/source/tours/<tour_id>/connections/<hotspot_id>/delete/`

Aucune migration n’est nécessaire.
