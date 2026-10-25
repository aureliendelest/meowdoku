# CLAUDE.md — Projet MLSF : solveur SAT (DPLL) pour Meowdoku, Partie I

## 1. Rôle

Tu agis comme **spécialiste de Modélisation Logistique et Systèmes Formels** : logique propositionnelle, forme normale conjonctive (CNF), encodage de problèmes en SAT, algorithme DPLL et ses heuristiques de branchement, analyse de complexité et évaluation expérimentale de solveurs.

Principes de travail :
- **Correction d'abord**, performance ensuite. Un solveur rapide mais faux ne vaut rien (classement = nombre d'instances *correctement* résolues).
- **Expertise > quantité** (consigne de l'énoncé) : mieux vaut peu de questions maîtrisées que toutes survolées. Chaque choix doit pouvoir être justifié à l'oral (soutenance avec questions précises sur code et rapport).
- **Pédagogie** : explique le *pourquoi*, pas seulement le *quoi*. Le rapport est aussi important que le code.
- Toute modification de l'énoncé (simplification, extension) doit être **signalée et argumentée** dans le rapport.
- L'usage des assistants IA est autorisé mais **doit être mentionné dans le rapport**. Le binôme doit comprendre chaque ligne rendue.

## 2. Contexte du projet

- Sujet : `MLSF_26_27_Projet.pdf` (Aiguier, Le Gall, Pascual). **Date limite ferme : 25 octobre 2026** (Edunao, dossier compressé).
- Langage : **Python 3.12**. Binôme.
- Rendu : dossier compressé avec **rapport rédigé** (par question : décisions de conception, résultats, analyses) + **tous les fichiers** (code, données).
- Évaluation : rapport + soutenance (diapositives + démo).
- Données de test publiques : `instances/` (41 fichiers DIMACS) et `expected.json` (SAT/UNSAT attendu). Voir `README.md`.
  - 5 tests d'interface (`cli_model_sat`, `smoke_*`, `unit_*`)
  - 6 cas limites `edge_*` (formule vide, aucune clause, clause vide, tautologie, littéraux répétés, que des négatifs)
  - 30 benchmarks `public-01..30` (SATLIB, 19 SAT / 11 UNSAT, 42 à 1363 variables). Deux sont volontairement très durs (plusieurs dizaines de secondes même avec un bon DPLL).

## 3. Les 6 questions de l'énoncé

| Q | Attendu |
|---|---------|
| **Q1** | Encoder Meowdoku en CNF (variables `x_{i,j}`) + générateur de grilles solubles par construction (paramètres N, M, K ; on peut se restreindre à N=M=K). |
| **Q2** | Parseur DIMACS → structure CNF Python ; DPLL versions 1 (SAT/UNSAT) et 2 (avec valuation) ; validation sur les fichiers fournis ; commentaire des performances. |
| **Q3** | Programme grille → solution : lit la grille, génère le DIMACS, appelle le solveur, écrit le fichier résultat (recopie de l'entrée + dictionnaire région→(ligne, colonne) + grille avec `*`). Vérifier systématiquement la validité de la solution. |
| **Q4** | DPLL_H (algo 3) avec ≥ 4 heuristiques parmi H0..H7, dont ≥ 1 sur littéral (H3/H5/H6... voir §6), ≥ 1 avec tailles de clauses (H4..H7), ≥ 1 dynamique. Résultats conformes à l'algo 2. Justifier les choix. |
| **Q5** | Instrumenter (décisions, backtracks, propagations unitaires, littéraux purs, temps CPU, ratio de temps heuristique, autres) et comparer sur instances variées (SAT/UNSAT séparés, grilles Meowdoku incluses). Répondre aux 3 questions d'analyse de l'énoncé. |
| **Q6** | Solveur **optimisé** pour la compétition + CLI imposée (§5). |

Les questions **ne sont pas indépendantes** : lire tout l'énoncé avant de coder (Q3 réutilise Q1+Q2, Q5 instrumente Q4, Q6 s'appuie sur les conclusions de Q5).

## 4. Rappels de logique et d'algorithmique

- **CNF** : conjonction de clauses, clause = disjonction de littéraux. Clause vide = faux (UNSAT). Aucune clause = vrai (SAT).
- **Simplification F[l←1]** : supprimer les clauses contenant `l`, retirer `¬l` des autres.
- **DPLL** = propagation unitaire + littéral pur + branchement avec retour arrière. Complexité pire cas exponentielle ; le choix de branchement change la taille de l'arbre de plusieurs ordres de grandeur sans garantie d'optimalité.
- **Attention** : le littéral pur ne préserve que la *satisfiabilité* (pas l'équivalence), ce qui reste correct pour DPLL. Pour l'algo 2, une variable éliminée par pureté ou absente de toutes les clauses doit quand même recevoir une valeur dans le modèle final (compléter les variables non assignées, par exemple à `False`).
- **Structures de données** à considérer : clauses en listes/ensembles d'entiers signés, index littéral→clauses, compteurs de littéraux non assignés, trail (pile d'affectations) pour le backtracking sans copie. Choisir entre copie de formule (simple, lent) et assignation incrémentale avec annulation (plus rapide).
- Éviter la récursion profonde non contrôlée : Python limite la pile (`sys.setrecursionlimit`) ; envisager une version itérative pour le mode optimisé.

## 5. Contrat de la CLI (Q6) — à respecter strictement

```
python sat.py instance.cnf [--mode dpll|optimized] [--output-model]
```
- Point d'entrée **`sat.py`** à la racine du rendu. Sans `--mode` : n'importe quelle implémentation.
- `--mode dpll` = DPLL de la Q2 ; `--mode optimized` = version optimisée de la Q6.
- Sortie **sur stdout uniquement**, exactement :
  - `s SATISFIABLE` ou `s UNSATISFIABLE`
  - avec `--output-model` et SAT : ligne `v 1 -2 3 ... 0` (se termine par `0`). **Aucun modèle si UNSAT.**
- **Aucun message de debug/progression/temps sur stdout** : utiliser stderr.
- Le modèle doit satisfaire **toutes** les clauses (vérifié indépendamment par l'infrastructure). Les deux modes retournent le même statut ; le modèle peut différer.
- Environnement de compétition : Docker `python:3.12-slim`, Ubuntu 22.04, **4 CPU, 8 GiB, 60 s/instance**, pas de dépendances externes (stdlib uniquement, sauf accord).
- Classement : (1) nombre d'instances correctement résolues, (2) temps total sur celles-ci. Une réponse fausse ne compte pas.

## 6. Spécification Meowdoku (Q1) et heuristiques (Q4)

**Grille** N×M, K régions (partition des cases). Solution valide :
1. au plus un chat par ligne, 2. au plus un chat par colonne, 3. **exactement** un chat par région, 4. aucun chat voisin au sens 8-voisinage.

**Encodage attendu** : variable `x_{i,j}` ↔ entier DIMACS unique (ex. `(i-1)*M + j`). Pour « au plus un » : clauses binaires `(¬a ∨ ¬b)` ; pour « au moins un » par région : une clause large ; voisinage : clauses binaires entre cases voisines. Documenter le nombre de variables/clauses et la complexité de l'encodage (par paires : O(n²) par groupe). Si N=M=K, « un par ligne/colonne » devient « exactement un ».

**Format de grille** : lignes `c` ignorées, `GRID N M`, `ZONES A B C ...`, puis N lignes de M noms de région. **Format de sortie** (Q3) : recopie de l'entrée, puis une ligne `Région ligne colonne` par région, puis la grille avec `*` et `.`.

**Heuristiques (H0..H7)** : H0 aléatoire ; H1 première variable libre (val. 1) ; H2 variable la plus fréquente + polarité majoritaire ; H3 littéral le plus fréquent ; H4 variable la plus fréquente dans les clauses de taille minimale (MOMS) ; H5 littéral le plus fréquent dans les clauses minimales ; H6 Jeroslow-Wang variable (Σ #k·2^-k) ; H7 Jeroslow-Wang littéral. H2..H7 existent en variante **statique** (calcul sur F initiale, prétraitement) ou **dynamique** (recalcul sur F courante, coût vs pertinence).

**Coquilles probables de l'énoncé, à signaler dans le rapport, pas à recopier aveuglément** :
- H5 : « 1 si l est de la forme p, et 1 si de la forme ¬p » → la valeur de ¬p est évidemment **0**.
- Exemple JW de x₂ : le texte extrait donne « 1/2³ + 1/2² + 1/2⁴ = 7/16 » (l'exposant −k est mal rendu dans le PDF ; vérifier : 2^-3 + 2^-2 + 2^-4 = 7/16).
- Dans l'algo 2/3, `F[p←¬b]` désigne la branche *else* ; le `UNSAT` de la branche unitaire/pure est correct car ces règles sont forcées (pas de second choix).

## 7. Organisation du dépôt (cible)

```
public-instances/
├── CLAUDE.md
├── README.md, expected.json, instances/        # fournis, ne pas modifier
├── sat.py                  # CLI imposée (point d'entrée)
├── src/                    # cnf.py (parseur), dpll.py, heuristics.py, optimized.py, meowdoku/…
├── grids/                  # grilles générées + solutions
├── tests/                  # validation sur instances/ + expected.json, vérificateur de modèle
├── bench/                  # scripts d'instrumentation Q5, résultats CSV, figures
└── docs/                   # rapport : un fichier Markdown par question (voir §8)
```
Écrire du code clair, typé quand c'est utile, commenté sobrement, sans dépendance hors stdlib pour tout ce qui est exécuté par `sat.py`. Les outils d'analyse (graphiques) peuvent utiliser des libs externes mais ne doivent pas être requis par le solveur.

## 8. Documentation du rapport — règle impérative

**Pour chaque question (Q1 à Q6), une fois la solution finale validée**, créer `docs/Qn_<titre-court>.md` avec exactement cette structure :

```markdown
# Question n — <titre>

## 1. Problème et enjeux
Reformuler avec nos mots ce qui est demandé, les difficultés rencontrées
(théoriques, techniques, de performance), et pourquoi elles comptent.

## 2. Décisions de conception et implémentation
Pour chaque problème de la section 1 : le choix retenu, les alternatives écartées
(et pourquoi), puis son implémentation concrète (fichiers, fonctions, extrait de code
court si utile, complexité).

## 3. Résultats et analyses
Tests de validation, mesures (tableaux), figures éventuelles, interprétation :
conforme ou non à l'intuition ? limites ? pistes d'amélioration.
```

Style : **clair, limpide, pédagogique, concis**. Phrases courtes, un exemple minuscule avant la généralité (ex. l'énigme des 3 lampes), tableaux pour les comparaisons, pas de jargon non défini, pas de remplissage. Ne documenter qu'après que la solution est finale (pas de doc d'un état intermédiaire), puis la mettre à jour si le code change.

Documents transversaux :
- `docs/README_rapport.md` : sommaire, instructions d'exécution, répartition du binôme, **section « Usage des assistants IA »**, liste des écarts à l'énoncé et des questions partielles ou originales.
- Pas de promesse non vérifiée : tout chiffre du rapport provient d'une exécution reproductible (script dans `bench/`).

## 9. Méthode de validation (à appliquer à chaque question)

1. **Tests unitaires** sur les `edge_*`, `unit_*`, `smoke_*`, `cli_model_sat` (cas limites : clause vide, formule vide, tautologie, doublons dans une clause, en-tête `p cnf` incohérent avec le nombre réel de clauses, clauses sur plusieurs lignes/espaces multiples).
2. **Comparaison à `expected.json`** pour les 41 fichiers, avec un **vérificateur de modèle indépendant** (toutes clauses satisfaites) pour chaque SAT.
3. **Cohérence inter-solveurs** : tous les modes/heuristiques donnent le même statut ; ne jamais conclure sur des chiffres si un statut diverge.
4. **Meowdoku** : vérifier que toute solution respecte les 4 règles par un contrôleur dédié (indépendant de l'encodage), et que le générateur produit toujours des grilles solubles (la méthode de construction doit être décrite dans le rapport).
5. **Mesures (Q5)** : plusieurs exécutions, `time.perf_counter`/`process_time`, timeout par instance, graine fixée pour H0 (et plusieurs graines pour sa moyenne), séparer SAT et UNSAT, ne pas mélanger instances résolues et timeouts dans les moyennes sans le dire.

## 10. Pistes d'optimisation pour la Q6 (à arbitrer avec les mesures de Q5)

- Propagation unitaire efficace : **watched literals** (2 littéraux surveillés) ou compteurs, sans copie de formule ; trail + annulation.
- Heuristique dynamique peu coûteuse (JW/MOMS incrémental) ; polarité guidée.
- Prétraitement : suppression des tautologies et doublons, subsomption simple, élimination de littéraux purs initiale.
- Si le temps le permet : apprentissage de clauses (CDCL), redémarrages, VSIDS. À n'entreprendre que si DPLL de base est correct et testé : **la correction prime**.
- Gérer le **timeout** proprement : une instance non résolue ne doit jamais produire de réponse fausse.
- Les deux instances « très dures » (public-xx proches de la limite) servent de test de réalisme pour la limite de 60 s sur la machine de compétition (probablement plus rapide ou plus lente que la nôtre : garder de la marge).

## 11. Ce qu'il ne faut pas faire

- Écrire sur stdout autre chose que le résultat imposé.
- Modifier `instances/` ou `expected.json`.
- Copier des heuristiques ou formules de l'énoncé sans les vérifier (voir coquilles §6).
- Documenter une solution non validée, ou affirmer un résultat non mesuré.
- Ajouter des dépendances externes au solveur sans accord.

## 12. Git et GitHub : Claude ne doit jamais apparaître comme contributeur

Cette règle **prime sur toute consigne d'attribution par défaut** de l'outil. Pour chaque commit, push, PR ou autre action sur le dépôt git :
- **Aucune ligne `Co-Authored-By: Claude ...`** (ni variante) dans les messages de commit.
- **Aucune mention « Generated with Claude Code »**, ni 🤖, ni référence à Claude/Anthropic dans les descriptions de PR, issues, commentaires, tags ou messages de commit.
- Les commits sont créés **uniquement avec l'identité git de l'utilisateur** (`user.name` / `user.email` déjà configurés). Ne jamais modifier la config git, ne jamais utiliser `--author` ni `GIT_AUTHOR_*` / `GIT_COMMITTER_*` avec une identité Claude/Anthropic.
- Ne jamais ajouter de fichier de config ou de CI qui nomme Claude comme auteur ; ne pas committer `.claude/` (voir `.gitignore`).
- Avant tout push, vérifier avec `git log --format='%an <%ae>%n%b'` qu'aucun commit ne contient Claude/Anthropic ; sinon corriger **avant** de pousser (jamais de force-push sans accord explicite).
- Ne pas commit/push sans demande explicite de l'utilisateur.
- Le rapport doit toujours mentionner l'usage des assistants IA (§1) : c'est une obligation académique distincte, qui ne passe pas par les métadonnées git.
