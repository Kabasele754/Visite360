# app_streetview — version complète canonical source

Cette version garde la logique principale de l'application :

Organization → Place → Tour existant → Scene360 existantes → publication Google Street View.

Elle ne recrée plus les tours, scènes ou images 360. Le module app_streetview sert seulement à publier les contenus existants sur Google Street View et à garder l'état de publication.

## Inclus

- Frontend simplifié pour choisir organisation, place et tour existant.
- Liste compacte des images/scènes du tour.
- Publication Google Street View depuis les images existantes.
- Connexion OAuth Google Street View avec refresh automatique du token.
- Correction timezone token_expiry aware/naive.
- Correction heading Google : normalisation dans l'intervalle [0, 360).
- Normalisation pitch, roll, fov.
- Injection XMP Photo Sphere avant upload.
- Auto-liaison des scènes et récupération des hotspots navigate existants.
- Migration 0002 propre qui n'essaie pas de renommer les anciens index SQLite.

## Installation

Depuis la racine du projet :

```bash
unzip apps_app_streetview_complete_canonical_publish_fixed.zip -d .
python manage.py migrate app_streetview
python manage.py check
python manage.py runserver 8000
```

Si une ancienne migration 0002 cassée existe déjà dans ton dossier local, supprime-la avant de dézipper :

```bash
rm -f apps/app_streetview/migrations/0002_streetviewsourcepublication_and_more.py
```

Puis dézippe la version complète et relance la migration.

## URL

```text
/apis/streetview/
```

## Test token Google

```bash
python manage.py shell -c "from apps.app_streetview.models import StreetViewGoogleAccount; from apps.app_streetview.services.tokens import get_valid_access_token; a=StreetViewGoogleAccount.objects.first(); print('avant:', a.token_expiry); token=get_valid_access_token(a); a.refresh_from_db(); print('token ok:', bool(token)); print('apres:', a.token_expiry)"
```

## Test heading

```bash
python manage.py shell -c "from apps.app_streetview.services.orientation import normalize_heading; print(normalize_heading(360), normalize_heading(-10), normalize_heading(720))"
```

Résultat attendu :

```text
0.0 350.0 0.0
```
