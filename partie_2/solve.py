"""Q5 — La chaine complete : texte du modele -> solveur de la partie I -> valeurs.

    texte --parse--> AST --analyser--> contraintes --encoder--> FNC --resoudre--> valeurs
      (Q2)              (Q3)                          (Q4)        (partie I)      (Q5)

Le solveur est celui de la partie I, importe directement : `src.cnf.Cnf` est
une dataclass ordinaire, on la construit en memoire et il n'y a pas de fichier
temporaire a ecrire. Le fichier DIMACS reste disponible par `csp.py --dimacs`,
pour inspection ou pour `sat.py`.

A partir du modele rendu par le solveur, on retrouve la valeur de chaque
variable du modele de depart : celle des v tels que x_v est vraie.
"""

from dataclasses import dataclass

from src.cnf import Cnf, verifier_modele

from .analyze import Modele, analyser
from .dimacs import nom_de_case
from .encode import Encodeur, encoder
from .syntax import parse
from .tseitin import Fnc


@dataclass
class Compilation:
    """Tout ce que produit la compilation d'un modele."""

    modele: Modele
    fnc: Fnc
    encodeur: Encodeur


def compiler_texte(texte: str) -> Compilation:
    """Du texte d'un modele a sa FNC."""
    modele = analyser(parse(texte))
    fnc, encodeur = encoder(modele)
    return Compilation(modele, fnc, encodeur)


def resoudre(c: Compilation, jobs: int | None = None) -> list[tuple[str, str]] | None:
    """Liste `(nom de case, valeur)`, ou None si le modele est insatisfiable.

    Le modele rendu par le solveur est verifie sur les clauses avant d'etre
    traduit : une erreur de compilation ne peut pas passer pour une solution.
    `jobs=1` evite la creation de processus (utile pour les tests).
    """
    from src.optimized import resoudre as resoudre_cnf

    cnf = Cnf(c.fnc.nb_vars, c.fnc.clauses)
    if not cnf.clauses:
        modele = {}
    else:
        modele = resoudre_cnf(cnf, jobs=jobs)
        if modele is None:
            return None
        if not verifier_modele(cnf, modele):
            raise RuntimeError("le modele rendu par le solveur ne satisfait pas les clauses")
    return lire_valeurs(c.encodeur, modele)


def lire_valeurs(encodeur: Encodeur, modele: dict[int, bool]) -> list[tuple[str, str]]:
    """Pour chaque case, la valeur v telle que x_v est vraie."""
    table = encodeur.table
    sortie = []
    for case, domaine in encodeur.cases:
        choisie = None
        for v in domaine.valeurs:
            litteral = encodeur.litteraux[(case, v)]
            vrai = modele.get(abs(litteral), False) == (litteral > 0)
            if vrai:
                choisie = v
                break
        if choisie is None:          # ne devrait pas arriver : les clauses de domaine l'interdisent
            raise RuntimeError(f"aucune valeur pour {nom_de_case(table, case)}")
        sortie.append((nom_de_case(table, case), table.nom_de_valeur(domaine, choisie)))
    return sortie


def formater(valeurs: list[tuple[str, str]] | None) -> str:
    """Sortie demandee par l'enonce : statut, puis une ligne `nom = valeur`."""
    if valeurs is None:
        return "s UNSATISFIABLE\n"
    lignes = ["s SATISFIABLE"]
    lignes += [f"{nom} = {valeur}" for nom, valeur in valeurs]
    return "\n".join(lignes) + "\n"
