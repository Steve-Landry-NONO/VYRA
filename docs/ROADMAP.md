# Feuille de route — VYRA

Dernière révision : **21 novembre 2026**. La distinction entre **intégré**, **vérifié** et **à valider** est intentionnelle.

## Version en référence : V2.0 — quatre univers animés

- [x] API locale FastAPI pour analyse, tâche, statut et récupération du média.
- [x] Conversion MP4/MP3 orchestrée par yt-dlp et FFmpeg dans le code.
- [x] Interface thématisée YouTube, Instagram, TikTok, Snapchat.
- [x] Détection automatique de plateforme au collage/saisie d'une URL reconnue.
- [x] Fondus, transitions, ergonomie responsive et mouvement réduit.
- [x] Démo HTML autonome distincte de l'application serveur.
- [x] 16 tests Python simulés réussis localement.
- [x] Documentation de reprise et conventions de commits françaises.
- [ ] **Validation réelle** du téléchargement sur les principales plateformes.
- [ ] Qualification du support Snapchat (extraction publique, limites, messages).

## Priorité P0 — V2.1 : qualification et robustesse

- [ ] Tester YouTube, Instagram et TikTok avec des contenus publics autorisés et consigner versions, formats, erreurs et résultat de lecture.
- [ ] Différencier correctement « lien non supporté », « privé », « contenu supprimé », « restriction de plateforme » et « erreur transitoire ».
- [ ] Ajouter tests navigateur reproductibles (par ex. Playwright) pour les quatre thèmes, erreurs, focus clavier, 320 px et démo.
- [ ] Tester limites, saturation du pool, nettoyage, interruptions, taille/durée et fichiers partiels.
- [ ] Vérifier les binaires générés avec `ffprobe` ; ajouter vérification des codecs/conteneurs.
- [ ] Éviter la dérive entre `DEMO_INTERFACE.html` et `app/static/*` (génération ou test de parité).
- [ ] Documenter les versions exactes des dépendances pour rendre les builds reproductibles.

**Critère de sortie :** suite automatisée et recette réelle versionnée, erreurs compréhensibles, absence de confusion entre capacité affichée et capacité démontrée.

## Priorité P1 — V2.2 : sécurisation pour partage contrôlé

- [ ] Implémenter authentification, autorisation par utilisateur et accès aux fichiers par propriétaire.
- [ ] Définir quotas par compte et plafonds d'usage CPU, RAM, espace disque et bande passante.
- [ ] Mettre en place une protection SSRF/egress réseau y compris pour redirections et sous-requêtes de l'extracteur.
- [ ] Isoler les traitements ; appliquer timeouts d'exécution et purge planifiée indépendante des appels HTTP.
- [ ] Ajouter audit d'usage, logs structurés sans données sensibles et métriques opérationnelles.
- [ ] Rédiger politique d'utilisation acceptable, conformité et respect des droits sur les médias.

**Critère de sortie :** audit de sécurité et de charge approuvé, flux d'accès testés, documentation d'exploitation complète.

## Priorité P2 — V3 : industrialisation et diffusion

- [ ] File de jobs persistante (service dédié), état partagé et reprise après incident.
- [ ] Stockage des artefacts temporaire externe et purge garantie, avec coût maîtrisé.
- [ ] Interface d'observabilité, journal des traitements autorisés et alertes.
- [ ] Déploiement conteneur permanent derrière HTTPS avec environnement préprod.
- [ ] Accessibilité WCAG et tests multi-navigateurs automatisés.
- [ ] Politique de disponibilité réaliste pour chaque plateforme ; désactiver visuellement une source non qualifiée.

**Critère de sortie :** publication contrôlée, supervision et mécanismes de rollback opérationnels.

## Règles de décision

Ne pas transformer une fonctionnalité **codée** en fonctionnalité **validée** sans cas de test réel documenté. Ne pas présenter Snapchat comme compatible tant qu'une extraction n'est pas vérifiée et maintenable. Ne pas exposer publiquement la V2 initiale sous prétexte que la page d'accueil est fonctionnelle.

Les demandes produit nouvelles doivent faire l'objet d'une issue/PR, d'une estimation d'impact sur les fichiers et d'un test de non-régression avant fusion.
