"""Q1/Q5 — Ecriture de la FNC au format DIMACS.

DIMACS ne connait que des numeros. Pour pouvoir traduire le modele rendu par le
solveur dans les termes du modele de depart, la correspondance est ecrite en
commentaires, comme le suggere l'enonce :

    c var 1 queen[1]=1
    c var 2 queen[1]=2
    p cnf 64 736
    1 2 3 4 5 6 7 8 0
    ...

Chaque variable booleenne vaut « cette case prend cette valeur ». Dans la
chaine complete (`csp.py --solve`), c'est l'encodeur qui sert, pas les
commentaires : on n'ecrit rien qu'on doive ensuite relire. Les variables
auxiliaires de Tseitin n'ont pas de nom et n'apparaissent donc pas.
"""

from .encode import Encodeur
from .ir import Case
from .symbols import Table
from .tseitin import Fnc


def nom_de_case(table: Table, case: Case) -> str:
    """`grid[1][2]`, ou `row[A]` si la dimension est un type enumere."""
    entree = table[case.nom]
    morceaux = []
    for i, dim in zip(case.indices, entree.dims):
        morceaux.append(str(i) if dim.type == "int" else table[dim.type].valeurs_enum[i])
    return case.nom + "".join(f"[{m}]" for m in morceaux)


def correspondance(encodeur: Encodeur) -> list[tuple[int, str]]:
    """(numero, description) pour chaque variable nommee, dans l'ordre des numeros."""
    table = encodeur.table
    lignes = []
    for case, domaine in encodeur.cases:
        for v in domaine.valeurs:
            litteral = encodeur.litteraux[(case, v)]
            if litteral > 0:          # pour une case bool, seule la valeur vraie a un numero
                lignes.append((litteral,
                               f"{nom_de_case(table, case)}={table.nom_de_valeur(domaine, v)}"))
    return sorted(lignes)


def ecrire(fnc: Fnc, encodeur: Encodeur, commentaires: tuple[str, ...] = ()) -> str:
    """Texte DIMACS : commentaires libres, correspondance, en-tete, clauses."""
    lignes = [f"c {c}" for c in commentaires]
    lignes += [f"c var {n} {desc}" for n, desc in correspondance(encodeur)]
    lignes.append(f"p cnf {fnc.nb_vars} {len(fnc.clauses)}")
    lignes += [" ".join(map(str, clause)) + " 0" for clause in fnc.clauses]
    return "\n".join(lignes) + "\n"


def lire_correspondance(texte: str) -> dict[int, str]:
    """Numero -> description, d'apres les lignes `c var <numero> <description>`."""
    sortie = {}
    for ligne in texte.splitlines():
        mots = ligne.split()
        if len(mots) == 4 and mots[0] == "c" and mots[1] == "var":
            sortie[int(mots[2])] = mots[3]
    return sortie
