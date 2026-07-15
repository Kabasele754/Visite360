# Patch DOM Safe — canonical publisher

Ce patch corrige les erreurs frontend :
- `Cannot set properties of null (setting 'onclick')`
- `Cannot set properties of null (setting 'src')`
- `initCanonicalPublisherPage is not a function`

Cause principale : mismatch entre template HTML et JS chargé/cache navigateur ou collectstatic.
Correction : le JS devient tolérant aux IDs absents et la callback Google Maps est déclarée dès le début du fichier.

Après installation, vider le cache navigateur ou tester en navigation privée.
En production, lancer `python manage.py collectstatic --noinput`.
