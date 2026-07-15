# Patch tabs Images Google / Éditer un tour

Correction de l'interface `canonical_publisher` :

- les onglets restent cliquables même si une requête API échoue ;
- `Éditer un tour` et `Images Google` basculent correctement les panneaux ;
- la bibliothèque Google initialise ses états (`googlePhotos`, filtres, pagination) ;
- protection contre les chargements multiples ;
- fallback par délégation d'événement pour éviter les soucis de cache / ordre de chargement JS.

Après installation, faire un refresh fort du navigateur : Cmd+Shift+R.
