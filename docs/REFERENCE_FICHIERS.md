# Guide de reprise — responsabilité de chaque fichier

> Objectif : qu'une personne découvrant VYRA puisse identifier **où intervenir, quoi préserver, quoi tester et où chercher l'information** sans accès à l'historique de discussion. Ce guide décrit le contenu V2 du dépôt.

## Lire ce guide dans cet ordre

1. Lire `README.md` pour la promesse produit et le démarrage.
2. Lire `docs/ARCHITECTURE.md` pour comprendre les flux de données et les risques.
3. Étudier les trois fichiers `app/static/*` pour l'expérience visuelle et `app/main.py` pour le moteur.
4. Exécuter `pytest -q` et parcourir `docs/VALIDATION.md` avant toute modification.

## Racine et exploitation

### `README.md`
- **Rôle :** page d'accueil du dépôt ; source de vérité éditoriale sur l'état livré, les limites, l'installation et les documents associés.
- **Entrées :** architecture, tests, décisions produit et état de la livraison.
- **Sortie :** instructions lisibles et liens vers les références techniques.
- **À mettre à jour :** pour chaque version, changement de prérequis, modification de capacité ou de statut.
- **Vigilance :** ne jamais transformer une fonction codée mais non testée en promesse de compatibilité plateforme.

### `LICENSE`
- **Rôle :** licence MIT du dépôt ; existait avant l'import V2.
- **À préserver :** texte et avis de copyright ; ne modifier qu'après décision explicite sur la licence.

### `Dockerfile`
- **Rôle :** assemble une image à partir de `node:22-bookworm-slim`, installe Python/venv et FFmpeg, puis les dépendances et `app/`.
- **Entrées :** `requirements.txt` et dossier `app/`.
- **Sortie :** conteneur qui lance Uvicorn en **un processus** sur le port `8080`, sous l'utilisateur `vyra` (UID 10001).
- **À tester :** `docker compose up --build`, `/api/health`, droits du dossier `/tmp/vyra-media`, extraction et conversion de médias de test autorisés.
- **Vigilance :** préserver Node.js pour les extracteurs qui l'exigent ; les versions ne sont pas verrouillées à des SHA, donc un nouveau build peut modifier les dépendances.

### `compose.yaml`
- **Rôle :** démarrage local, publication `8080:8080`, variables de limite et redémarrage automatique.
- **À modifier :** ports, environnement et éventuelles ressources/volumes **après revue d'exploitation**.
- **Vigilance :** le port expose l'API sur l'hôte ; ce fichier n'apporte ni HTTPS ni authentification. Ne pas assimiler cette configuration à un déploiement Internet public.

### `requirements.txt`
- **Rôle :** déclare FastAPI, Uvicorn et `yt-dlp[default]`.
- **À modifier :** lors d'une mise à jour de sécurité ou d'une dépendance métier, en documentant les versions minimales et les effets sur les extracteurs.
- **À tester :** installation propre sur Python 3.11+ et exécution de la suite pytest ; tester aussi au moins un média réel autorisé lorsque c'est possible.

### `pytest.ini`
- **Rôle :** déclare la racine Python et le répertoire `tests/` pour pytest.
- **À modifier :** uniquement si l'organisation du code/test évolue.

### `.gitignore`
- **Rôle :** empêche le suivi des caches Python, environnements virtuels, `.env`, fichiers `.mp3`/`.mp4` et morceaux incomplets.
- **Vigilance :** aucune donnée sensible, aucun média utilisateur et aucun cookie navigateur ne doivent entrer dans les commits.

### `DEMO_INTERFACE.html`
- **Rôle :** démonstrateur **autonome**, visuellement fidèle aux quatre thèmes ; contient son CSS et son JS dans un seul fichier.
- **Entrées :** clic sur les plateformes, interaction locale, URLs simulées ou saisies.
- **Sortie :** bascule de thèmes et retours d'interface, **sans appel de téléchargement réel**.
- **À tester :** ouvrir directement en navigateur, sélectionner les quatre thèmes, tester mobile et préférence de réduction des animations.
- **Vigilance :** la démo est un snapshot autonome ; **ne pas faire évoluer uniquement la démo** en pensant avoir modifié l'application servie par FastAPI. Toute évolution visuelle doit être répercutée explicitement si l'on veut maintenir leur parité.

## Paquet `app/` et moteur backend

### `app/__init__.py`
- **Rôle :** permet l'import Python de `app` comme paquet.
- **À modifier :** rarement ; ne pas y introduire de logique d'exécution.

### `app/main.py`
- **Rôle :** point central FastAPI ; exposition du frontend (`StaticFiles`) et des routes `/api/*`.
- **Entrées :** URL utilisateur, identifiant d'inspection, format demandé (`mp4`/`mp3`), qualité, variables d'environnement, appels à `yt-dlp` et FFmpeg.
- **Sorties :** métadonnées, état et progression de tâche, erreurs lisibles et fichier MP4/MP3.
- **Sections / fonctions à connaître :**
  - `DOMAINS`, `platform_from_url()` : filtrage de l'hôte et chemin HTTPS ; ne pas élargir les hôtes sans analyse SSRF.
  - `InspectRequest`, `DownloadRequest` : validation structurée des requêtes.
  - `throttle()` : limites par IP et action ; état non persistant.
  - `metadata_from_url()` : extraction des métadonnées sans téléchargement ; contrôle playlist, live et durée.
  - `Job` et `run_download()` : statut, progressions, options MP4/MP3, conversion, fichier final.
  - `prune()` : suppression paresseuse des inspections et anciens jobs.
  - `health()`, `inspect()`, `download()`, `job_status()`, `job_file()` : contrat HTTP consommé par le JavaScript.
- **Invariants :** identifiants aléatoires ; jamais de cookies utilisateurs ; qualité MP4 contrôlée contre les hauteurs détectées ; un seul serveur worker pour l'état local.
- **À tester :** `tests/test_app.py`, traitement d'erreurs, expiration des objets, ressources disque, et essais réels manuels sur liens autorisés.
- **Points faibles connus :** les redirections/extracteurs imposent des défenses réseau supplémentaires contre SSRF ; dictionnaires et quotas non partagés ; pas d'authentification ; purge non planifiée ; progression approximative ; n'exposer publiquement qu'après durcissement.

## Interface servie par le backend

### `app/static/index.html`
- **Rôle :** squelette sémantique du navigateur, attributs et identifiants DOM attendus par le JavaScript.
- **Zones :** sélection des réseaux, titre de parcours, champ URL, bouton d'analyse, carte d'informations média, sélecteurs format/qualité, état et progression.
- **Entrées :** événements de clic/saisie et manipulation DOM depuis `app.js`.
- **Sortie :** structure HTML accessible et lisible en mobile.
- **À modifier :** lors d'un nouveau parcours ou élément visuel. Vérifier systématiquement que les ID/classes consommés par `app.js` et `styles.css` existent toujours.
- **À tester :** navigation clavier, lecteurs d'écran, rendu petit écran, événements d'analyse et d'erreur.

### `app/static/styles.css`
- **Rôle :** système visuel complet : variables de couleurs, typographies, espacements, surfaces, animations, responsive et thèmes par plateforme.
- **Entrées :** attribut `data-theme` défini par le JS, classes HTML, médiaqueries (dont mouvement réduit).
- **Sortie :** identités YouTube (rouge/blanc), Instagram (dégradé), TikTok (noir/cyan/rose), Snapchat (jaune/noir), transitions fluides.
- **À modifier :** variables de thème **avant** d'ajouter des styles ponctuels ; garder un thème par plateforme cohérent.
- **À tester :** quatre thèmes sur desktop/mobile, contrastes texte/fond, focus clavier, largeur 320 px et absence de débordement. Les captures `previews/` documentent une référence visuelle.

### `app/static/app.js`
- **Rôle :** orchestration côté navigateur, sans framework.
- **Sections à connaître :**
  - `modeDetails`, `platformFromLink()`, `setTheme()` : sélection/identification et animation visuelle.
  - Gestion de l'URL et du bouton Coller : reconnaissance automatique du réseau (retour utilisateur côté client seulement).
  - `apiFetch()` : requêtes JSON et conversion des erreurs HTTP.
  - `renderResult()`, `setFormat()`, `updateQualities()` : aperçu, MP4/MP3 et hauteurs proposées.
  - `poll()` et gestion du bouton Télécharger : demande de tâche, suivi, résultat et lien de récupération.
- **Entrées :** liens collés, réponses `/api/*`, événements de l'interface.
- **Sorties :** DOM actualisé, thèmes adaptés, messages, progression.
- **À tester :** `node --check app/static/app.js`, correspondance des ID HTML, sélections format/qualité, URLs invalides, erreurs réseau, état d'attente et téléchargement terminé.
- **Vigilance :** le choix du thème côté client ne constitue ni validation d'URL ni permission de téléchargement.

## Tests et ressources documentaires

### `tests/test_app.py`
- **Rôle :** tests `pytest` de l'API via `TestClient`, avec un faux objet `YoutubeDL` injecté dans `sys.modules`.
- **Scénarios :** rejet de domaines/protocoles invalides, plateformes reconnues, extraction simulée avec qualités, parcours MP4/MP3, validation d'erreurs, inspection expirée et route health.
- **Limite :** aucun média réel téléchargé ; les tests n'évaluent ni les changements de plateformes ni les codecs finaux.
- **À étendre :** quotas, expiration fichier, concurrence, erreurs FFmpeg, redirections, compatibilité des plateformes en environnement contrôlé et tests front automatisés.

### `previews/*`
- **Rôle :** **captures de référence** V2 des états neutre, YouTube, Instagram, TikTok, Snapchat, écran de résultat et présentations mobiles.
- **À modifier :** régénérer après changement visuel significatif et conserver l'ancien jeu dans une release ou branche si nécessaire.
- **Limite :** image figée ; ce ne sont pas des tests de comportement.

### `docs/ARCHITECTURE.md`
- **Rôle :** flux, API, stockage, limites, risques et dépendances techniques.

### `docs/VALIDATION.md`
- **Rôle :** rapport des tests réellement exécutés et liste de validation manuelle pour les futures sorties.

### `docs/CONTRIBUTION.md`
- **Rôle :** règles Git, branches de fonctionnalités, commits français détaillés, critères de revue.

### `docs/ROADMAP.md`
- **Rôle :** distinction V2 livrée, qualification future, durcissement et production.

### `.github/workflows/ci.yml`
- **Rôle :** exécuter les tests Python, compilation et vérification syntaxique JS sur push et PR.
- **Vigilance :** statut du workflow à consulter sur GitHub après le premier push ; pas de test réseau de téléchargements réels ni de build Docker automatisé dans cette version.

### `.github/pull_request_template.md`
- **Rôle :** guide de description du changement, inventaire des fichiers et des validations avant fusion.

## Checklist de prise en main

- [ ] Cloner le dépôt, lire les limitations avant tout usage public.
- [ ] Lancer `docker compose up --build` ou le serveur Python local.
- [ ] Vérifier `curl http://localhost:8080/api/health`.
- [ ] Exécuter `pytest -q` et `node --check app/static/app.js`.
- [ ] Explorer les thèmes dans le vrai site et `DEMO_INTERFACE.html`.
- [ ] Ouvrir les captures `previews/` pour connaître l'interface V2 de référence.
- [ ] Créer une branche dédiée pour tout changement, avec tests et commits français descriptifs.
- [ ] Qualifier séparément le moteur sur des vidéos publiques autorisées avant de promettre une compatibilité réseau.
