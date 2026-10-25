"""Q2/Q4/Q5 — DPLL (algos 1, 2 et 3), compteurs d'instrumentation."""

import sys
from dataclasses import dataclass
from time import process_time

from .cnf import Cnf, normaliser
from .heuristics import Choix, creer

sys.setrecursionlimit(100_000)

Formule = list[frozenset[int]]


@dataclass
class Stats:
    """Compteurs d'instrumentation (Q5). Simples incréments entiers, sans effet sur la recherche.

    - `visites` : clauses parcourues par `_propager` (scan) et `simplifier`, hors heuristique.
      Compté par `len(formule)` à l'entrée de chaque parcours (un conflit détecté en cours de scan
      compte donc la formule entière : surestimation faible).
    - `visites_heuristique` : au moins un parcours de la formule par décision (`len(formule)`) ;
      MOMS/JW en font deux, d'où une sous-estimation pour H4..H7. Indépendant de la machine,
      contrairement à `t_heuristique`.
    """
    decisions: int = 0
    backtracks: int = 0       # exécutions de la branche else (ligne 21 de l'algo 3)
    unitaires: int = 0        # propagations unitaires
    purs: int = 0             # littéraux purs
    conflits: int = 0         # clauses vides rencontrées
    visites: int = 0
    visites_heuristique: int = 0
    t_heuristique: float = 0.0  # secondes CPU (process_time, même horloge que le temps total) dans `choisir`

    @property
    def propagations_par_decision(self) -> float | None:
        """Qualité du choix : propagations unitaires déclenchées par décision (None si 0 décision)."""
        return self.unitaires / self.decisions if self.decisions else None


def simplifier(formule: Formule, lit: int) -> Formule:
    """F[lit←1] : supprime les clauses contenant `lit`, retire `-lit` des autres."""
    neg = -lit
    out = []
    for c in formule:
        if lit in c:
            continue
        out.append(c - {neg} if neg in c else c)
    return out


def _propager(formule: Formule, modele: dict[int, bool], stats: Stats):
    """Applique clauses unitaires et littéraux purs jusqu'au point fixe.

    Renvoie la formule simplifiée, ou None si une clause vide apparaît (conflit).
    Les littéraux forcés sont inscrits dans `modele`.
    """
    while True:
        if not formule:
            return formule
        unitaire = None
        presents: set[int] = set()
        stats.visites += len(formule)
        for c in formule:
            if not c:
                stats.conflits += 1
                return None
            if unitaire is None and len(c) == 1:
                unitaire = next(iter(c))
            presents |= c
        if unitaire is None:
            pur = next((l for l in presents if -l not in presents), None)
            if pur is None:
                return formule
            unitaire = pur
            stats.purs += 1
        else:
            stats.unitaires += 1
        modele[abs(unitaire)] = unitaire > 0
        stats.visites += len(formule)
        formule = simplifier(formule, unitaire)


def _dpll(formule: Formule, modele: dict[int, bool], choisir: Choix, stats: Stats) -> bool:
    formule = _propager(formule, modele, stats)
    if formule is None:
        return False
    if not formule:
        return True
    t0 = process_time()
    lit = choisir(formule)  # Heuristics(F, H) de l'algo 3 : p = |lit|, b = (lit > 0)
    stats.t_heuristique += process_time() - t0
    stats.decisions += 1
    stats.visites_heuristique += len(formule)
    for l in (lit, -lit):  # branche then F[p←b], puis else F[p←¬b]
        if l == -lit:
            stats.backtracks += 1
        essai = dict(modele)
        essai[abs(l)] = l > 0
        stats.visites += len(formule)
        if _dpll(simplifier(formule, l), essai, choisir, stats):
            modele.update(essai)
            return True
    return False


def dpll_h(cnf: Cnf, heuristique: str = "H0", graine: int = 0,
           stats: Stats | None = None) -> dict[int, bool] | None:
    """Algorithme 3 : valuation complète (variables 1..n) ou None si UNSAT.

    `heuristique` : un nom de `heuristics.NOMS` (H0 aléatoire, H1, H2s..H7d, MJs, MJd).
    `graine` ne sert qu'à H0. `stats` : objet `Stats` rempli pendant la recherche (Q5).
    """
    if stats is None:
        stats = Stats()
    formule = normaliser(cnf.clauses)
    modele: dict[int, bool] = {}
    if not _dpll(formule, modele, creer(heuristique, formule, graine), stats):
        return None
    # Variables éliminées par pureté ou absentes des clauses : valeur arbitraire (False).
    return {v: modele.get(v, False) for v in range(1, cnf.nb_vars + 1)}


def dpll_v1(cnf: Cnf, graine: int = 0) -> bool:
    """Algorithme 1 : SAT / UNSAT seulement (choix aléatoire, H0)."""
    return dpll_h(cnf, "H0", graine) is not None


def dpll_v2(cnf: Cnf, graine: int = 0) -> dict[int, bool] | None:
    """Algorithme 2 : valuation complète ou None si UNSAT (choix aléatoire, H0)."""
    return dpll_h(cnf, "H0", graine)
