# Question 2 — Parseur DIMACS et DPLL (versions 1 et 2)

## 1. Problème et enjeux

Trois tâches : (1) lire un fichier DIMACS et le traduire en structure Python ; (2) implémenter DPLL en version 1 (réponse SAT/UNSAT) et version 2 (SAT avec une valuation) ; (3) les valider sur les fichiers fournis et commenter les performances.

**Lire un fichier, ce n'est pas écrire une fonction.** Une première idée était de transformer le fichier en fonction « liste de 0/1 → formule satisfaite ? ». Elle est écartée : DPLL ne teste pas des affectations complètes (2ⁿ possibilités). Il *lit* la formule pour retirer des clauses, retirer des littéraux et repérer les clauses unitaires et les littéraux purs. Il faut donc des **données**. Le test « cette affectation satisfait-elle la formule ? » existe quand même, comme vérificateur de modèle.

Difficultés :

| Difficulté | Exemple | Pourquoi ça compte |
|---|---|---|
| Format DIMACS souple | clause sur plusieurs lignes ; plusieurs clauses sur une ligne ; en-tête `p cnf` faux | un parseur naïf lit de travers sans erreur visible |
| Cas limites logiques | aucune clause (vrai) ; clause vide `0` (faux) ; tautologie `1 -1` ; littéraux répétés | une réponse fausse ne compte pas dans le classement |
| Valuation complète | variable éliminée par pureté, ou absente de toutes les clauses | le modèle doit donner une valeur à chaque variable |
| Récursion | profondeur jusqu'au nombre de variables (1363 au plus ici) | limite de pile de Python |
| Performance | arbre de recherche exponentiel au pire cas | certaines instances dépassent 60 s |

## 2. Décisions de conception et implémentation

### Structure de données (`src/cnf.py`)

Une formule est `Cnf(nb_vars: int, clauses: list[list[int]])`. Une clause est une liste d'entiers signés : `3` pour x₃, `-3` pour ¬x₃ (convention DIMACS).

```
p cnf 3 2          →  Cnf(nb_vars=3, clauses=[[1, -2], [2, 3]])
1 -2 0
2 3 0
```

| Choix envisagé | Décision | Raison |
|---|---|---|
| Clause = dict `variable → 0/1` | écarté | `(x₁ ∨ ¬x₁)` a deux fois la clé 1 ; confusion avec la valeur 0/1 donnée à une variable |
| Clause = entiers signés | **retenu** | la polarité est dans le signe ; x et ¬x peuvent coexister |
| Formule = set de clauses | écarté | un `set` ne contient que des objets hashables (il faudrait des `frozenset`) ; il fusionne les doublons et perd l'ordre |
| Formule = liste de clauses | **retenu** | simple ; accepte la clause vide `[]` |

### Parseur (`parse_dimacs`, `read_dimacs`)

Une seule boucle sur les *mots* (tokens) de chaque ligne, avec une clause « en cours » :

1. ligne `c…` : ignorée ; ligne `%` : fin de fichier (convention SATLIB) ; ligne `p cnf V C` : on retient V ;
2. pour chaque nombre : `0` ferme la clause en cours et la range (même si elle est vide, c'est la clause vide) ; sinon on l'ajoute à la clause en cours ;
3. si une clause reste ouverte en fin de fichier (pas de `0` final), on la range.

L'en-tête n'est **pas cru** : `nb_vars` est le maximum entre V et le plus grand indice lu, et le nombre de clauses est celui réellement lu. Le parseur conserve les clauses telles quelles ; le nettoyage est fait à part par `normaliser` (suppression des tautologies, qui préserve la satisfiabilité, et des littéraux répétés). Complexité : linéaire en la taille du fichier.

### DPLL (`src/dpll.py`)

La formule est une liste de `frozenset` (test d'appartenance en O(1)). Trois briques :

- `simplifier(F, l)` = F[l←1] : retire les clauses contenant `l`, retire `-l` des autres. Une clause qui devient vide signale un conflit.
- `_propager(F, modèle)` : répète jusqu'à stabilité : clause vide → conflit ; clause unitaire `{l}` → on affecte `l` ; littéral pur (son opposé n'apparaît nulle part) → on l'affecte. Chaque littéral forcé est écrit dans le modèle.
- `_choix_aleatoire(F, rng)` = `RandomChoice` de l'algo 2 : une variable tirée au hasard parmi celles de F, une valeur tirée au hasard. Les variables sont triées avant le tirage, pour que le résultat dépende seulement de la graine.
- `_dpll(F, modèle, rng)` : propage ; formule vide → SAT ; sinon on branche sur `(p, b)` (branche *then* F[p←b]), puis sur `(p, ¬b)` (branche *else*). On travaille sur une copie du modèle dans chaque branche et on ne la recopie que si la branche réussit.

Le `UNSAT` d'une unité ou d'un pur est correct sans second choix : ces affectations sont forcées (le pur ne préserve que la satisfiabilité, ce qui suffit à DPLL).

- `dpll_v1(cnf, graine=0) → bool` : SAT/UNSAT seulement.
- `dpll_v2(cnf, graine=0) → dict | None` : valuation complète pour les variables 1..n, `None` si UNSAT. Les variables non affectées (pures éliminées, ou absentes) reçoivent `False`.

Les deux versions partagent la même fonction de recherche (v2 garde simplement le modèle). La récursion est autorisée jusqu'à 100 000 niveaux, et `sat.py` s'exécute dans un thread à grande pile (512 Mo).

### Vérificateur (`verifier_modele`)

Vérifie sur les clauses **d'origine** (avant `normaliser`) que chacune contient un littéral vrai. Il est indépendant du solveur.

### CLI (`sat.py`)

`python sat.py instance.cnf [--mode dpll|optimized] [--output-model]` : écrit `s SATISFIABLE`/`s UNSATISFIABLE` et, si demandé, `v … 0` sur stdout seulement. `--mode dpll` lance ce DPLL ; `--mode optimized` lance le portefeuille de la Q6 (voir `docs/Q6_optimise.md`).

### Conformité à l'énoncé (algorithmes 1 et 2 relus dans le PDF)

| Point | Énoncé | Notre code |
|---|---|---|
| Ordre des tests | clause vide, formule vide, unité, pur, choix | identique |
| Unité / pur | une affectation puis un appel récursif | une boucle de propagation jusqu'à stabilité dans un seul appel : même résultat, récursion moins profonde |
| Choix (ligne 17) | `RandomChoice` : variable et valeur aléatoires | identique, graine fixée (`graine=0`) pour la reproductibilité |
| Branche *else* | F[p←¬b] | identique |
| Valuation | ensemble partiel d'associations `p←1`/`p←0` | complétée par `False` pour toutes les variables 1..n : extension voulue, le modèle DIMACS doit être complet |
| Tautologies, littéraux répétés | non traités | retirés avant la recherche (`normaliser`), sans effet sur la satisfiabilité |

Premier jet : nous avions d'abord branché sur le premier littéral de la première clause (déterministe) sans avoir relu l'énoncé. Nous l'avons remplacé par le tirage aléatoire demandé. Ce changement a modifié fortement les temps (voir §3), ce qui montre la sensibilité de DPLL au choix de branchement.

Le timeout de 60 s est une valeur que nous avons reprise de la compétition (Q6) ; l'énoncé n'en impose aucun pour la Q2.

## 3. Résultats et analyses

### Validation

- `tests/test_instances.py` (12 tests, tous OK) couvre le parseur (en-tête incohérent, clause multi-lignes, clause vide, indice au-delà de l'en-tête, normalisation), les instances rapides (statut, modèle complet et valide) et la CLI. *Correction : ces tests ont été écrits avec la Q6 ; le fichier n'était jusque-là qu'un squelette vide, contrairement à ce que cette section affirmait.*
- `python -m bench.run_bench 60` : v1 et v2 sur les 41 instances, timeout 60 s, un processus par instance. Résultat brut : `bench/q2_resultats.csv`.
- **38 instances sur 41 résolues**, toutes avec le statut de `expected.json` ; v1 et v2 sont d'accord, et chaque modèle SAT satisfait toutes les clauses d'origine. Les 6 cas `edge_*` sont corrects.
- **3 timeouts à 60 s** (graine 0) : public-03 (UNSAT), public-12 et public-27 (SAT). Ce sont des non-réponses, pas des réponses fausses.

### Performances

Une seule exécution par instance, graine 0, sur une seule machine. Les tirages aléatoires rendent les temps très variables d'une graine à l'autre : **ces chiffres illustrent, ils ne sont pas des moyennes**.

| Instance | Variables | Clauses | Statut | v1 (s) | v2 (s) |
|---|---|---|---|---|---|
| public-07 | 225 | 1 280 | SAT | 0,02 | 0,02 |
| public-30 | 100 | 850 | UNSAT | 1,07 | 1,05 |
| public-22 | — | — | UNSAT | 1,24 | 1,24 |
| public-18 | 459 | 7 054 | SAT | 7,33 | 7,37 |
| public-19 | 729 | 22 060 | SAT | 8,33 | 8,34 |
| public-11 | 729 | 21 844 | SAT | 24,48 | 24,04 |
| public-03 | 63 | 168 | UNSAT | >60 | >60 |
| public-12 | 522 | 11 636 | SAT | >60 | >60 |
| public-27 | 181 | 3 151 | SAT | >60 | >60 |

Lecture :

1. **v1 ≈ v2** : construire la valuation ne coûte presque rien. Le coût est dans la recherche.
2. **La taille ne prédit pas le temps.** public-03 (63 variables) ne se résout pas en 60 s alors que public-19 (729 variables, 22 060 clauses) prend 8 s.
3. **Sensibilité au branchement.** Avec notre premier choix déterministe (premier littéral de la première clause), public-07 timeoutait, public-11 prenait 0,9 s et public-27 4,7 s. Avec le tirage aléatoire, public-07 prend 0,02 s, public-11 24 s et public-27 timeoute. Une même instance passe de 0,02 s à plus de 60 s selon la stratégie de branchement : c'est la motivation des heuristiques de la Q4. (Comparaison de deux stratégies à une graine ; pas une étude de variance.)
4. **Les UNSAT sont exposées** : il faut fermer tout l'arbre. C'est cohérent avec public-03, mais le nombre de nœuds n'a pas été mesuré.

### Causes probables du coût (non mesurées)

1. Branchement aléatoire, sans heuristique → Q4.
2. `simplifier` recopie toute la formule à chaque affectation, et la recherche des purs reparcourt toute la formule à chaque tour → structures incrémentales en Q6.
3. Aucune mémoire des conflits (pas d'apprentissage).

Pour passer de l'hypothèse à la preuve, il faut les compteurs de la Q5 (décisions, retours arrière, propagations).

### Limites

- Une exécution par instance et une seule graine ; pas de moyenne. À refaire avec plusieurs graines en Q5.
- Le temps de la machine de compétition (4 CPU, 60 s) peut différer de celui de notre machine.
- La Q2 n'a pas de solution aux 3 instances en timeout : elles servent de cible pour les heuristiques (Q4) et l'optimisation (Q6).
