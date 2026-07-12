# app_streetview — Twinscopes Street View 360 Studio

Application Django complète pour préparer et publier des visites 360° vers Google Street View Publish API.

## Emplacement attendu

Le module est configuré pour vivre dans :

```text
apps/app_streetview/
```

car `apps.py` contient :

```python
name = "apps.app_streetview"
```

## Installation

Dans `INSTALLED_APPS` :

```python
INSTALLED_APPS = [
    # ...
    "apps.app_streetview",
]
```

Dans `urls.py` principal :

```python
from django.urls import include, path

urlpatterns = [
    # ...
    path("apis/streetview/", include("apps.app_streetview.urls")),
]
```

Puis :

```bash
python manage.py migrate app_streetview
```

## Page studio

Ouvre :

```text
http://localhost:8000/apis/streetview/
```

La page inclut :

- dashboard des visites ;
- upload multiple d'images 360 ;
- sauvegarde Django ;
- preview Marzipano ;
- hotspots info/lien/url ;
- Google Maps + recherche adresse ;
- liens entre scènes ;
- publication Street View Publish API.

## Endpoints importants

```text
GET  /apis/streetview/config/
GET  /apis/streetview/oauth/start/
GET  /apis/streetview/oauth/callback/
GET  /apis/streetview/tours/
POST /apis/streetview/tours/create/
POST /apis/streetview/tours/<id>/upload-scenes/
POST /apis/streetview/tours/<id>/save-project/
POST /apis/streetview/tours/<id>/publish/
```

## Variables `.env`

```env
GOOGLE_MAPS_BROWSER_KEY=...
GOOGLE_STREETVIEW_CLIENT_ID=...
GOOGLE_STREETVIEW_CLIENT_SECRET=...
GOOGLE_STREETVIEW_SCOPE=https://www.googleapis.com/auth/streetviewpublish
GOOGLE_STREETVIEW_REDIRECT_URI=https://twinscopes.com/apis/streetview/oauth/callback/
GOOGLE_STREETVIEW_REDIRECT_URI_LOCAL=http://localhost:8000/apis/streetview/oauth/callback/
```

## Google Cloud Console

Authorised JavaScript origins :

```text
https://twinscopes.com
http://localhost:8000
http://127.0.0.1:8000
```

Authorised redirect URIs :

```text
https://twinscopes.com/apis/streetview/oauth/callback/
http://localhost:8000/apis/streetview/oauth/callback/
http://127.0.0.1:8000/apis/streetview/oauth/callback/
```

## Remarque importante

Google Street View ne reprend pas les hotspots Marzipano personnalisés. Google reprend surtout :

- image 360 ;
- latitude / longitude ;
- altitude ;
- connexions entre photos ;
- métadonnées Photo Sphere/XMP si elles sont présentes dans l'image.

Les hotspots info/url restent pour la visite web Marzipano dans Twinscopes.
