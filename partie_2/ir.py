"""Q3 — Representation intermediaire : ce qui reste apres l'analyse.

L'arbre de syntaxe reflete le texte ; il contient des boucles, des tranches,
des noms a resoudre et des expressions calculables des la compilation. La
question 3 le reduit a une liste de contraintes qui ne portent plus que sur des
**cases de variables**, et c'est cette representation-la que la question 4
traduit en FNC.

Trois nouveaux noeuds suffisent :

  - `Case` : une case de variable, par exemple grid[1][2] ou b ;
  - `Cmp`  : une comparaison entre deux termes, chacun une `Case` ou une valeur
             connue (`Val`) ;
  - `Glob` : une contrainte globale, dont le nombre d'arguments est connu.

Les connecteurs (`And`, `Or`, `Not`, `Implies`) sont ceux de `syntax.py` : on
les reutilise tels quels, puisqu'ils ne changent pas de sens. Les constantes
vrai et faux sont les booleens `True` et `False` de Python ; l'analyse les
elimine au fur et a mesure, de sorte qu'elles n'apparaissent jamais dans une
contrainte conservee.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    """Une case de variable : `b` est Case('b', ()), grid[1][2] est Case('grid', (1, 2))."""

    nom: str
    indices: tuple[int, ...] = ()


@dataclass
class Cmp:
    """Comparaison entre deux termes (`Case` ou `Val`), dont au moins un est une `Case`."""

    op: str              # = != < <= > >=
    gauche: object
    droite: object


@dataclass
class Glob:
    """Contrainte globale sur un nombre connu d'arguments.

    - atLeastOne / atMostOne / exactlyOne : `args` est une liste d'expressions
      booleennes ;
    - allDifferent : `args` est une liste de termes entiers ou enumeres.
    """

    nom: str
    args: list


OPPOSE = {"=": "!=", "!=": "=", "<": ">=", ">=": "<", ">": "<=", "<=": ">"}
SYMETRIQUE = {"=": "=", "!=": "!=", "<": ">", ">": "<", "<=": ">=", ">=": "<="}
