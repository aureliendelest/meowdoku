"""Q2 — Structure CNF, parseur DIMACS et vérificateur de modèle."""

from dataclasses import dataclass, field


@dataclass
class Cnf:
    """Formule CNF : `clauses` est une liste de clauses, chaque clause une liste d'entiers signés.

    Le littéral `k` (> 0) est la variable k, `-k` sa négation. Une clause vide `[]` est fausse ;
    une formule sans clause est vraie. Les clauses sont conservées telles que lues (doublons et
    tautologies compris) : c'est `normaliser` qui les nettoie, pas le parseur.
    """

    nb_vars: int = 0
    clauses: list[list[int]] = field(default_factory=list)


def parse_dimacs(text: str) -> Cnf:
    """Lit du texte DIMACS. Tolérant : seuls les `0` terminaux délimitent les clauses.

    - lignes `c` (commentaires) ignorées, ligne `%` = fin de fichier (convention SATLIB) ;
    - une clause peut s'étaler sur plusieurs lignes, ou plusieurs clauses tenir sur une ligne ;
    - l'en-tête `p cnf V C` n'est pas cru : le nombre de variables est élargi au plus grand
      indice rencontré, le nombre de clauses est celui réellement lu.
    """
    nb_vars = 0
    clauses: list[list[int]] = []
    courante: list[int] = []
    for ligne in text.splitlines():
        ligne = ligne.strip()
        if not ligne or ligne[0] == "c":
            continue
        if ligne[0] == "%":
            break
        if ligne[0] == "p":
            parts = ligne.split()
            if len(parts) >= 3 and parts[1] == "cnf":
                nb_vars = int(parts[2])
            continue
        for tok in ligne.split():
            lit = int(tok)
            if lit == 0:
                clauses.append(courante)
                courante = []
            else:
                courante.append(lit)
    if courante:  # dernière clause sans 0 final
        clauses.append(courante)
    plus_grand = max((abs(l) for c in clauses for l in c), default=0)
    return Cnf(max(nb_vars, plus_grand), clauses)


def read_dimacs(path: str) -> Cnf:
    with open(path, encoding="utf-8") as f:
        return parse_dimacs(f.read())


def normaliser(clauses: list[list[int]]) -> list[frozenset[int]]:
    """Supprime les tautologies (conservent la satisfiabilité) et les littéraux répétés."""
    out = []
    for c in clauses:
        s = frozenset(c)
        if any(-l in s for l in s):
            continue
        out.append(s)
    return out


def verifier_modele(cnf: Cnf, modele: dict[int, bool]) -> bool:
    """Vérificateur indépendant du solveur : chaque clause d'origine a un littéral vrai."""
    return all(
        any(modele.get(abs(l), False) == (l > 0) for l in c) for c in cnf.clauses
    )
