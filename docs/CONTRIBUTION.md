# Contribuer à VYRA — Git, qualité et traçabilité

Ce projet doit pouvoir être repris sans explication orale. Les règles ci-dessous prolongent les conventions de documentation des autres projets du même auteur : **état du produit explicite, changements isolés, historique exploitable et commits en français**.

## 1. Branches et stratégie d'évolution

- `main` : état de référence intégré et documenté. Éviter les refontes non isolées après l'import initial.
- `feat/<description>` : fonctionnalité ciblée ; exemples : `feat/controle-telechargement` ou `feat/theme-snapchat-accessibilite`.
- `fix/<description>` : correction reproduite et couverte par un test.
- `docs/<description>` : documentation seule.
- `chore/<description>` : outillage / maintenance.

Procédure type :

```bash
git checkout main
git pull --ff-only
git switch -c feat/qualite-video
# modifier, tester, documenter
git add app/static/app.js app/static/styles.css tests/test_app.py
git commit -m "feat(interface): clarifier le choix des résolutions" \
  -m "- app/static/app.js : rendre les qualités indisponibles non sélectionnables." \
  -m "- app/static/styles.css : améliorer l'état de focus et le contraste des options." \
  -m "- tests/test_app.py : conserver le contrôle des formats exposés par l'API." \
  -m "Vérifications : pytest -q ; node --check app/static/app.js."
git push -u origin feat/qualite-video
```

Ouvrir ensuite une **pull request** vers `main`, idéalement avec captures avant/après pour les changements UI.

## 2. Convention de commits : français obligatoire

Adopter une variante des *Conventional Commits* avec une **description et un corps en français** :

```text
<type>(<périmètre>): <action au présent en français>

- chemin/du/fichier.ext : responsabilité modifiée, ancien comportement, nouveau comportement.
- autre/fichier.ext : raison de la modification et impact sur les dépendances.

Validation : commandes exécutées et résultats.
Limites : points non testés, risques ou tâches reportées.
```

**Types acceptés :** `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`. Le *type* standard peut rester anglais pour l'outillage, mais le **sujet et le corps sont en français**.

Un commit doit :

1. poursuivre **un objectif compréhensible** (ne pas mélanger une refonte UI avec un changement de sécurité backend) ;
2. détailler **chaque fichier modifié**, ce qu'il fait et pourquoi le changement était nécessaire ;
3. mentionner **les tests vraiment exécutés**, jamais des tests supposés ;
4. déclarer clairement les éventuels travaux non réalisés et impacts connus ;
5. ne contenir **ni média utilisateur, ni secret, ni authentification de plateforme**.

## 3. Règles techniques par zone

| Zone | À préserver | Vérifications requises |
|---|---|---|
| API / `app/main.py` | Contrats `/api/*`, liste blanche, qualité, états, absence de cookies | `pytest -q`, cas négatifs, revue SSRF |
| UI HTML / JS | IDs partagés, messages d'erreur, bascule automatique de plateforme | `node --check`, parcours complet et clavier |
| CSS / thèmes | Identité de chaque réseau, fondus, responsive, mouvement réduit | Quatre thèmes sur ordinateur/mobile, contrastes |
| `DEMO_INTERFACE.html` | Exécution autonome et absence d'appel réseau de téléchargement | Ouverture sans Docker et cohérence visuelle avec l'app |
| Infra | Un worker Uvicorn et stockage local tant que l'état est en RAM | Build Docker, `/api/health`, droits du dossier temporaire |
| Documentation | Alignement entre promesse README et réalité | Relire `ROADMAP`, `VALIDATION`, `REFERENCE_FICHIERS` |

**Défense en profondeur :** le filtrage HTTPS / hôtes de l'URL d'entrée ne suffit pas seul pour sécuriser tous les accès réseaux secondaires de `yt-dlp`. Toute ouverture au public exige un modèle de menace spécifique.

## 4. Critères de revue de pull request

La description doit contenir : le problème, la solution, **l'inventaire des fichiers modifiés**, la raison de chaque modification, les effets de bord, les résultats de tests, les captures pour les vues impactées, les risques et les éléments reportés. Utiliser le modèle `.github/pull_request_template.md`.

Avant fusion :

- [ ] Code lisible et fonctions limitées à une responsabilité.
- [ ] Tests de régression adaptés ; `pytest -q` passe.
- [ ] JavaScript syntaxiquement valide ; chemins API cohérents.
- [ ] README et documents mis à jour si changement fonctionnel.
- [ ] Aucune sur-promesse sur la prise en charge de plateformes externes.
- [ ] Aucune donnée secrète ou contenu tiers introduit dans l'historique.
- [ ] Capture ou description de test pour chaque thème modifié.
- [ ] Revue attentive des changements d'accès réseau, d'écriture disque ou de commandes système.

## 5. Versionnement et traçabilité

Les versions V1/V2 présentées dans le README sont un **historique fonctionnel**, pas nécessairement des tags Git publiés. Pour une future release : créer un tag après validation, documenter les évolutions dans `docs/ROADMAP.md` et conserver les captures de comparaison.

Ne pas réécrire ou forcer l'historique de `main` pour une correction ordinaire. Une régression doit être résolue par un nouveau commit, de préférence isolé, testable et réversible.
