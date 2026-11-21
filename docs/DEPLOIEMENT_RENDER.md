# VYRA V2 — Déploiement de test sur Render

> **Statut : configuration prête, hébergement non lancé tant qu’un service Render n’a pas été créé.** La présence de `render.yaml` ne prouve pas que le site est accessible.

## Objectif

Déployer **une seule instance Docker** de FastAPI, yt-dlp, Node et FFmpeg pour tester des liens **publics et autorisés** sur YouTube, Instagram et TikTok. Snapchat reste expérimental. Aucun contournement DRM, compte privé, cookies, ou authentification aux plateformes n'est prévu.

## Procédure Render

1. Connecter Render à GitHub, puis choisir `Steve-Landry-NONO/VYRA`.
2. Dans Render : **New > Blueprint**, choisir le dépôt et sa branche `main`. Render lira `render.yaml`.
3. Vérifier avant validation : service `vyra-tests`, `runtime: docker`, région `frankfurt`, plan `free` (ou plan de test adapté si l’offre gratuite ne suffit pas).
4. À l'étape des variables, définir **`VYRA_ACCESS_PASSWORD`** directement dans Render, avec un mot de passe long et unique. Ne pas le mettre dans GitHub ou un message.
5. Examiner les logs de build et attendre l'état **Live**. Utiliser uniquement l’URL `https://<sous-domaine-reel>.onrender.com` donnée par Render : ne pas inventer d’URL.
6. Accéder au site : le navigateur demande l’utilisateur (`testeur`) et le mot de passe choisi. Les requêtes API utilisent la même origine.
7. Contrôler `/api/health` : `ok: true`, `engine: true` et `ffmpeg: true` sont les résultats attendus. `ok: true` seul ne garantit pas que le moteur est opérationnel.

## Parcours de recette réelle

1. Utiliser **une vidéo dont le téléchargement est autorisé**, coller une URL YouTube publique ; vérifier métadonnées, miniature et qualités réellement offertes.
2. Demander un MP4 360p ou 720p **seulement si disponible**, patienter jusqu’à `ready`, télécharger le fichier et vérifier sa lecture avec audio.
3. Recommencer avec MP3 ; vérifier la lecture du fichier audio.
4. Tester une vidéo Instagram publique, puis TikTok public. Les plateformes peuvent restreindre l’accès depuis les datacenters ou changer leur fonctionnement ; consigner précisément les erreurs.
5. Vérifier URL invalide, publication indisponible, format absent, vidéo trop longue et limite de fréquence.
6. Tester sur mobile et ordinateur, en consignant la date, la plateforme, le type de média, le résultat, les logs pertinents et le temps d’analyse, sans diffuser de données privées.

## Paramètres de l’instance

| Variable | Valeur Render | Rôle |
|---|---|---|
| `PORT` | fourni par Render | Port d’écoute géré par le Dockerfile |
| `VYRA_REQUIRE_AUTH` | `1` | Verrouille pages et API sauf la santé |
| `VYRA_ACCESS_USER` | `testeur` | Identifiant HTTP Basic |
| `VYRA_ACCESS_PASSWORD` | secret Render | Mot de passe ; s’il manque, accès refusé par `503` |
| `VYRA_MAX_DURATION_SECONDS` | `600` | Durée maximale de 10 min pour les premiers essais |
| `VYRA_MAX_FILE_BYTES` | `104857600` | Taille maximale annoncée : 100 Mio |

## Limites et risques

- Les téléchargements et tâches restent dans la **mémoire et le stockage temporaire de l’instance unique**. Mise en veille, panne ou redéploiement ⇒ perte des travaux en cours et des fichiers.
- Le service n'est **pas prêt pour un trafic public**. Les fichiers volumineux, les conversions lourdes et les téléchargements simultanés peuvent dépasser les quotas ou la RAM de l’offre gratuite.
- Le plan gratuit peut se mettre en veille après inactivité et comporte des limites de bande passante ; vérifier le plan courant dans Render.
- Une plateforme peut refuser l’accès depuis une adresse IP de datacenter, même pour un contenu public. Cela ne signifie pas nécessairement que VYRA est en panne.
- L’authentification HTTP Basic suppose **HTTPS obligatoire**, fourni par Render, mais ne remplace pas une vraie gestion de comptes et de quotas pour la production.
- La limite de taille yt-dlp n’est pas encore une isolation forte du disque ou des ressources.
- Respecter droits d’auteur, droits à l’image, conditions des plateformes et confidentialité des créateurs.

## Tester localement sans hébergement

```bash
git clone https://github.com/Steve-Landry-NONO/VYRA.git
cd VYRA
docker compose up --build
# Ouvrir http://localhost:8080
# curl http://localhost:8080/api/health
```

Par défaut, Docker Compose local ne demande pas de mot de passe. Pour protéger un accès réseau, définir `VYRA_REQUIRE_AUTH=1` et `VYRA_ACCESS_PASSWORD` comme variables d’environnement **non versionnées**.
