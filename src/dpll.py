"""Q2/Q4/Q5 — DPLL (algos 1, 2 et 3), compteurs d'instrumentation."""

import sys

from .cnf import Cnf, normaliser
from .heuristics import Choix, creer

sys.setrecursionlimit(100_000)

Formule = list[frozenset[int]]


def simplifier(formule: Formule, lit: int) -> Formule:
    """F[lit←1] : supprime les clauses contenant `lit`, retire `-lit` des autres."""
    neg = -lit
    out = []
    for c in formule:
        if lit in c:
            continue
        out.append(c - {neg} if neg in c else c)
    return out


def _propager(formule: Formule, modele: dict[int, bool]):
    """Applique clauses unitaires et littéraux purs jusqu'au point fixe.

    Renvoie la formule simplifiée, ou None si une clause vide apparaît (conflit).
    Les littéraux forcés sont inscrits dans `modele`.
    """
    while True:
        if not formule:
            return formule
        unitaire = None
        presents: set[int] = set()
        for c in formule:
            if not c:
                return None
            if unitaire is None and len(c) == 1:
                unitaire = next(iter(c))
            presents |= c
        if unitaire is None:
            pur = next((l for l in presents if -l not in presents), None)
            if pur is None:
                return formule
            unitaire = pur
        modele[abs(unitaire)] = unitaire > 0
        formule = simplifier(formule, unitaire)


def _dpll(formule: Formule, modele: dict[int, bool], choisir: Choix) -> bool:
    formule = _propager(formule, modele)
    if formule is None:
        return False
    if not formule:
        return True
    lit = choisir(formule)  # Heuristics(F, H) de l'algo 3 : p = |lit|, b = (lit > 0)
    for l in (lit, -lit):  # branche then F[p←b], puis else F[p←¬b]
        essai = dict(modele)
        essai[abs(l)] = l > 0
        if _dpll(simplifier(formule, l), essai, choisir):
            modele.update(essai)
            return True
    return False


def dpll_h(cnf: Cnf, heuristique: str = "H0", graine: int = 0) -> dict[int, bool] | None:
    """Algorithme 3 : valuation complète (variables 1..n) ou None si UNSAT.

    `heuristique` : un nom de `heuristics.NOMS` (H0 aléatoire, H1, H2s..H7d, MJs, MJd).
    `graine` ne sert qu'à H0.
    """
    formule = normaliser(cnf.clauses)
    modele: dict[int, bool] = {}
    if not _dpll(formule, modele, creer(heuristique, formule, graine)):
        return None
    # Variables éliminées par pureté ou absentes des clauses : valeur arbitraire (False).
    return {v: modele.get(v, False) for v in range(1, cnf.nb_vars + 1)}


def dpll_v1(cnf: Cnf, graine: int = 0) -> bool:
    """Algorithme 1 : SAT / UNSAT seulement (choix aléatoire, H0)."""
    return dpll_h(cnf, "H0", graine) is not None


def dpll_v2(cnf: Cnf, graine: int = 0) -> dict[int, bool] | None:
    """Algorithme 2 : valuation complète ou None si UNSAT (choix aléatoire, H0)."""
    return dpll_h(cnf, "H0", graine)
