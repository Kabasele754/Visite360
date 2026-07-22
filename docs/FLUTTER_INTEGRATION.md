# Contrats Flutter / Mobile

Le projet Flutter n’était pas inclus dans l’archive source. Cette documentation fournit les contrats nécessaires pour connecter une application existante.

## Authentification

```http
POST /api/auth/login/
Content-Type: application/json

{"email":"user@example.com","password":"..."}
```

Conserver le jeton JWT dans un stockage sécurisé, puis envoyer :

```http
Authorization: Bearer <access-token>
```

## Créer une conversation

```http
POST /api/enterprise/chat/conversations/
Content-Type: application/json
Authorization: Bearer <access-token>

{
  "organization": 1,
  "tour": 8,
  "scene": 96,
  "locale": "fr",
  "title": "Assistant visite 360"
}
```

## Envoyer un message REST

```http
POST /api/enterprise/chat/conversations/<uuid>/message/
Content-Type: application/json
Authorization: Bearer <access-token>

{"message":"Quels services propose cette organisation ?"}
```

La réponse contient notamment `content`, `citations`, `confidence`, `intent`, `validation` et `metadata`.

## WebSocket

```text
wss://<domain>/ws/enterprise/chat/<conversation_uuid>/
```

Message client :

```json
{"message":"Je voudrais réserver un rendez-vous"}
```

Le cookie/session d’authentification doit être disponible au handshake dans l’implémentation actuelle. Pour une application JWT pure, ajouter un middleware Channels de validation du token dans la query string ou le sous-protocole avant mise en production.

## Base de connaissances

```http
GET /api/enterprise/knowledge/search/?organization=1&q=services
```

## Analyse d’une scène

```http
POST /api/enterprise/vision/analyses/
Content-Type: application/json
Authorization: Bearer <access-token>

{"organization":1,"scene":96,"requested_providers":["yolo","gemini"]}
```

Puis lancer/rejouer l’analyse via les actions exposées dans Swagger.

## Formulaire public

```http
GET  /api/enterprise/integrations/public/forms/<form_uuid>/
POST /api/enterprise/integrations/public/forms/<form_uuid>/
```

Le schéma des champs est renvoyé par le GET. Le POST accepte les clés définies par l’organisation.

## ICS de rendez-vous

```http
POST /api/enterprise/integrations/appointments/ics/
Authorization: Bearer <access-token>
Content-Type: application/json

{"appointment_id":123}
```

Traiter la réponse comme un fichier `text/calendar`.

## Recommandations d’interface

- Afficher les citations comme liens vers les pages officielles de l’organisation.
- Signaler visuellement une réponse dont `validation.valid` est faux.
- Conserver l’UUID de conversation pendant toute la visite.
- Envoyer l’identifiant de scène lors d’un changement de panorama.
- Prévoir un fallback REST lorsque le WebSocket est indisponible.
