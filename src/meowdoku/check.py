"""Q1/Q3 — Contrôleur indépendant de validité d'une solution Meowdoku.

Vérifie les 4 règles directement sur la grille, sans passer par le CNF : une
erreur d'encodage ou de solveur ne peut donc pas être masquée par ce contrôle.
"""

from itertools import combinations

from .grid import Grid


def verifier(grid: Grid, positions) -> list[str]:
    """Retourne la liste des règles violées par `positions` (vide = solution valide).

    `positions` est un ensemble de cases (i, j), numérotées à partir de 1,
    qui portent un chat.
    """
    pos = sorted(set(positions))
    erreurs: list[str] = []

    for i, j in pos:
        if not (1 <= i <= grid.n_rows and 1 <= j <= grid.n_cols):
            erreurs.append(f"case hors grille : ({i}, {j})")
    if erreurs:
        return erreurs

    for axe, nom in ((0, "ligne"), (1, "colonne")):
        compte: dict[int, int] = {}
        for p in pos:
            compte[p[axe]] = compte.get(p[axe], 0) + 1
        erreurs += [f"{nom} {k} : {c} chats" for k, c in sorted(compte.items()) if c > 1]

    compte_zone = {z: 0 for z in grid.zones}
    for i, j in pos:
        compte_zone[grid.region_of(i, j)] += 1
    erreurs += [
        f"région {z} : {c} chats (1 attendu)" for z, c in compte_zone.items() if c != 1
    ]

    for (i1, j1), (i2, j2) in combinations(pos, 2):
        if max(abs(i1 - i2), abs(j1 - j2)) <= 1:
            erreurs.append(f"chats adjacents : ({i1}, {j1}) et ({i2}, {j2})")

    return erreurs
