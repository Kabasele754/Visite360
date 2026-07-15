# Bibliothèque Google Street View publiée

Ajoute une bibliothèque pour récupérer les photos Street View publiées par le compte Google connecté.

Endpoints ajoutés :

- `GET /apis/streetview/published/google-photos/`
- `POST /apis/streetview/published/google-photos/link-scene/`
- `POST /apis/streetview/published/google-photos/delete/`
- `POST /apis/streetview/published/google-photos/update-pose/`

La bibliothèque fusionne les photos retournées par Google avec les états locaux `StreetViewSourceSceneState`, car Google peut ne pas retourner immédiatement les photos récemment publiées pendant leur indexation.

Workflow recommandé :

1. Connecter Google Street View.
2. Ouvrir l’onglet `Images Google`.
3. Cliquer `Actualiser`.
4. Filtrer par `Tout`, `Liées`, `Non liées`, `Rejetées`.
5. Sélectionner une scène dans l’éditeur si on veut rattacher une photo Google existante à une scène locale.
