# Partie II — Rapport

## Sommaire

| Fichier | Contenu |
|---|---|
| `P2_Q1_Q5_compilateur.md` | Questions 1 à 5 : grammaire, analyse, encodage, jonction avec le solveur |
| `P2_Q6_modelisation.md` | Question 6 : les deux modélisations de Meowdoku |

Les questions 1 à 5 sont traitées ensemble parce qu'elles décrivent les cinq étapes d'une même chaîne, et que les décisions prises à l'une contraignent les suivantes. La découpe par question reste visible dans les sous-sections.

## Exécution

Tout se lance depuis la racine du dépôt, pour que `src` (partie I) soit importable.

```bash
pip install lark

# compiler et résoudre un modèle
python -m partie_2.csp partie_2/exemples/queens.csp --solve
python -m partie_2.csp partie_2/exemples/sudoku.csp --dimacs sudoku.cnf
python -m partie_2.csp partie_2/exemples/coloring.csp --ast

# le fichier DIMACS produit se donne aussi au solveur de la partie I
python sat.py sudoku.cnf --output-model

# Meowdoku (question 6)
python -m partie_2.meowdoku grids/figure1.txt --modele cases
python -m partie_2.meowdoku grids/figure1.txt --modele positions -o m.csp
python -m partie_2.csp m.csp --solve

# tests
python -m unittest discover -s partie_2/tests -t .

# mesures de la question 6
python -m bench.p2_modeles --tailles 6 8 10 12 --graines 0 1 2 --sortie bench/p2_resultats.csv
```

Interface : celle que l'énoncé conseille, avec `-m` et le chemin complet du module (`python -m partie_2.csp` au lieu de `python csp.py`), parce que le compilateur importe le solveur de la partie I.

## Organisation des fichiers

```
partie_2/
├── syntax.py     Q2  grammaire Lark (LALR), AST, affichage
├── symbols.py    Q3  table des symboles, valeurs typées, domaines
├── ir.py         Q3  représentation intermédiaire (Case, Cmp, Glob)
├── analyze.py    Q3  analyse, déroulage des forall, simplification
├── encode.py     Q4  encodage direct, comparaisons, contraintes globales
├── tseitin.py    Q1  mise en FNC
├── dimacs.py     Q1  écriture DIMACS, correspondance nom/numéro
├── solve.py      Q5  chaîne complète, appel du solveur, retraduction
├── csp.py            ligne de commande
├── meowdoku.py   Q6  grille → modèle, les deux modélisations
├── exemples/         les quatre modèles de l'énoncé
└── tests/            88 tests
bench/p2_modeles.py Q6  mesures
```

## Écarts à l'énoncé

| Écart | Justification |
|---|---|
| **Extension : listes en compréhension** (`e for i in S where c`) | question optionnelle de l'énoncé, et seule façon d'écrire « au moins un chat par région » (question 6.4). `for` et `where` deviennent réservés. Voir `P2_Q6_modelisation.md` §2.2 |
| Interface `python -m partie_2.csp` au lieu de `python csp.py` | le compilateur importe `src` de la partie I ; signalé comme l'énoncé le demande |
| **Correction d'un bug de portabilité de la partie I** | `threading.stack_size(512 Mo)` est refusé par Windows (`ValueError`) : le solveur ne démarrait pas hors Linux. `src/optimized.py` essaie désormais plusieurs tailles décroissantes et garde la première acceptée. Comportement inchangé sous Linux, donc en compétition |
| Le solveur appelé est le mode optimisé de la partie I | c'est « notre solveur » au sens de l'énoncé ; `--mode dpll` reste accessible par le fichier DIMACS et `sat.py` |

## Questions non traitées ou partielles

- **Mesures de la question 6** : faites sur grilles 6 à 12, trois graines, sous Windows. Données brutes dans `bench/p2_resultats.csv`. Les tailles au-delà de 12 n'ont pas été explorées, le temps de compilation du modèle `positions` devenant limitant.
- **Compteur séquentiel de Sinz** : non implémenté. L'avertissement de l'énoncé sur son usage sous une négation est discuté dans `P2_Q1_Q5_compilateur.md` §2.4.
- **Encodage par ordre des domaines finis** : non implémenté.
- **Optimisation de polarité (Plaisted–Greenbaum)** : non implémentée, et pourquoi.
- **Équivalence `<->`** : non ajoutée.
- **Contraintes globales `count` et `sum`** : non ajoutées.

## Usage des assistants IA

<!-- À compléter honnêtement : c'est une obligation académique, et la soutenance
     portera sur votre capacité à expliquer chaque ligne.

     Indiquer au minimum :
     - quel assistant, pour quelles parties ;
     - ce que vous avez repris tel quel, modifié, ou réécrit ;
     - comment vous vous êtes assurés de comprendre le résultat (lecture,
       tests écrits par vous, reformulation, etc.).

     Points du code qu'il faut savoir expliquer au tableau :
     - pourquoi Tseitin plutôt que la distribution, et ce que « équisatisfiable »
       veut dire exactement (les deux sens de l'implication) ;
     - les clauses de t <-> (a et b), et pourquoi ce sont celles-là ;
     - pourquoi `clause_positive` et `clause_negative` sont mutuellement
       récursives ;
     - pourquoi la simplification est faite au vol et non en une passe séparée
       (le court-circuit) ;
     - les deux conflits LALR de la grammaire et comment ils sont résolus ;
     - pourquoi une variable bool ne coûte qu'une variable SAT ;
     - le choix entre disjonction des bonnes valeurs et conjonction des
       négations des mauvaises, pour `x <= v` ;
     - pourquoi le modèle `positions` fait moins de décisions que `cases` tout
       en étant cinq fois plus lent (question 6.3). -->
