# Incident YouTube — vérification anti-robot sur Render

Date : 21 novembre 2026.

## Constat réel

- Le frontend VYRA affiche correctement le choix des plateformes et le formulaire de saisie.
- Trois requêtes `POST /api/inspect` ont renvoyé HTTP 422 lors du premier essai utilisateur.
- Les messages initiaux confondaient l'exigence de connexion et la protection anti-robot.
- Après ajout d'un diagnostic **sans identifiant ni URL dans les logs**, un essai ponctuel d'extraction de métadonnées d'une vidéo YouTube publique depuis Render a produit :
  `Echec VYRA etape=diagnostic plateforme=YouTube categorie=youtube_bot_check type=DownloadError`.
- Cela confirme une demande de vérification automatique côté YouTube **pour cette exécution sur Render**. Les informations disponibles ne démontrent pas que la vidéo initiale est privée, et ne garantissent pas qu'un autre environnement soit accepté.

## Correction V2.0.1

- `app/main.py` : distinguer `youtube_bot_check`, `youtube_javascript`, `rate_limited`, `access_forbidden`, `login_required`, `video_unavailable`, `unsupported_url`, `timeout`, et limites de taille/durée.
- Journaliser uniquement la plateforme, l'étape, la catégorie et le type d'exception ; ne jamais enregistrer une URL, un cookie, un identifiant ou un secret d'authentification.
- Un diagnostic temporaire au démarrage peut être activé avec `VYRA_DIAGNOSTIC_URL` sur une URL YouTube publique autorisée ; **il est désactivé par défaut**.
- `tests/test_app.py` : 26 tests réussis localement.

## Limites actuelles

- L'application sait extraire et convertir certains médias avec `yt-dlp` et `FFmpeg`, mais cela ne signifie pas que chaque réseau ni chaque IP de serveur soient autorisés à récupérer les vidéos.
- **Une réponse 200 à /api/health ne prouve pas l'accès aux plateformes.**
- Des contrôles anti-bot peuvent survenir sur une IP de datacenter. Ne pas demander au client ses cookies ou ses identifiants pour contourner ces contrôles.
- Vérifier les droits nécessaires avant d'effectuer un téléchargement ; ne pas tenter de récupérer du contenu privé ou soumis à DRM.

## Suites de recette

1. Tester localement via `docker compose up --build`, sur un réseau autorisé, et vérifier `/api/health`.
2. Réessayer une vidéo publique autorisée et de courte durée sur YouTube. Vérifier l'analyse, puis MP4/MP3 si les métadonnées sont disponibles.
3. Tester séparément des contenus autorisés d'Instagram et TikTok depuis Render : leurs comportements ne peuvent pas être déduits de l'échec YouTube.
4. Consigner statut, catégorie et durée par plateforme ; **ne pas promettre de disponibilité universelle**.
5. Si Render reste bloqué, privilégier un service self-hosted privé sur la machine de l'utilisateur ou un hébergement autorisé compatible avec le fournisseur.

Suivi : mise en ligne de la classification d'erreurs le 21 novembre 2026, déploiement Render en état `live`. Téléchargement MP4/MP3 réel sur Render **non validé**.
