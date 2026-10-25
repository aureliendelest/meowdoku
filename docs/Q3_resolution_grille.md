# Question 3 — De la grille à la solution

## 1. Problème et enjeux

Il faut un programme qui prend une grille Meowdoku et écrit un fichier solution : recopie de l'entrée, une ligne `Région ligne colonne` par région, puis la grille avec `*` (chat) et `.` (case vide).

Il n'y a pas de nouvel algorithme de recherche à inventer. Une recherche « au hasard » serait exponentielle ; un parcours case par case avec retour arrière *est* DPLL. La Q3 est donc un **assemblage** des questions précédentes :

```
grille ──parse──▶ Grid ──encode (Q1)──▶ clauses ──▶ Cnf ──dpll_v2 (Q2)──▶ modèle
                                                                            │
fichier solution ◀── mise en forme ◀── vérification ◀── cases des chats ◀───┘
```

Difficultés :

| Difficulté | Pourquoi ça compte |
|---|---|
| Une erreur d'encodage serait invisible si on ne vérifie que les clauses | la solution satisferait des clauses fausses |
| Ordre et format de la sortie | l'énoncé (figure 2) impose le format |
| Grille sans solution | l'énoncé ne dit pas quoi écrire |
| Taille des grilles | DPLL à branchement aléatoire peut devenir lent |

Exemple minuscule : la région F de la figure 1 n'a qu'une case, (6,1), variable 31. « Au moins un chat dans F » donne la clause unitaire `(x₃₁)`. DPLL l'affecte sans brancher : les petites régions se règlent d'elles-mêmes par propagation unitaire.

## 2. Décisions de conception et implémentation

Fichier : `src/meowdoku/solve_grid.py` ; usage `python -m src.meowdoku.solve_grid grille.txt [--output sortie.txt] [--dimacs grille.cnf]`.

| Décision | Alternatives écartées | Raison |
|---|---|---|
| Passer directement de `encode` à un `Cnf` en mémoire ; fichier DIMACS écrit seulement avec `--dimacs` | écrire puis relire un `.cnf` | même résultat, sans E/S inutiles ; le `.cnf` reste disponible pour tester `sat.py` |
| Résoudre avec `dpll_v2` (Q2) | écrire une recherche dédiée | DPLL fait déjà branchement et retour arrière ; propagation unitaire et heuristiques viendront de la Q4/Q6 |
| Vérifier deux fois (`resoudre`) | ne vérifier que les clauses | `verifier_modele` contrôle les clauses ; `verifier` (`check.py`) contrôle les 4 règles du jeu sur la grille, **indépendamment de l'encodage**. Une incohérence lève une erreur : on n'écrit jamais une fausse solution |
| Lignes `Région ligne colonne` dans l'ordre de `ZONES` (`positions_par_region`) | ordre de parcours de la grille | ordre de la figure 2 ; chercher la région d'une case est en O(1) (`Grid.region_of`) |
| Recopier le texte d'entrée tel quel (commentaires compris) | reconstruire avec `format_grid` | « recopie de l'entrée » demandée par l'énoncé |
| Grille sans solution : recopie de l'entrée puis la ligne `UNSAT` | rien écrire ; planter | **choix à nous** : l'énoncé ne traite pas ce cas ; `UNSAT` reprend le vocabulaire du projet |

Fonctions : `resoudre(grid)` (encodage, DPLL, décodage par `decode_model`, vérifications), `positions_par_region`, `dessiner`, `ecrire_solution`. Complexité : celle de l'encodage (O(n²) par groupe, par paires, Q1) plus celle de DPLL (exponentielle au pire cas).

Écart : le programme s'exécute dans un thread à grande pile (comme `sat.py`) à cause de la récursion de DPLL ; une erreur de lecture de grille affiche un message mais le code de sortie du processus reste 0.

## 3. Résultats et analyses

### Validation

- `python -m unittest discover -s tests -t .` : 23 tests OK. Ceux de la Q3 (`tests/test_solve_grid.py`) vérifient :
  - la figure 1 est résolue avec la solution de la figure 2 de l'énoncé (`A 3 2`, `B 2 5`, `C 1 3`, `D 5 6`, `E 4 4`, `F 6 1`) (le test compare les positions trouvées à celles de l'énoncé ; il ne prouve pas l'unicité de la solution) ;
  - le format du fichier : recopie, six lignes de dictionnaire, grille ;
  - les grilles générées pour n ∈ {1, 4, 5, 6, 7, 8, 9}, 5 graines chacune, sont toutes résolues avec une solution valide selon `verifier` ;
  - une grille 2×2 (sans solution) donne `UNSAT`.
- Pour la figure 1 : 36 variables, 408 clauses (`grids/figure1.cnf`) ; la sortie est dans `grids/figure1_solution.txt`.

### Performances

`python -m bench.q3_grilles` (`bench/q3_resultats.csv`) : grilles générées, 3 graines par taille, timeout 30 s, une exécution chacune.

| n (N=M=K) | variables | clauses | temps (s) |
|---|---|---|---|
| 4 | 16 | 99–101 | < 0,001 |
| 6 | 36 | 336–446 | 0,001 |
| 8 | 64 | 828–951 | 0,004–0,011 |
| 10 | 100 | 1 630–1 914 | 0,016–0,025 |
| 12 | 144 | 2 924–3 137 | 0,020–0,038 |

Toutes les grilles testées sont résolues, avec une solution valide, sans timeout.

### Analyse

- Les grilles Meowdoku sont des instances **faciles pour DPLL**, contrairement à certaines instances SATLIB de la Q2 : les clauses unitaires (petites régions) et la propagation réduisent fortement l'espace avant tout branchement. Nous n'avons pas mesuré le nombre de décisions ; c'est une explication plausible, à confirmer par les compteurs de la Q5.
- Le nombre de clauses varie d'une grille à l'autre pour une même taille : il dépend de la forme des régions (clauses « au plus un » par paires dans chaque région).

### Limites

- Une seule exécution par grille, trois graines par taille, et seulement jusqu'à n = 12.
- Le générateur est aléatoire et les grilles sont probablement plus faciles que celles de vrais puzzles ; les résultats ne se généralisent pas à des grilles très grandes sans mesure.
- Le cas `UNSAT` est un choix de notre part, à signaler dans la liste des écarts.
