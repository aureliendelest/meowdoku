# Question 6 — Solveur optimisé pour la compétition

## 1. Problème et enjeux

`python sat.py instance.cnf --mode optimized` doit rendre le bon statut, avec un modèle valide, en moins de 60 s sur une machine à 4 CPU et 8 GiB, avec la bibliothèque standard seule. Le classement compte d'abord les instances **correctement** résolues, puis le temps total sur celles-ci. Une réponse fausse ne compte pas.

Ce que la Q5 nous apprend, et qui oriente tout :

| Constat de la Q5 | Conséquence |
|---|---|
| Le choix de branchement change tout (×19 en décisions sur UNSAT) | prendre la meilleure heuristique : H4d |
| Aucune heuristique n'est la meilleure partout (H0 et H1 gagnent sur les petites grilles, H4d ailleurs) | ne pas parier sur une seule |
| Sur SAT, le temps varie énormément d'une graine à l'autre | faire tourner plusieurs tirages en même temps |
| Le sujet donne 4 CPU | on peut le faire en parallèle |

Contraintes de sûreté : un timeout ne doit jamais produire de fausse réponse ; aucun message sur stdout ; pas de solveur qui continue à tourner si le programme est tué.

## 2. Décisions de conception et implémentation

### Un portefeuille de solveurs en parallèle (`src/optimized.py`)

Quatre solveurs complets tournent dans des processus séparés ; **le premier qui répond gagne**, les autres sont arrêtés.

| Solveur | Rôle |
|---|---|
| `H4d` | MOMS dynamique sur variable : la meilleure heuristique de la Q5 (39 instances sur 42 à 10 s) |
| `H1` | aucun calcul d'heuristique : pas de surcoût de recalcul sur les grandes grilles |
| `H0`, graine 1 | diversification aléatoire |
| `H0`, graine 2 | idem |

Pourquoi ce choix plutôt qu'un modèle par taille de grille : `sat.py` ne reçoit qu'un fichier CNF, pas la grille ; détecter « c'est une grille » à partir des clauses est fragile ; et deviner la bonne stratégie avant de résoudre est moins sûr que de les laisser courir en parallèle.

**Pourquoi c'est correct.** Tous les solveurs sont complets (DPLL_H de la Q4) : un `UNSAT` de l'un est valable, et un modèle `SAT` est **revérifié** dans le processus parent sur les clauses d'origine avant d'être rendu (`verifier_modele`). Un solveur qui meurt (récursion, mémoire) n'empêche pas les autres de répondre ; si tous meurent, le programme échoue au lieu de deviner.

**Détails d'implémentation.**
- `fork` lorsque disponible (démarrage quasi instantané, le CNF n'est pas recopié par sérialisation). Le nombre de solveurs est `min(4, nombre de CPU)`, dans l'ordre de priorité du tableau.
- Chaque fils travaille dans un thread à pile de 512 Mo (la récursion de DPLL peut atteindre le nombre de variables).
- **Pas d'orphelins** : un fil de surveillance dans chaque solveur quitte si le parent disparaît (timeout de l'infrastructure, SIGTERM). Vérifié : aucun processus restant après le benchmark.
- Dans `sat.py`, le mode `optimized` s'exécute dans le thread principal (on évite de forker depuis un programme multi-thread) ; le mode `dpll` garde son thread à grande pile. Sans `--mode`, on utilise le mode optimisé. Stdout ne reçoit que `s …` et `v … 0`.

### Alternatives écartées

| Alternative | Pourquoi pas |
|---|---|
| Un modèle par taille de grille | voir ci-dessus : le solveur ne voit pas la grille |
| Moteur sans copie de formule (surveillance de 2 littéraux, pile d'affectations) | gain probablement le plus grand, mais long à écrire et à valider ; non fait faute de temps |
| CDCL (apprentissage de clauses) | trop risqué pour la date de rendu ; la correction prime |
| Portefeuille plus large que 4 | on ne dispose que de 4 CPU |

### Choix du portefeuille : une réserve

Les quatre membres ont été choisis avec les données de la Q5 (H4d seul résout 39 instances, `H0` graine 1 ajoute `public-12` et `public-27` à 10 s). Les instances publiques servent donc à la fois à choisir et à évaluer : le résultat sur elles est **optimiste**. Les 12 grilles du benchmark ci-dessous utilisent des graines (10 à 12) distinctes de celles de la Q5 et sont, elles, indépendantes du choix.

## 3. Résultats et analyses

### Protocole (`bench/q6_optimise.py`)

- 53 instances : les 41 fichiers de `instances/` et 12 grilles Meowdoku (n = 12, 16, 20, 24 ; graines 10 à 12).
- Trois configurations lancées **par la vraie CLI** : `dpll` (`--mode dpll`, algorithme 2), `h4d_seul` (H4d dans un seul processus) et `optimized` (le portefeuille). Elles s'exécutent l'une après l'autre.
- Temps réel du processus `sat.py` (démarrage de Python, lecture, création des processus compris), timeout de 60 s, processus et fils tués en cas de dépassement.
- Chaque sortie est contrôlée : format exact, statut attendu, modèle qui satisfait toutes les clauses.

### Résultats

**0 réponse fausse ou mal formée** sur les 159 exécutions. Fichiers : `bench/q6_resultats.csv` (brut), `bench/q6_synthese.md` (tableaux).

| Configuration | Fichiers (41) | Grilles (12) | Total (53) |
|---|---|---|---|
| `dpll` (algo 2) | 38 | 10 | 48 |
| `h4d_seul` | 40 | 12 | 52 |
| `optimized` | 40 | 12 | 52 |

Temps sur les 48 instances résolues par les trois configurations :

| Configuration | Temps total (s) | Médiane (s) | Plus lente (s) |
|---|---|---|---|
| `dpll` | 78,4 | 0,15 | 33,4 |
| `h4d_seul` | 16,6 | 0,08 | 4,4 |
| `optimized` | 10,0 | 0,09 | 2,0 |

Les cas qui différencient les configurations (T = timeout, s) :

| Instance | `dpll` | `h4d_seul` | `optimized` |
|---|---|---|---|
| public-03 (UNSAT) | T | T | T |
| public-12 (SAT) | T | 11,4 | 1,9 |
| public-27 (SAT) | T | 12,2 | 3,5 |
| grille 24, graine 10 | T | 2,1 | 1,1 |
| grille 24, graine 11 | T | 3,8 | 5,8 |

### Analyse

1. **L'essentiel du gain vient de l'heuristique, pas du parallélisme.** `h4d_seul` passe de 48 à 52 instances et divise le temps par 4,7 (78,4 s → 16,6 s) face à l'algorithme 2. Le portefeuille ne résout pas plus d'instances à 60 s que H4d seul (52 contre 52).
2. **Le portefeuille réduit le temps** : 10,0 s contre 16,6 s sur les 48 instances communes (environ −40 %), et surtout il raccourcit les cas durs : `public-12` passe de 11,4 s à 1,9 s et `public-27` de 12,2 s à 3,5 s. À 10 s, cela aurait fait la différence entre résolu et non résolu (Q5). Nous n'avons pas mesuré *quel* membre gagne sur chaque instance ; l'explication par la diversification (H1, graines de H0) est cohérente avec la Q5 mais n'est pas prouvée.
3. **Pas de surcoût visible sur les instances triviales** : médiane de 0,070 s contre 0,080 s pour `dpll` (29 instances sous 0,5 s), démarrage des processus compris.
4. **Le portefeuille n'est pas toujours plus rapide** : sur la grille 24 graine 11, 5,8 s contre 3,8 s pour H4d seul. Hypothèse (non testée) : concurrence entre les quatre processus pour la mémoire.
5. **`public-03` reste hors de portée** de toutes les configurations en 60 s : UNSAT de 63 variables, difficile pour DPLL sans apprentissage de clauses.

### Limites

- Une exécution par (instance, configuration) : les écarts de quelques dixièmes de seconde sont du bruit.
- Machine de développement (8 cœurs), pas la machine de compétition (4 CPU). Si l'infrastructure lance plusieurs instances en même temps, le gain du portefeuille diminue, car les quatre processus se partagent les CPU. Le temps de calcul total (somme des processus) est aussi plus élevé que celui de H4d seul.
- Évaluation optimiste sur les instances publiques (voir §2) ; confirmée seulement sur les grilles de graines nouvelles, où H4d seul fait déjà 12/12.
- Marge sur la limite de 60 s : la plus lente des instances résolues prend 5,8 s ici.

### Pistes d'amélioration

1. Moteur DPLL sans copie de formule (2 littéraux surveillés, pile d'affectations, version itérative) : c'est le gain principal restant, puisque la Q5 montre 44 à 74 % du temps en recalcul de l'heuristique sur les grilles.
2. Scores MOMS tenus à jour de façon incrémentale.
3. Apprentissage de clauses (CDCL) pour des instances comme `public-03`.
4. Mesurer quel membre du portefeuille gagne, pour ajuster sa composition.
