# Rapport — Projet MLSF : un solveur SAT (DPLL) pour Meowdoku, Partie I

Binôme : Aurélien Delest et Joseph Bouteiller. 
Langage : Python 3.12, bibliothèque standard uniquement pour tout ce que lance `sat.py`.

## 0. En bref

| Question                                                 | État                             | Fichiers principaux                                                   |
| -------------------------------------------------------- | --------------------------------- | --------------------------------------------------------------------- |
| Q1 — Encodage SAT de Meowdoku + générateur de grilles | traitée                          |  `src/meowdoku/{grid,encode,generate,check}.py`                     |
| Q2 — Parseur DIMACS, DPLL v1 et v2                      | traitée                          | `src/cnf.py`, `src/dpll.py`                                       |
| Q3 — Grille → solution                                 | traitée                          | `src/meowdoku/solve_grid.py`                                        |
| Q4 — DPLL_H : 16 variantes d'heuristiques               | traitée                          | `src/heuristics.py`, `src/dpll.py`                                |
| Q5 — Instrumentation et comparaison                     | traitée                          | `bench/q5_*.py`, `src/dpll.py` (`Stats`)                        |
| Q6 — Solveur optimisé pour la compétition | traitée (portefeuille parallèle) | `src/optimized.py`, `sat.py`, `bench/q6_*.py` |

Ce que nous retenons des mesures :

- **Correction.** Sur 756 exécutions de la Q5 (42 instances × 16 heuristiques) : 0 réponse fausse. Sur les 41 fichiers fournis, le statut est celui de `expected.json` à chaque fois qu'une réponse est rendue, et chaque modèle SAT est vérifié clause par clause.
- **Le choix de branchement domine tout.** Sur les instances UNSAT publiques, la meilleure heuristique fait environ 19 fois moins de décisions que le choix aléatoire.
- **Solveur final (Q6).** Un portefeuille de 4 solveurs en parallèle (H4d, H1, H0 ×2 graines) résout 52 des 53 instances testées en 60 s, contre 48 pour le DPLL de la Q2, en 10 s au lieu de 78 s sur les instances que les deux résolvent. Une seule instance (`public-03`) reste hors de portée.
- **Les grilles Meowdoku se comportent autrement que les instances SATLIB** : les heuristiques qui comptent les occurrences y sont mauvaises tant que la grille est petite, mais indispensables dès que la grille grandit.

Chaque question suit le même plan : le problème, les décisions de conception, les résultats et leur analyse. Les détails (tableaux complets, alternatives écartées) sont dans `docs/Q1.md`, `Q2_dpll.md`, `Q3_resolution_grille.md`, `Q4_heuristiques.md`, `Q5_instrumentation.md`, `Q6_optimise.md`.

## 1. Exécution et reproduction

```
python sat.py instance.cnf [--mode dpll|optimized] [--output-model]   # CLI imposée (stdout seul)
python -m src.meowdoku.generate --n 8 --seed 3 --output grids/g8.txt  # générateur (Q1)
python -m src.meowdoku.solve_grid grille.txt --output sortie.txt      # grille → solution (Q3)
python -m pytest -q tests                                              # 44 tests
python -m bench.run_bench 60 > bench/q2_resultats.csv                  # Q2
python -m bench.q3_grilles > bench/q3_resultats.csv                    # Q3
python -m bench.q5_heuristiques 10 6 > bench/q5_resultats.csv          # Q5 (~20 min)
python -m bench.q5_analyse > bench/q5_synthese.md                      # tableaux de la Q5
python -m bench.q6_optimise 60 > bench/q6_resultats.csv                # Q6 (~15 min)
python -m bench.q6_analyse > bench/q6_synthese.md                      # tableaux de la Q6
```

Tout chiffre de ce rapport vient de l'un de ces scripts. Les temps sont mesurés sur une seule machine : seuls les rapports entre heuristiques et les compteurs (décisions, propagations…) se transposent à une autre.

## 2. Question 1 — Modéliser Meowdoku en SAT

**Problème.** Une grille N×M est partitionnée en K régions. Une solution place des chats avec : au plus un par ligne, au plus un par colonne, exactement un par région, aucun chat voisin d'un autre (8-voisinage). Il faut une formule CNF dont les modèles sont exactement les solutions, et un générateur de grilles solubles. Le danger principal est silencieux : une erreur d'encodage donne une fausse « solution », et le solveur ne peut pas la détecter.

**Encodage.** La variable `x_{i,j}` (« chat en (i,j) ») a pour numéro DIMACS `(i−1)·M + j`.

| Règle                                   | Clauses                                             | Nombre                                |
| ---------------------------------------- | --------------------------------------------------- | ------------------------------------- |
| au moins un chat par région             | une clause large                                    | K                                     |
| au plus un par ligne / colonne / région | clauses binaires `(¬a ∨ ¬b)` pour chaque paire | N·C(M,2) + M·C(N,2) + Σ C(\|R\|,2) |
| pas de voisins en diagonale              | clauses binaires, une seule fois par paire          | 2(N−1)(M−1)                         |

L'adjacence horizontale et verticale n'a pas de clauses propres : deux cases voisines partagent une ligne ou une colonne, déjà couvertes (économie valable seulement parce que ces deux familles sont présentes). Pour N = M = K, un chat « au plus » par ligne revient à « exactement », une option ajoute ces clauses redondantes ; elle est désactivée par défaut.

*Alternative écartée :* l'encodage séquentiel (Sinz) du « au plus un », plus compact pour les grands groupes. À la taille d'une grille de jeu, la formule reste de quelques milliers de clauses, et les variables auxiliaires donneraient à DPLL de quoi brancher inutilement. Les paires ont aussi la propagation la plus directe : un chat posé rend unitaire toutes les clauses de son groupe.

**Taille de la formule** (moyenne sur 10 grilles générées) : n = 4 → 16 variables, 101 clauses ; n = 10 → 100 et 1 702 ; n = 20 → 400 et 13 346 ; n = 30 → 900 et 44 241. Croissance en O(n³) (lignes et colonnes par paires), très raisonnable.

**Générateur « solution d'abord »** (N = M = K = n, simplification autorisée par l'énoncé) :

1. placer n chats par backtracking aléatoire (un par ligne et par colonne, sans voisins) ;
2. faire pousser n régions connexes, chacune à partir d'un chat : chacune contient donc exactement un chat ;
3. nommer les régions dans un ordre aléatoire, pour ne pas trahir la solution.

Les chats de l'étape 1 sont une solution : **la grille est soluble par construction**. Le tirage est reproductible (`random.Random(seed)`). Il n'existe pas de grille pour n = 2 et n = 3, le générateur les refuse. L'*unicité* de la solution n'est pas garantie (seule l'existence l'est).

**Contrôleur indépendant** (`check.py`) : il vérifie les 4 règles directement sur la grille, sans passer par le CNF. C'est lui qui détecterait une erreur d'encodage.

**Résultats.**

- Pour la grille de l'énoncé (figure 1) : 36 variables, 408 clauses. Une comparaison par force brute sur les 6⁶ placements « un chat par ligne » montre que l'encodage et les règles du jeu s'accordent sur tous, et qu'il y a **une seule solution**, celle de la figure 2.
- Même équivalence vérifiée sur 5 grilles 5×5 générées. Le contrôleur refuse 7 types de violations. Huit grilles illicites sont rejetées avec une erreur claire.
- Générateur testé pour n ∈ {1, 4, 5, 6, 8, 12, 20, 30} avec 5 graines : la solution construite satisfait les clauses et le contrôleur.

## 3. Question 2 — Parseur DIMACS et DPLL (algorithmes 1 et 2)

**Problème.** Lire un fichier DIMACS en structure Python, implémenter DPLL v1 (SAT/UNSAT) et v2 (avec valuation), les valider sur les fichiers fournis et commenter les performances. Pièges : clause étalée sur plusieurs lignes, en-tête `p cnf` faux, clause vide, tautologie, littéraux répétés, variable absente de toutes les clauses (le modèle doit pourtant lui donner une valeur), profondeur de récursion.

**Structure de données.** Une formule est `Cnf(nb_vars, clauses)` ; une clause est une liste d'entiers signés (`-3` pour ¬x₃). Une clause en dictionnaire `variable → 0/1` a été écartée : `(x₁ ∨ ¬x₁)` aurait deux fois la clé 1. Un ensemble de clauses a aussi été écarté (doublons fusionnés, clause vide impossible à représenter sans `frozenset`).

**Parseur.** Une boucle sur les nombres : `0` ferme la clause en cours (même vide), lignes `c` ignorées, `%` termine (convention SATLIB). **L'en-tête n'est pas cru** : on retient le plus grand indice réellement lu. La normalisation (suppression des tautologies, qui préserve la satisfiabilité, et des littéraux répétés) est faite à part, pour garder le parseur fidèle au fichier.

**DPLL.** La recherche travaille sur une liste de `frozenset` :

- `simplifier(F, l)` = F[l←1] ;
- `_propager` répète clause vide (conflit), clause unitaire, littéral pur jusqu'à stabilité ;
- on branche sur `(p, b)` puis, si échec, sur `(p, ¬b)`.

Le littéral pur ne préserve que la satisfiabilité (pas l'équivalence), ce qui suffit à DPLL ; une variable éliminée par pureté ou absente des clauses reçoit `False` dans le modèle final. La récursion est autorisée jusqu'à 100 000 niveaux et `sat.py` tourne dans un thread à grande pile.

**Validation.** `tests/test_instances.py` (12 tests) couvre le parseur (en-tête incohérent, clause sur plusieurs lignes ou vide, tautologies, `%`, `0` final manquant), v1/v2 sur 16 instances rapides, et la CLI (format exact de stdout). Le vérificateur de modèle contrôle chaque clause **d'origine** (avant normalisation), indépendamment du solveur. Bilan sur les 41 fichiers (`bench/q2_resultats.csv`, timeout 60 s) : **38 résolus, tous conformes à `expected.json`** ; v1 et v2 sont d'accord ; les 6 cas `edge_*` sont corrects. Trois timeouts à 60 s (non-réponses, pas des réponses fausses) : `public-03` (UNSAT), `public-12` et `public-27` (SAT).

**Performances (graine 0, une exécution, à titre d'illustration).**

| Instance  | Variables | Statut | v1 (s) | v2 (s) |
| --------- | --------- | ------ | ------ | ------ |
| public-07 | 225       | SAT    | 0,02   | 0,02   |
| public-30 | 100       | UNSAT  | 1,07   | 1,05   |
| public-19 | 729       | SAT    | 8,33   | 8,34   |
| public-11 | 729       | SAT    | 24,48  | 24,04  |
| public-03 | 63        | UNSAT  | > 60   | > 60   |

1. **v1 ≈ v2** : construire la valuation est gratuit, le coût est dans la recherche.
2. **La taille ne prédit pas le temps** : `public-03` (63 variables) n'est pas résolue en 60 s, `public-19` (729 variables, 22 060 clauses) l'est en 8 s.
3. **Sensibilité au branchement.** Avec notre premier choix (premier littéral de la première clause), `public-07` timeoutait ; avec le tirage aléatoire elle prend 0,02 s, mais `public-11` passe de 0,9 s à 24 s. Une même instance varie de 0,02 s à plus de 60 s selon la stratégie : c'est la motivation de la Q4.

## 4. Question 3 — De la grille à la solution

**Problème.** Lire une grille, produire le fichier solution (recopie de l'entrée, une ligne `Région ligne colonne` par région, puis la grille avec `*`). Il n'y a rien à inventer côté recherche : un parcours case par case avec retour arrière *est* DPLL. La Q3 assemble donc Q1 et Q2 :

```
grille → Grid → encode (Q1) → Cnf → dpll_v2 (Q2) → modèle → cases des chats → vérification → fichier
```

**Décisions.**

- **Double vérification systématique** : `verifier_modele` contrôle les clauses, `verifier` (Q1) contrôle les 4 règles du jeu sur la grille. En cas d'incohérence, une erreur est levée : on n'écrit jamais une fausse solution.
- Le `Cnf` reste en mémoire ; le fichier DIMACS n'est écrit qu'avec `--dimacs` (utile pour tester `sat.py`).
- Les lignes de dictionnaire suivent l'ordre de `ZONES` (comme la figure 2) ; l'entrée est recopiée telle quelle.
- **Grille sans solution** : l'énoncé ne dit rien ; nous recopions l'entrée puis écrivons `UNSAT` (choix à nous, signalé en §9).

**Résultats.** La figure 1 est résolue avec exactement la solution de la figure 2 (`A 3 2`, `B 2 5`, `C 1 3`, `D 5 6`, `E 4 4`, `F 6 1`). Les grilles générées pour n ∈ {1, 4, 5, 6, 7, 8, 9} (5 graines chacune) sont toutes résolues avec une solution valide ; une grille 2×2 donne `UNSAT`. Temps (`bench/q3_resultats.csv`, 3 graines par taille) : moins de 1 ms pour n = 4 et 6, 4 à 11 ms pour n = 8, 16 à 25 ms pour n = 10, 20 à 38 ms pour n = 12.

**Limite, corrigée par la Q5.** En Q3 nous avions jugé les grilles « faciles pour DPLL » (propagation des petites régions). C'est vrai jusqu'à n = 12, mais la Q5 montre que cela ne tient plus pour n = 16 et n = 20 avec le choix aléatoire (§7).

## 5. Question 4 — DPLL_H avec heuristiques de branchement (algorithme 3)

**Problème.** Remplacer le tirage aléatoire (ligne 17) par une fonction `Heuristics(F, H)`. L'énoncé demande au moins 4 heuristiques parmi H0..H7, dont une sur littéral, une qui utilise les tailles de clauses, une dynamique ; des résultats conformes à l'algorithme 2 ; des choix justifiés. Une heuristique ne doit **jamais** changer la réponse, seulement le temps.

**Périmètre : 16 variantes.** H0 (aléatoire), H1 (première variable libre, valeur vraie), H2..H7 en version statique (`s`) et dynamique (`d`), et une combinaison originale MJs/MJd.

**Décision centrale : une grille 2 × 3.** H2..H7 ne sont pas six idées mais deux choix croisés, ce qui donne un seul code de score :

| portée \ pondération | fréquence | clauses minimales (MOMS) | Jeroslow-Wang |
| ---------------------- | ---------- | ------------------------ | ------------- |
| variable               | H2         | H4                       | H6            |
| littéral              | H3         | H5                       | H7            |

Chaque case est un « score par littéral » ; la portée *variable* additionne les deux polarités et prend la polarité majoritaire (vrai si #⁺ ≥ #⁻), la portée *littéral* lit le score directement.

**Statique et dynamique.**

- Dynamique : le score est recalculé sur la formule courante à chaque décision (information à jour, coût O(|F|) par décision).
- Statique : on classe une fois sur la formule initiale et on prend le premier élément dont la variable est encore présente. Les éléments de score nul sont mis en fin de classement (une première version plantait quand les clauses minimales initiales avaient disparu).

**Jeroslow-Wang en entiers.** Le poids 2⁻ᵏ est remplacé par `2^(K−k)` (K = plus grande taille) : mêmes comparaisons, aucune erreur d'arrondi. Le test retrouve bien 7/16 pour x₂ sur l'exemple de l'énoncé.

**Départages** : à score égal, la plus petite variable (le littéral positif d'abord) : chaque heuristique hors H0 est déterministe.

**Combinaison MJ (originale).** MOMS laisse souvent beaucoup de variables à égalité, JW arbitre : clé lexicographique `(MOMS, JW)`. Elle vérifie une **hypothèse** (« le départage JW améliore MOMS »), testée en Q5. Une autre combinaison (« H4 si clause de taille ≤ 2, sinon H6 ») a été écartée : après propagation unitaire, la taille minimale est toujours ≥ 2, elle reviendrait à H4.

**Validation.** Les 16 variantes donnent le statut de `expected.json` et un modèle qui satisfait toutes les clauses sur les 6 cas `edge_*`, les tests d'interface et 15 instances `public-*` rapides. Des tests dédiés vérifient les scores, les choix attendus sur la formule de l'énoncé, la polarité négative de H4/H5 et qu'une heuristique statique ne rebranche pas sur une variable déjà affectée.

## 6. Question 6 — Solveur optimisé

**Problème.** `sat.py --mode optimized` doit rendre le bon statut et un modèle valide en moins de 60 s (4 CPU, 8 GiB, stdlib seule). Le classement compte les instances correctement résolues, puis le temps total. Les conclusions de la Q5 orientent le choix : le branchement domine (H4d est la meilleure heuristique), aucune heuristique n'est meilleure partout, et sur SAT le temps varie beaucoup d'une graine à l'autre.

**Décision : un portefeuille de quatre solveurs complets, lancés en parallèle** (`src/optimized.py`). Le premier qui répond gagne, les autres sont arrêtés.

| Solveur | Rôle |
| --- | --- |
| H4d | MOMS dynamique sur variable : la meilleure heuristique de la Q5 |
| H1 | aucun calcul d'heuristique, pas de surcoût de recalcul sur les grandes grilles |
| H0, graines 1 et 2 | diversification aléatoire (coupe la queue lourde des temps sur SAT) |

*Alternative écartée : un modèle différent selon la taille de la grille.* `sat.py` ne reçoit qu'un fichier CNF, pas la grille, et parier sur la bonne stratégie avant de résoudre est moins sûr que de les laisser courir ensemble.

**Correction.** Tous les solveurs sont complets ; un modèle SAT est **revérifié** dans le parent sur les clauses d'origine avant d'être rendu. Un solveur qui meurt n'empêche pas les autres de répondre ; chaque solveur quitte si le parent disparaît (pas de processus orphelin). Stdout ne reçoit que `s …` et `v … 0`.

**Protocole.** 41 fichiers + 12 grilles de graines nouvelles (n = 12 à 24), 3 configurations lancées par la vraie CLI (`dpll`, H4d seul, `optimized`), temps réel, timeout de 60 s, sortie contrôlée (format, statut, modèle). **0 réponse fausse sur 159 exécutions.**

| Configuration | Instances résolues (sur 53) | Temps total sur les 48 instances communes | Plus lente |
| --- | --- | --- | --- |
| `dpll` (algo 2) | 48 | 78,4 s | 33,4 s |
| H4d seul | 52 | 16,6 s | 4,4 s |
| `optimized` | 52 | **10,0 s** | 2,0 s |

Cas durs (s) : `public-12` : T / 11,4 / **1,9** ; `public-27` : T / 12,2 / **3,5** ; `public-03` : T / T / T (T = timeout, colonnes dans l'ordre `dpll` / H4d seul / `optimized`).

**Analyse.**
1. **Le gain principal vient de l'heuristique**, pas du parallélisme : H4d seul passe de 48 à 52 instances et divise le temps par 4,7. Le portefeuille ne résout pas plus d'instances que H4d seul à 60 s.
2. **Le portefeuille réduit le temps** (environ −40 % sur les instances communes) et raccourcit les cas durs : `public-12` de 11,4 s à 1,9 s. À 10 s, cela ferait la différence entre résolu et non résolu. Nous n'avons pas mesuré quel membre gagne ; l'explication par la diversification reste une hypothèse.
3. **Pas de surcoût sur les instances triviales** (médiane de 0,07 s, démarrage des processus compris), mais le portefeuille n'est pas toujours plus rapide (grille 24 graine 11 : 5,8 s contre 3,8 s).

**Limites.** Une exécution par cas ; machine à 8 cœurs, pas la machine de compétition ; si l'infrastructure lance plusieurs instances en parallèle, le gain diminue. Le portefeuille a été choisi avec les données de la Q5 : l'évaluation sur les instances publiques est **optimiste**, seules les 12 grilles de graines nouvelles sont indépendantes (H4d seul y fait déjà 12/12).

**Non fait (pistes).** Moteur DPLL sans copie de formule (2 littéraux surveillés, pile d'affectations, version itérative) : le plus gros gain restant, puisque le recalcul des scores occupe 44 à 74 % du temps sur les grilles (Q5). Apprentissage de clauses (CDCL) pour des instances comme `public-03`, que ni DPLL ni le portefeuille ne résolvent en 60 s. Détails dans `docs/Q6_optimise.md`.

## 7. Question 5 — Instrumentation et comparaison

**Problème.** Mesurer les 16 variantes, répondre à trois questions : les résultats sont-ils conformes aux attentes ? Quel apport d'une heuristique face à l'algorithme 2 ? Le recalcul dynamique vaut-il son coût ? Obstacles : mesurer sans fausser, ne pas moyenner timeouts et temps, distinguer SAT et UNSAT, tenir compte du hasard de H0.

**Instrumentation** (`Stats` dans `src/dpll.py`, de simples incréments). Compteurs de l'énoncé : décisions, retours arrière (branche *else*), propagations unitaires, littéraux purs, temps CPU, part du temps passée dans l'heuristique. Deux critères de notre choix :

- **propagations par décision** (`unitaires / décisions`) : la *qualité* d'un choix. Une bonne décision déclenche beaucoup de propagation derrière elle ;
- **clauses visitées** : un *coût indépendant de la machine*. Les clauses de l'heuristique sont sous-estimées pour H4..H7 (un parcours compté au lieu de deux).

Nous avons écarté la profondeur maximale de l'arbre : elle décrit la forme, pas la qualité, et reste proche du nombre de variables décidées.

**Protocole.** 30 instances `public-*` et 12 grilles Meowdoku (n = 8, 12, 16, 20 ; 3 graines), 16 variantes, H0 avec 3 graines : 756 exécutions, un processus par exécution tué à 10 s. Chaque réponse est vérifiée (statut attendu, modèle valide). Les moyennes (géométriques) ne portent que sur les instances **résolues par toutes les heuristiques comparées** ; les timeouts sont comptés à part ; SAT, UNSAT et grilles sont séparés. Une première exécution mesurait le temps de l'heuristique en temps réel et le temps total en temps CPU (le ratio dépassait 100 %) : nous avons corrigé et tout relancé.

**Résultats globaux.** 0 réponse fausse, 116 timeouts (15 %). `public-03` et `public-27` ne sont résolues par aucune variante en 10 s.

| Instances résolues sur 42 | H0 | H1 | statiques (H2s..H7s, MJs) | dynamiques variable (H4d, H6d, MJd) |
| -------------------------- | -- | -- | ------------------------- | ----------------------------------- |
| total                      | 32 | 36 | 33 à 35                  | 37 à **39**                  |
| grilles (sur 12)           | 9  | 10 | 8                         | **12**                        |

**Instances UNSAT publiques** (9 instances résolues par les 16 variantes ; ici `backtracks = décisions`, tout l'arbre est parcouru) :

| heuristique | décisions  | propagations / décision | temps CPU (ms) |
| ----------- | ----------- | ------------------------ | -------------- |
| H0          | 552         | 13,4                     | 353            |
| H1          | 256         | 13,7                     | 184            |
| H2d         | 79,5        | 14,7                     | 66             |
| H3d         | 143,6       | 14,0                     | 110            |
| H4s / H4d   | 46,5 / 29,5 | 15,2 / 16,3              | 36 / 27        |
| H6d         | 30,5        | 17,4                     | 32             |

**Instances SAT publiques** (11 instances communes) : H0 : 47 décisions, 49 ms ; H4d : 13 décisions, 13 ms ; MJs : 12 décisions, 13 ms.

**Grilles Meowdoku** (7 grilles communes, toutes de taille ≤ 16) : H0 : 39 décisions, 43 ms ; heuristiques de comptage : 108 à 159 décisions, 67 à 122 ms.

Temps CPU (ms) sur les grandes grilles (T = timeout ; pour H0, T dès qu'une des 3 graines échoue) :

| grille       | H0  | H1    | H2s | H2d   | H4d   | MJd   |
| ------------ | --- | ----- | --- | ----- | ----- | ----- |
| 16, graine 0 | T   | T     | 310 | 374   | 426   | 778   |
| 20, graine 0 | 658 | 6 458 | T   | 1 257 | 1 410 | 3 657 |
| 20, graine 1 | T   | T     | T   | 3 155 | 2 484 | 2 772 |

### Les trois questions de l'énoncé

**1. Adéquation avec nos attentes.**

- *Conforme.* Sur UNSAT : H0 est la pire, MOMS et JW les meilleures ; les heuristiques *variable* battent leur version *littéral* (H2d 79,5 décisions contre H3d 143,6), ce qui est normal puisque la polarité ne compte pas quand tout l'arbre est parcouru. Le blocage de H2 sur `public-21`, observé ponctuellement en Q4, est reproduit.
- *Hypothèse non confirmée.* Le départage JW n'améliore pas MOMS (MJd 30,9 décisions contre H4d 29,5 sur UNSAT ; 17 SAT résolues chacune) et coûte plus cher (24,6 % du temps dans l'heuristique contre 11,0 %).
- *Surprise 1 : sur les petites grilles, H0 et H1 battent les heuristiques de comptage.* Sur une grille, toutes les clauses binaires sont `(¬a ∨ ¬b)` ; les littéraux positifs n'apparaissent que dans les clauses « un chat par région ». Toutes les heuristiques de comptage choisissent donc `¬x` (« pas de chat ici ») sur la même case, d'où des compteurs **identiques** pour H2s, H3s, H4s, H5s, H7s (vérifié sur une grille). Poser « pas de chat » propage peu (0,7 à 1,7 propagation par décision pour les dynamiques, contre 9 à 10 pour H0 et H1). Cette lecture est plausible, mais nous n'avons pas fait l'expérience qui la prouverait (forcer la polarité positive).
- *Surprise 2 : H0 et H1 ne passent pas à l'échelle* (9 et 10 grilles sur 12, contre 12 pour toutes les dynamiques). Le jeu commun de 7 grilles est biaisé vers les petites.
- *Surprise 3 : sur SAT, les heuristiques littéral dynamiques résolvent moins* (H3d et H7d : 13 sur 19, contre 17 pour H4d et MJd). Hypothèse : une mauvaise polarité en haut de l'arbre est payée par un sous-arbre entier, DPLL n'ayant ni redémarrage ni apprentissage.

**2. Apport d'une heuristique face à l'algorithme 2 (H0).**

| Instances        | H0                     | meilleure          | gain                              |
| ---------------- | ---------------------- | ------------------ | --------------------------------- |
| UNSAT publiques  | 552 décisions, 353 ms | H4d : 29,5 ; 27 ms | ×19 en décisions, ×13 en temps |
| SAT publiques    | 47 décisions, 49 ms   | MJs : 12 ; 13 ms   | environ ×4                       |
| petites grilles  | 39 décisions, 43 ms   | aucune             | perte (×1,5 à ×2,8 en temps)   |
| résolues sur 42 | 32                     | 39 (H4d, MJd)      | +7                                |

Une bonne heuristique améliore fortement DPLL sur les instances publiques, surtout UNSAT. Sur les grilles, la réponse dépend de la taille : plus lente sur les petites, indispensable sur les grandes. Toutes ne sont pas bonnes : H2 et H3 résolvent moins de SAT que MOMS et JW.

**3. Le recalcul dynamique vaut-il son coût ?** Il coûte : la part du temps passée dans l'heuristique passe d'environ 6 à 8 % (statique) à 9 à 25 % (dynamique) sur les instances publiques, et à 44 à 74 % sur les grilles.

| Cas             | Dynamique / statique                                                                 | Verdict                                                       |
| --------------- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| UNSAT publiques | 21 à 37 % de décisions en moins ; temps de 0,70 à 0,90 du statique                | **gagnant** partout                                     |
| SAT publiques   | décisions de 0,82 à 1,18 ; temps de 0,82 à 1,10                                   | **neutre** (bruit)                                      |
| Grilles         | visites divisées par 3 à 4 ; temps de 0,55 à 0,85 ; 12 grilles résolues contre 8 | **gagnant**, malgré 44 à 74 % de temps en heuristique |

Sur les grilles, le gain ne vient pas de choix plus pertinents (le nombre de décisions est environ égal) mais de l'**absence de retours arrière** : environ 97 pour le statique, 0,1 pour le dynamique. Le classement initial devient faux dès qu'on a affecté quelques cases ; le recalcul le corrige. Un comptage incrémental devrait supprimer l'essentiel du surcoût (piste restante après la Q6).

### Limites de la Q5

- Timeout de 10 s (60 s en compétition) : un écart d'**une** instance résolue entre deux heuristiques n'est pas significatif (une première exécution avait décalé plusieurs totaux de ±1).
- Jeux communs petits (11, 9 et 7 instances) et biaisés vers les faciles ; sur les difficiles, seul le nombre de résolues est comparable.
- Les explications des surprises 1 et 3 sont des hypothèses, pas des résultats testés.

## 8. Usage des assistants IA

Nous avons utilisé l'assistant **Claude** au cours du projet, pour :

- nous aider à écrire le code et écrire les tests ;
- nous aider à écrire les scripts de benchmark et d'analyse ;
- rédiger les brouillons des documents par question et ce rapport ;

## 9. Écarts à l'énoncé, apports originaux, parties partielles

**Écarts et choix à signaler.**

| Point                     | Énoncé                                | Nous                                      | Raison                                                                             |
| ------------------------- | --------------------------------------- | ----------------------------------------- | ---------------------------------------------------------------------------------- |
| Générateur              | N, M, K quelconques                     | N = M = K = n                             | simplification autorisée ; l'encodage et le parseur acceptent N, M, K quelconques |
| Unité / pur (algo 2)     | une affectation puis un appel récursif | boucle de propagation jusqu'à stabilité | même résultat, récursion moins profonde                                         |
| Valuation                 | ensemble partiel                        | complétée par `False`                 | le modèle DIMACS doit être complet                                               |
| Tautologies, doublons     | non traités                            | retirés avant la recherche               | sans effet sur la satisfiabilité                                                  |
| En-tête `p cnf`        | —                                      | non cru                                   | robustesse                                                                         |
| Grille sans solution (Q3) | non précisé                           | recopie puis `UNSAT`                    | choix à nous                                                                      |
| JW                        | fractions 2⁻ᵏ                         | entiers 2^(K−k)                          | mêmes comparaisons, sans arrondi                                                  |
| Timeouts                  | —                                      | 60 s (Q2), 10 s (Q5), 30 s (Q3)           | 10 s pour tenir 756 exécutions ; 60 s est la limite de compétition               |

**Partiel ou non fait.** Q6 : pas de moteur DPLL à littéraux surveillés ni d'apprentissage de clauses ; `public-03` n'est résolue par aucune configuration en 60 s. L'unicité de la solution d'une grille n'est pas testée.

**Apports originaux.** Générateur « solution d'abord » ; contrôleur de grille indépendant de l'encodage ; grille 2×3 des heuristiques H2..H7 et combinaison MOMS+JW ; deux critères de comparaison de notre choix (propagations par décision, clauses visitées) ; explication de l'identité des heuristiques statiques sur les grilles ; portefeuille parallèle avec revérification du modèle (Q6).

**Répartition du binôme.** Projet réalisé à deux sur l'ensemble des questions
