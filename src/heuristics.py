"""Q4 — Heuristiques de branchement H0..H7 (statiques et dynamiques) et combinaison MOMS+JW.

Une heuristique est un `choisir(formule) -> littéral` : `p` signifie « affecter p à vrai »,
`-p` « affecter p à faux » (l'autre branche essaie l'opposé). `creer(nom, formule_initiale)`
construit cette fonction.

Les six heuristiques H2..H7 forment une grille :

    | portée \\ pondération | fréquence | clauses minimales | Jeroslow-Wang |
    | variable             | H2        | H4                | H6            |
    | littéral             | H3        | H5                | H7            |

Chaque case est un « score par littéral » (dict littéral -> entier) agrégé par variable
(somme des deux polarités) ou lu directement par littéral.

- Dynamique (suffixe `d`) : le score est recalculé sur la formule courante à chaque décision.
- Statique (suffixe `s`) : le classement est calculé une fois sur la formule initiale ;
  on prend ensuite le premier élément dont la variable apparaît encore dans la formule.
- `MJs` / `MJd` : combinaison originale « MOMS puis JW en départage » (clé lexicographique).

Départages : à score égal, la plus petite variable ; pour un littéral, le positif d'abord.
Les poids de Jeroslow-Wang sont des entiers (2^(K-k), K = plus grande taille de clause) :
mêmes comparaisons que 2^-k, sans erreur d'arrondi.
"""

import random
from typing import Callable

Formule = list[frozenset[int]]
Choix = Callable[[Formule], int]

NOMS = (
    ["H0", "H1"]
    + [f"H{i}{m}" for i in range(2, 8) for m in "sd"]
    + ["MJs", "MJd"]
)


# --- scores par littéral -------------------------------------------------------------------

def _compter(formule: Formule, poids) -> dict[int, int]:
    """Score de chaque littéral = somme de `poids(clause)` sur les clauses qui le contiennent."""
    s: dict[int, int] = {}
    for c in formule:
        w = poids(c)
        if w:
            for l in c:
                s[l] = s.get(l, 0) + w
    return s


def score_frequence(formule: Formule) -> dict[int, int]:
    """occ(l, F) : nombre d'occurrences de chaque littéral."""
    return _compter(formule, lambda c: 1)


def score_min(formule: Formule) -> dict[int, int]:
    """occ_k(l, F) avec k = taille minimale des clauses : occurrences dans les clauses minimales."""
    k = min(map(len, formule), default=0)
    return _compter(formule, lambda c: 1 if len(c) == k else 0)


def score_jw(formule: Formule) -> dict[int, int]:
    """Σ_k occ_k(l, F) · 2^-k, multiplié par 2^K (K = plus grande taille) pour rester entier."""
    kmax = max(map(len, formule), default=0)
    return _compter(formule, lambda c: 1 << (kmax - len(c)))


POIDS = {"freq": score_frequence, "min": score_min, "jw": score_jw}
# H2..H7 -> (portée, pondération)
GRILLE = {
    2: ("var", "freq"), 3: ("lit", "freq"),
    4: ("var", "min"), 5: ("lit", "min"),
    6: ("var", "jw"), 7: ("lit", "jw"),
}


# --- classements : littéral préféré de chaque variable / littéraux triés --------------------

def _par_variable(s: dict[int, int], variables=None) -> dict[int, tuple[int, int]]:
    """variable -> (score total, polarité). Valeur = vrai si #+ >= #- (convention de l'énoncé).

    `variables` : toutes les variables à classer (score 0 si absentes de `s`) ; par défaut
    celles qui ont un score.
    """
    out = {}
    for p in variables if variables is not None else {abs(l) for l in s}:
        pos, neg = s.get(p, 0), s.get(-p, 0)
        out[p] = (pos + neg, p if pos >= neg else -p)
    return out


def meilleur(formule: Formule, portee: str, ponderation: str) -> int:
    """Littéral à affecter selon (portée, pondération), calculé sur `formule`."""
    s = POIDS[ponderation](formule)
    if portee == "lit":
        return max(s, key=lambda l: (s[l], -abs(l), l > 0))
    v = _par_variable(s)
    p = max(v, key=lambda p: (v[p][0], -p))
    return v[p][1]


def classement(formule: Formule, portee: str, ponderation: str) -> list[int]:
    """Tous les choix possibles, du meilleur au moins bon (pour les versions statiques).

    Les variables ou littéraux de score nul (hors des clauses minimales pour H4/H5) sont placés
    en fin de classement : sinon une version statique n'aurait plus de choix une fois les
    clauses minimales initiales éliminées.
    """
    s = POIDS[ponderation](formule)
    litteraux = {l for c in formule for l in c}
    if portee == "lit":
        return sorted(litteraux, key=lambda l: (-s.get(l, 0), abs(l), l < 0))
    v = _par_variable(s, {abs(l) for l in litteraux})
    return [v[p][1] for p in sorted(v, key=lambda p: (-v[p][0], p))]


def meilleur_mj(formule: Formule) -> int:
    """MOMS puis JW : parmi les variables de score MOMS maximal, celle de meilleur score JW."""
    return classement_mj(formule)[0]


def classement_mj(formule: Formule) -> list[int]:
    moms, jw = _par_variable(score_min(formule)), score_jw(formule)
    v_jw = _par_variable(jw)
    cle = lambda p: (-moms.get(p, (0, 0))[0], -v_jw[p][0], p)  # MOMS décroissant, JW, indice
    return [v_jw[p][1] for p in sorted(v_jw, key=cle)]  # valeur : polarité majoritaire JW


# --- construction des heuristiques ---------------------------------------------------------

def _statique(ordre: list[int]) -> Choix:
    """Premier littéral du classement initial dont la variable est encore dans la formule."""
    def choisir(formule: Formule) -> int:
        presentes = {abs(l) for c in formule for l in c}
        return next(l for l in ordre if abs(l) in presentes)
    return choisir


def creer(nom: str, formule_initiale: Formule, graine: int = 0) -> Choix:
    """Heuristique `nom` (voir NOMS). `formule_initiale` ne sert qu'aux versions statiques."""
    if nom == "H0":
        rng = random.Random(graine)

        def h0(formule: Formule) -> int:
            variables = sorted({abs(l) for c in formule for l in c})  # tri : reproductible
            p = rng.choice(variables)
            return p if rng.random() < 0.5 else -p
        return h0
    if nom == "H1":  # première variable libre, valeur 1
        return lambda formule: min(abs(l) for c in formule for l in c)
    if nom in ("MJs", "MJd"):
        return meilleur_mj if nom == "MJd" else _statique(classement_mj(formule_initiale))
    if nom in NOMS:
        portee, pond = GRILLE[int(nom[1])]
        if nom[2] == "d":
            return lambda formule: meilleur(formule, portee, pond)
        return _statique(classement(formule_initiale, portee, pond))
    raise ValueError(f"heuristique inconnue : {nom} (attendu : {', '.join(NOMS)})")
