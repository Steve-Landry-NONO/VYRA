# Validation et recette — VYRA V2

## 1. État de la qualité au 21 novembre 2026

| Vérification | Résultat connu | Portée |
|---|---|---|
| `pytest -q` | **16 tests réussis localement** | TestClient + moteur d'extraction simulé |
| `node --check app/static/app.js` | **Réussi localement** | Syntaxe JavaScript, pas le comportement dans un navigateur |
| Rendus Chromium antérieurs V2 | **Vérifiés visuellement** | Thèmes YouTube, Instagram, TikTok, Snapchat ; ordinateur et mobile |
| Sélection MP4/MP3 et parcours de résultat | **Parcours simulé vérifié** | Réponses API fictives, pas de conversion réelle |
| Test de téléchargement sur médias réels | **Non exécuté ici** | À effectuer séparément sur contenus autorisés |
| Extraction de stories Snapchat | **Non validée** | Fonction expérimentale |
| CI GitHub Actions | **À vérifier sur GitHub après commit** | Workflow ajouté au dépôt, succès non présumé |

**Interprétation :** le code et la navigation sont en place ; la compatibilité opérationnelle avec les sites tiers n'est **pas démontrée** par ces résultats. Éviter les mentions « testé YouTube/Instagram/TikTok » sans tracer les essais réels.

## 2. Exécution des vérifications

```bash
# À la racine du projet, dans un environnement Python activé
python -m pip install -r requirements.txt pytest httpx
pytest -q
node --check app/static/app.js
python -m compileall -q app
```

Pour tester le build :

```bash
docker compose up --build -d
curl -sS http://localhost:8080/api/health
docker compose down
```

Le code d'état HTTP `200` et les indicateurs `engine` / `ffmpeg` donnent une **vérification de dépendances**, pas une assurance de téléchargement réel.

## 3. Ce que couvrent les tests automatisés

Les cas de `tests/test_app.py` vérifient :

- refus des protocoles non HTTPS, des hôtes usurpés, d'IP locales, des URL contenant un port ou des identifiants, des domaines inconnus et des chemins non compatibles ;
- reconnaissance des quatre familles de plateformes sur leurs liens admis ;
- extraction simulée des métadonnées et présentation de résolutions réellement présentes dans le faux extracteur ;
- rejet d'une résolution absente ;
- création d'une tâche MP4 et restitution d'un fichier fictif ;
- parcours MP3 fictif et réponse de type audio ;
- inspection introuvable/expirée et routes `/` et `/api/health`.

Les 16 tests comprennent les cas paramétrés d'URL et les autres scénarios d'API. Les tests ne font **aucun appel externe aux plateformes** et remplacent temporairement `yt_dlp.YoutubeDL` par une classe factice. Les octets « fake-media » ne constituent pas un média MP4 ou MP3 valide.

## 4. Grille de recette visuelle (à reprendre après toute refonte)

| Parcours | Attendu | État de la preuve |
|---|---|---|
| Accueil sans réseau | Apparence neutre, formulaire lisible | Capture `previews/01-neutral-desktop.jpg` |
| Clic YouTube | Palette rouge/blanc, textes et pictogramme cohérents | Capture `previews/02-youtube-desktop.jpg` |
| Clic Instagram | Dégradé violet-rose-orange | Capture `previews/02-instagram-desktop.jpg` |
| Clic TikTok | Fond noir, touches cyan/rose | Capture `previews/02-tiktok-desktop.jpg` |
| Clic Snapchat | Jaune/noir/blanc | Capture `previews/02-snapchat-desktop.jpg` |
| Coller une URL reconnue | Basculer automatiquement vers le réseau détecté | Parcours Chromium antérieur, à automatiser |
| Résultat après inspection | Titre, miniature, durée, options MP4/MP3 et hauteurs | Capture `previews/03-youtube-result.jpg` sur réponse simulée |
| Mobile | Pas de débordement, champs utilisables au toucher | Captures `previews/04-*-mobile.jpg` |
| `prefers-reduced-motion` | Réduire ou désactiver les effets superflus | Logique CSS intégrée, tests d'accessibilité à compléter |
| Erreur API | Expliquer le problème, débloquer l'interface | Recette manuelle à compléter |

**Attention :** les captures prouvent un rendu ponctuel, pas la réussite d'un téléchargement ni l'accessibilité complète.

## 5. Scénarios d'intégration réelle (non exécutés)

Procéder uniquement avec un contenu dont les droits de téléchargement sont acquis.

- [ ] YouTube : vidéo publique autorisée et courte ; analyse, 360p/720p si présents, conversion MP4, ouverture dans un lecteur.
- [ ] YouTube : extraction MP3, vérifier la lecture du fichier et ses métadonnées, ne pas supposer une qualité audio créée artificiellement.
- [ ] Instagram : Reel public autorisé sans authentification ; contrôler le résultat ou l'erreur.
- [ ] TikTok : vidéo publique autorisée sans authentification ; contrôler le résultat ou l'erreur.
- [ ] Snapchat : lien public éligible ; documenter **succès ou non prise en charge**, sans promesse.
- [ ] Vidéo privée / protégée : refus explicite ; ne pas demander de cookie ni d'identifiant.
- [ ] Playlist / direct : refus ou message cohérent, conformément à la limitation à un média unique.
- [ ] Durée > 2 h et fichier > 500 Mio : comportement contrôlé ; vérifier aussi les fichiers partiels au sol.
- [ ] Lien invalide, hôte malveillant ou redirection non sûre : refus, journalisation et absence de connexion à un hôte interne (test isolé, non public).
- [ ] Plusieurs téléchargements concurrents : respecter la limite et libérer les ressources après échec.
- [ ] Après expiration : URL de fichier indisponible et nettoyage réel sur disque.

Consigner pour chaque test : plateforme, type de contenu, date, URL expurgée/anonymisée, format demandé, résolution proposée, statut, durée, logs techniques utiles, version de yt-dlp et de FFmpeg. Ne pas stocker un média tiers ou un cookie dans les rapports.

## 6. Critères minimaux avant publication publique

- [ ] Revue légale et politique d'utilisation acceptable.
- [ ] Authentification et autorisation d'accès aux tâches/fichiers.
- [ ] Limitation de débit globale et par identité, quotas CPU/stockage/bande passante.
- [ ] Protection SSRF au niveau réseau et contrôles des redirections.
- [ ] Isolation et restrictions des processus téléchargeurs et transcodeurs.
- [ ] Limites d'exécution et purge périodique indépendante des requêtes HTTP.
- [ ] Observabilité : logs sans secrets, métriques, alertes d'erreurs et saturation.
- [ ] Intégration réelle testée sur des médias autorisés et régression documentée.
- [ ] HTTPS, CSP et protections applicatives selon l'exposition retenue.

**Conclusion : V2 convient à l'exploration/auto-hébergement maîtrisé ; elle n'est pas qualifiée pour une exploitation publique à grande échelle.**
