# Twinscopes — PDF mobile, agents métiers, recherche et vision ciblée

Cette version ajoute quatre blocs cohérents sans remplacer les données existantes :

1. un lecteur PDF mobile avec flux HTTP `Range` sous la même origine ;
2. un agent hospitalier fondé sur des sources officielles et des contacts publics ;
3. des profils immobiliers/hôteliers interrogeables depuis la page d’accueil ;
4. une sélection visuelle redimensionnable avant l’inspection d’un objet 360°.

## 1. PDF sur Android et iOS

Le hotspot PDF fournit désormais `document_stream_url`. L’URL est contrôlée par Django, garde les règles de publication du tour et prend en charge :

- `GET` et `HEAD` ;
- `Accept-Ranges: bytes` ;
- `206 Partial Content` et `Content-Range` ;
- `Content-Disposition: inline` ;
- `X-Frame-Options: SAMEORIGIN` ;
- lecture progressive de PDF.js sans charger tout le document en mémoire ;
- module PDF.js legacy en priorité sur iOS ;
- worker désactivé sur mobile ;
- rendu immédiat des premières pages, puis chargement paresseux au défilement ;
- ouverture plein écran avec le lecteur natif en secours.

Tests rapides :

```bash
curl -I https://twinscopes.com/ORG/tours/TOUR_ID/hotspots/HOTSPOT_ID/document/

curl -I \
  -H 'Range: bytes=0-1023' \
  https://twinscopes.com/ORG/tours/TOUR_ID/hotspots/HOTSPOT_ID/document/
```

Le second appel doit répondre `206` avec `Content-Range`.

Les volumes Docker `media-data` et `static-data` restent inchangés. Le problème n’est donc pas traité en supprimant ou recréant les volumes, mais par la diffusion correcte du fichier et des statiques.

## 2. Agent hospitalier professionnel

L’application `apps.domain_intelligence` introduit :

- `OrganizationIntelligenceProfile` ;
- `HealthcareFacilityProfile` ;
- `MedicalSpecialty` ;
- `MedicalPractitioner` ;
- `PractitionerAvailability` ;
- `VerifiedSourceFact`.

Lorsqu’un lieu publié est classé `hospital`, `clinic`, `dental_clinic` ou `pharmacy`, le profil hospitalier est créé automatiquement. Si l’organisation possède un site officiel, une synchronisation Celery peut être déclenchée.

Le synchroniseur :

- respecte le domaine officiel et les règles `robots.txt` ;
- bloque les cibles locales/privées pour éviter le SSRF ;
- indexe les pages dans la base de connaissances pgvector ;
- lit les données JSON-LD de type Hospital, MedicalClinic, Physician et Dentist ;
- complète les informations avec des liens publics `tel:` et `mailto:` et des titres de pages clairement identifiés ;
- conserve l’URL source et la date de vérification ;
- ne rend public que le téléphone ou l’email explicitement marqué public ;
- ne donne ni diagnostic, ni prescription, ni disponibilité inventée.

Synchronisation :

```bash
docker compose exec django \
python manage.py sync_domain_intelligence \
  --organization melrosesurgical \
  --mode celery \
  --max-pages 30

docker compose logs -f celery_worker
```

Pour un premier diagnostic synchrone limité :

```bash
docker compose exec django \
python manage.py sync_domain_intelligence \
  --organization melrosesurgical \
  --mode sync \
  --max-pages 5
```

Les docteurs, spécialités, profils d’établissement, disponibilités récurrentes et contacts publics peuvent aussi être validés manuellement dans Django Admin.

## 3. Rendez-vous avec un docteur

La page d’accueil ouvre maintenant un formulaire de rendez-vous sécurisé depuis un résultat hospitalier. Il enregistre :

- organisation, tour et lieu ;
- docteur et spécialité ;
- nom, téléphone et email ;
- date et heure souhaitées ;
- mode sur place ou téléconsultation ;
- motif administratif.

La demande reste `pending` jusqu’à la confirmation de l’établissement. Si une connexion Google Calendar active existe, l’événement est ajouté au calendrier de l’organisation. Un échec Calendar ne supprime pas la demande.

La route publique comprend :

- protection CSRF ;
- honeypot anti-robot ;
- limitation par appareil/IP ;
- validation de la date, du téléphone et de l’email ;
- messages publics sans détails techniques.

## 4. Profils immobiliers et hôteliers

Les modèles ajoutés sont :

- `PropertyListingProfile` : type d’annonce, type de bien, chambres, salles de bain, stationnement, surface, prix, devise, ameublement, équipements, animaux et disponibilité ;
- `HospitalityProfile` : étoiles, nombre de chambres, prix de départ, horaires, équipements, lien de réservation et disponibilité.

Les anciens champs de `Tour` (`chambres`, `price`, `parking`, `balcon`, `ascenseur`) sont synchronisés vers le profil immobilier pour conserver la compatibilité.

La page Home comprend `Twinscopes Smart Discovery`. Elle comprend les demandes en français ou en anglais, par exemple :

- « maison de 3 chambres à louer à Sandton avec parking » ;
- « hôpital avec service de cardiologie » ;
- « hôtel proche de moi avec wifi ».

L’analyse structurée utilise l’IA lorsqu’elle est disponible et retombe automatiquement sur un parseur déterministe. Les résultats ne contiennent que des tours publiés, des organisations actives et des lieux publiés. Une adresse textuelle, une ville ou la position du navigateur peuvent être utilisées.

## 5. Inspection exacte d’un objet

Un appui long ne lance plus immédiatement l’analyse. Le visiteur obtient une zone de sélection :

- déplacement libre ;
- quatre poignées de redimensionnement ;
- grille et réticule ;
- confirmation explicite ;
- envoi du rectangle normalisé et des quatre coins yaw/pitch.

Le backend calcule le champ de vision à partir de la taille réelle de la sélection. Un résultat sans objet local et sans confirmation sémantique suffisante est rejeté, ce qui réduit les réponses obtenues en cliquant dans le vide.

La projection corrige la convention de pitch Marzipano avec :

```env
VISION_MARZIPANO_PITCH_SIGN=-1
```

Si une installation utilise la convention inverse, mettre temporairement `1`, recréer seulement `django` et `ai_worker`, puis tester une sélection au-dessus et au-dessous de l’horizon.

## 6. Déploiement sans perte de données

Sauvegarde d’abord la configuration :

```bash
cd /root/Visite360
cp .env ".env.backup_$(date +%Y%m%d_%H%M%S)"
```

Validation et déploiement :

```bash
docker compose config -q

docker compose build django celery_worker ai_worker nginx

docker compose up -d \
  django \
  celery_worker \
  ai_worker \
  celery_beat \
  nginx

docker compose exec django python manage.py migrate --noinput
docker compose exec django python manage.py collectstatic --noinput
docker compose exec django python manage.py check
docker compose exec nginx nginx -t
```

Ces commandes ne suppriment pas les volumes. Ne jamais exécuter pour ce déploiement :

```bash
docker compose down -v
docker volume prune
docker system prune --volumes
```

## 7. Vérifications fonctionnelles

```bash
# Routes et modèles
docker compose exec django python manage.py showmigrations domain_intelligence vendors

# Configuration IA/PDF
docker compose exec ai_worker python manage.py check_ai_stack

# Site officiel hospitalier
docker compose exec django python manage.py sync_domain_intelligence \
  --organization melrosesurgical --mode celery --max-pages 10

# Logs applicatifs
docker compose logs --tail=150 django celery_worker ai_worker nginx
```

Tester ensuite sur un vrai Android et un vrai iPhone : ouverture d’un petit PDF, d’un PDF volumineux, passage plein écran, retour au panorama, sélection d’un objet au-dessus et au-dessous de l’horizon, recherche d’un bien et demande de rendez-vous.

## 8. Saisie métier directement dans le formulaire Tour

Le formulaire de création/modification d’un Tour contient maintenant trois sections avancées :

- immobilier : type d’annonce, type de bien, salles de bain, stationnement, surface, devise, équipements, animaux et disponibilité ;
- hôtel : étoiles, nombre de chambres, prix de départ, check-in/check-out, équipements, URL de réservation et disponibilité ;
- santé : téléphone/email/URL de rendez-vous, urgence, walk-in, téléconsultation, spécialités et assurances.

Seule la section correspondant à la catégorie du `Place` sélectionné est enregistrée. Les champs historiques du Tour restent compatibles et alimentent le nouveau profil.

Pour les lieux et tours créés avant cette version :

```bash
docker compose exec django \
python manage.py bootstrap_domain_profiles
```

Pour une organisation précise :

```bash
docker compose exec django \
python manage.py bootstrap_domain_profiles --organization melrosesurgical
```

Pour créer les profils existants puis lancer la collecte des sites hospitaliers officiels :

```bash
docker compose exec django \
python manage.py bootstrap_domain_profiles \
  --queue-healthcare-sync \
  --max-pages 20
```

Cette commande ne supprime et ne remplace aucun Tour, aucune scène et aucun média.

## 9. Protection du Smart Discovery

La recherche publique possède maintenant :

- une limite par appareil/IP ;
- un cache des intentions structurées afin d’éviter de répéter les appels LLM identiques ;
- un parseur déterministe de secours lorsque l’IA est indisponible ;
- une limitation stricte aux tours publiés, organisations actives et lieux publiés ;
- aucun détail technique ni nom de fournisseur dans les erreurs publiques.

Variables :

```env
DISCOVERY_INTENT_CACHE_SECONDS=600
PUBLIC_DISCOVERY_RATE_LIMIT=30
PUBLIC_DISCOVERY_RATE_WINDOW_SECONDS=300
```

## 10. Sécurité Git et secrets

Le projet contient un `.gitignore` et un `.dockerignore` renforcés. Les fichiers `.env`, credentials Google, certificats, médias, sauvegardes, modèles IA et caches locaux ne doivent pas être poussés sur GitHub.

La configuration locale exemple reste versionnable :

```text
.env.production.example
```

Une ancienne clé Django codée en dur dans le fichier legacy `config/settingyys.py` a été remplacée par une lecture de `SECRET_KEY` depuis l’environnement.
