# Validation report

Validation statique exécutée avant création de l’archive :

- compilation Python de `apps`, `config` et `tests` ;
- validation JavaScript avec `node --check` pour le preview, l’agent de tour et Smart Discovery ;
- 3 tests unitaires du parseur de recherche ;
- parsing YAML de `docker-compose.yml` et contrôle des services/volumes persistants ;
- validation shell du script Nginx TLS ;
- contrôle d’équilibre des blocs Django des nouveaux templates ;
- recherche de signatures usuelles de clés OpenAI, clés Google et clés privées ;
- vérification que les volumes `dev-db-data`, `media-data` et `static-data` restent déclarés.

Résultat : toutes les validations statiques ont réussi.

Limite de l’environnement de génération : l’archive fournie ne contient pas `manage.py` ni le fichier complet de dépendances et l’environnement de génération ne possède pas Django/Docker. Les commandes `manage.py check`, `migrate`, le build Docker et les tests sur appareils Android/iOS doivent donc être exécutés sur le projet complet/serveur après intégration.
