# Matrice des fonctionnalités

| Fonctionnalité | État | Notes |
|---|---|---|
| Django / DRF / Channels | Intégré | Extension du projet existant |
| Celery / Redis | Intégré | File IA dédiée |
| PostgreSQL / pgvector | Intégré | Migration conditionnelle PostgreSQL |
| Routeur Gemini / OpenAI | Intégré | Fallback et logs |
| Embeddings / RAG | Intégré | Site, document, FAQ, produit, service |
| Crawler de site | Intégré | SSRF, robots, redirections, limites |
| YOLO | Intégré | Activé par défaut dans Docker |
| Florence-2 | Intégré, optionnel | Dépendances/poids à activer |
| PaddleOCR | Intégré, optionnel | PaddlePaddle adapté au matériel requis |
| Gemini Vision | Intégré | Vertex AI ou clé API |
| OpenAI Vision | Intégré, optionnel | Clé et flag requis |
| Fusion Vision | Intégré | Tolère les fournisseurs indisponibles |
| Agents IA | Intégré | 9 types provisionnables |
| Chat RAG | Intégré | REST + WebSocket + citations |
| Anti-hallucination | Intégré | Validation citations/liens vérifiés |
| Mémoire de conversation | Intégré | Messages, résumé, contexte et feedback |
| Google Calendar | Intégré partiellement | Liste/création avec credentials existants |
| Outlook | Modèle prêt | Adaptateur réseau non livré |
| Calendly | Modèle prêt | Adaptateur réseau non livré |
| Formulaires dynamiques | Intégré | Public GET/POST + validation |
| ICS | Intégré | Export des rendez-vous |
| Produits / services | Réutilisé + indexé | Modules existants conservés |
| Stripe / PayPal | Réutilisé | Logique commerce existante |
| Dashboard Enterprise | Intégré | Statistiques et activité récente |
| Monitoring / audit | Intégré | DB, Redis, fournisseurs, requêtes lentes |
| Docker / Nginx / Certbot | Intégré | Bootstrap HTTP puis activation HTTPS |
| Kubernetes | Non livré | Optionnel, hors archive source |
| Flutter | Contrats livrés | Projet Flutter absent de l’archive |
