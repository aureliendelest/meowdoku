# Question 4 — DPLL avec heuristiques de branchement (algo 3)

## 1. Problème et enjeux

Dans l'algorithme 2, la ligne 17 choisit au hasard la variable de branchement et sa valeur. L'algorithme 3 remplace ce tirage par une fonction `Heuristics(F, H)`. Le choix compte beaucoup : sur les mêmes instances, un simple changement de stratégie de branchement a fait passer des temps de moins d'une seconde à plus de 60 s (voir `docs/Q2_dpll.md`, §3).

Exigences de l'énoncé : au moins 4 heuristiques parmi H0..H7, dont une fondée sur un littéral, une qui utilise les tailles de clauses et une dynamique ; des résultats conformes à l'algo 2 ; des choix justifiés.

Exemple minuscule : dans `(x₁ ∨ x₂) ∧ (¬x₁ ∨ x₃) ∧ (x₁ ∨ x₃)`, choisir x₁ simplifie deux clauses d'un coup, alors que choisir x₂ n'en touche qu'une. Les heuristiques cherchent à repérer ces choix « rentables ».

Difficultés :

| Difficulté | Pourquoi ça compte |
|---|---|
| Statique ou dynamique | statique : peu de calcul mais information périmée ; dynamique : à jour mais recalculée à chaque décision |
| Variable ou littéral | choisir une variable impose une valeur (polarité majoritaire) ; choisir un littéral fixe aussi la valeur |
| Une heuristique ne doit jamais changer la réponse | seul le temps doit varier ; la correction prime |
| Coquilles de l'énoncé | recopier une formule fausse produirait une heuristique fausse |

**Coquilles relevées dans l'énoncé** (à ne pas recopier telles quelles) :
- H5 : « 1 si l est de la forme p, et 1 si de la forme ¬p » → la valeur d'un littéral ¬p est **0**.
- Exemple de JW pour x₂ : le texte extrait donne « 1/2³ + 1/2² + 1/2⁴ = 7/16 » ; le calcul correct est 2⁻³ + 2⁻² + 2⁻⁴ = 7/16 (l'exposant −k est mal rendu dans le PDF).
- La contrainte « au moins une heuristique fondée sur un littéral (H3, H5 ou H6) » : H6 est définie sur une *variable* (H7 est sa version littéral). Nous retenons H3, H5 et H7 pour cette contrainte.

## 2. Décisions de conception et implémentation

### Périmètre

Nous implémentons **toutes** les heuristiques de l'énoncé, plus une combinaison originale, soit 16 variantes :

| Famille | Noms | Remarque |
|---|---|---|
| Base | H0 (aléatoire), H1 (première variable libre, valeur 1) | H1 est déterministe : elle sert de référence face à H0, qui demande plusieurs graines |
| Statiques | H2s .. H7s | classement calculé une fois sur la formule initiale |
| Dynamiques | H2d .. H7d | recalcul sur la formule courante à chaque décision |
| Combinaison | MJs, MJd | « MOMS puis JW en départage » |

Les contraintes de l'énoncé sont couvertes : littéral (H3, H5, H7), tailles de clauses (H4 à H7), dynamique (H2d à H7d, MJd).

### Une grille 2 × 3 au lieu de six heuristiques écrites à la main

H2 à H7 ne sont pas six idées différentes, mais deux choix croisés :

| portée \ pondération | fréquence | clauses minimales (MOMS) | Jeroslow-Wang |
|---|---|---|---|
| variable | H2 | H4 | H6 |
| littéral | H3 | H5 | H7 |

Fichier `src/heuristics.py` : trois fonctions de score par littéral (`score_frequence`, `score_min`, `score_jw`), chacune un dictionnaire `littéral → entier` calculé en un passage sur la formule.
- Portée *littéral* : on lit le score du littéral.
- Portée *variable* : score de la variable = score(p) + score(¬p) ; valeur vraie si score(p) ≥ score(¬p) (polarité majoritaire).

Les poids de Jeroslow-Wang sont des **entiers** `2^(K−k)` (K = plus grande taille de clause) au lieu des fractions `2^−k` : mêmes comparaisons, sans erreur d'arrondi. Les tests retrouvent bien 7/16 pour x₂ sur l'exemple de l'énoncé.

### Statique et dynamique

- **Dynamique** (`meilleur`) : le score est recalculé sur la formule courante à la décision. Une variable déjà affectée n'y figure plus.
- **Statique** (`classement`, `_statique`) : on trie une fois, sur la formule initiale, tous les choix possibles du meilleur au moins bon. À chaque décision, on prend le premier dont la variable apparaît encore dans la formule courante. Cette vérification est nécessaire : brancher sur une variable qui n'est plus dans aucune clause redouble inutilement le travail sur un sous-arbre UNSAT.
- Les variables à score nul (par exemple hors des clauses minimales initiales, pour H4 et H5) sont placées **en fin de classement**. Sans cela, un premier jet plantait quand les clauses minimales initiales avaient toutes disparu (bug trouvé et corrigé pendant le développement).

### Départages

À score égal : la plus petite variable ; pour un littéral, le positif d'abord. Ainsi chaque heuristique (hors H0) est déterministe et reproductible.

### Combinaison « MOMS puis JW en départage » (MJs, MJd)

Les deux scores ne sont pas comparables entre eux (un nombre d'occurrences contre une somme de poids) ; on ne les mélange donc pas. On trie **par ordre lexicographique**, clé `(MOMS, JW)` :
1. on garde les variables de score MOMS maximal ;
2. parmi elles, on prend celle de meilleur score JW ;
3. la valeur est la polarité majoritaire du score JW.

Exemple (testé) :

```
C1 = x1 ∨ x2   C2 = ¬x1 ∨ x3   C3 = x2 ∨ ¬x3   C4 = x1 ∨ x2 ∨ x4   C5 = x1 ∨ x3 ∨ x4
```

| Variable | MOMS (clauses de taille 2) | JW |
|---|---|---|
| x1 | 2 | 3/4 |
| x2 | 2 | 5/8 |
| x3 | 2 | 5/8 |
| x4 | 0 | 1/4 |

MOMS laisse x1, x2, x3 à égalité ; JW choisit x1, avec la valeur vrai (JW positif 1/2 contre 1/4).

**Justification.** MOMS vise les clauses les plus courtes, qui deviennent unitaires le plus vite et déclenchent la propagation. Mais il laisse souvent de nombreuses variables à égalité. JW pondère toutes les clauses par 2⁻ᵏ, donc favorise aussi les courtes tout en tenant compte des longues : il est un bon arbitre. Nous testons donc l'**hypothèse** « le départage JW améliore MOMS seul » ; la Q5 la confirmera ou non.

Un combo « H4 si clauses de taille 1 ou 2, sinon H6 » a été écarté : au moment du branchement, les clauses unitaires ont déjà été propagées (lignes 5 à 10 de l'algo 3), donc la taille minimale est ≥ 2. Pour 3-SAT et pour Meowdoku, il existe presque toujours une clause binaire, et ce combo reviendrait presque à H4 seule.

### Intégration dans DPLL (`src/dpll.py`)

`dpll_h(cnf, heuristique, graine)` est l'algorithme 3 : `creer(nom, formule_initiale, graine)` construit la fonction de choix `choisir(F) → littéral` (le littéral `p` signifie « p ← 1 », `-p` « p ← 0 »). La branche *then* essaie ce littéral, la branche *else* son opposé. `dpll_v1` et `dpll_v2` (algos 1 et 2) sont maintenant `dpll_h` avec H0, avec le même tirage aléatoire qu'avant.

### Complexité

Soit |F| le nombre total de littéraux de la formule courante.
- Dynamique : O(|F|) par décision (un passage pour les scores, un pour l'agrégation).
- Statique : prétraitement O(|F| + n log n) ; mais chaque décision construit l'ensemble des variables présentes, en O(|F|). Le gain du statique porte donc sur la constante (pas de comptage ni de tri), pas sur l'ordre de grandeur.
- Le « ratio du temps passé dans l'heuristique » demandé en Q5 mesurera ce compromis coût / pertinence.

## 3. Résultats et analyses

### Validation (tests unitaires)

`python -m unittest discover -s tests -t .` : 32 tests OK, dont ceux de `tests/test_heuristiques.py` :

| Test | Ce qu'il vérifie |
|---|---|
| Scores de l'énoncé | #(x₂)=3, #⁺=2, #⁻=1 ; seule clause de taille 2 = (x₂ ∨ x₃) ; JW(x₂) = 7/16 |
| Scores du combo | JW de x₁..x₄ = 3/4, 5/8, 5/8, 1/4 |
| Choix sur la formule de l'énoncé | H2..H7, statique et dynamique, donnent le littéral attendu (statique = dynamique à la première décision) |
| H1 | première variable, valeur vraie |
| Combo | MJs et MJd choisissent x₁ à vrai |
| H4 / H5 avec polarité négative | le littéral choisi est `-1` : valide la correction de la coquille de H5 |
| Statique et variables disparues | après affectation de x₁, une heuristique statique ne rebranche pas sur x₁ |
| **Conformité à l'algo 2** | les 16 variantes donnent le statut de `expected.json` et un modèle complet qui satisfait toutes les clauses, sur les 6 cas `edge_*`, les tests d'interface (`cli`, `smoke`, `unit`) et 15 instances `public-*` rapides |

### Limites et suite

- La conformité n'est vérifiée que sur 15 des 30 instances `public-*`, choisies parce que les 16 variantes les résolvent vite. Les instances difficiles (dont les timeouts de la Q2) seront traitées en Q5.
- **Aucune comparaison de performance n'est faite ici** : elle demande les compteurs (décisions, retours arrière, propagations, temps de l'heuristique), plusieurs graines pour H0, et la séparation SAT / UNSAT. C'est l'objet de la Q5.
- Hypothèses à tester en Q5 (non mesurées) :
  1. H4s et H5s, qui reposent sur les clauses minimales *initiales*, sont probablement moins bonnes que leurs versions dynamiques ;
  2. le départage JW améliore MOMS seul (MJd contre H4d) ;
  3. le coût du recalcul dynamique est compensé par une réduction du nombre de décisions ;
  4. lors du développement, H2s et H2d ont dépassé 3 s sur public-21 alors que les autres variantes la résolvaient en moins d'une seconde (balayage ponctuel, non reproductible par un script du dépôt) : à vérifier proprement.
