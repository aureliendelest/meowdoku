"""Q1 — Encodage d'une grille Meowdoku en CNF.

Variable x_{i,j} (« un chat en (i,j) ») ↔ entier DIMACS (i-1)*M + j.

Clauses, dans cet ordre :
  1. au moins un chat par région            (1 clause large par région)
  2. au plus un chat par ligne              (clauses binaires par paires)
  3. au plus un chat par colonne
  4. au plus un chat par région
  5. pas de chats en diagonale              (2 directions par case, chaque paire une fois)

L'adjacence horizontale/verticale n'est pas encodée à part : deux cases voisines
de cette façon partagent une ligne ou une colonne, déjà couvertes par 2 et 3.
"""

from itertools import combinations

from .grid import Grid

Clause = list[int]


def var(i: int, j: int, n_cols: int) -> int:
    """Numéro DIMACS de la variable x_{i,j} (i, j à partir de 1)."""
    return (i - 1) * n_cols + j


def cell(v: int, n_cols: int) -> tuple[int, int]:
    """Case (i, j) associée à la variable v : inverse de `var`."""
    return (v - 1) // n_cols + 1, (v - 1) % n_cols + 1


def at_most_one(variables: list[int]) -> list[Clause]:
    """Encodage par paires : C(n, 2) clauses (¬a ∨ ¬b)."""
    return [[-a, -b] for a, b in combinations(variables, 2)]


def encode(grid: Grid, redundant: bool = False) -> tuple[int, list[Clause]]:
    """Retourne (nombre de variables, clauses).

    redundant=True ajoute « au moins un chat » par ligne et par colonne quand
    N = M = K (clauses impliquées par les autres, qui peuvent aider la propagation).
    """
    n, m = grid.n_rows, grid.n_cols
    v = lambda i, j: var(i, j, m)
    clauses: list[Clause] = []

    for cases in grid.regions.values():
        clauses.append([v(i, j) for i, j in cases])

    rows = [[v(i, j) for j in range(1, m + 1)] for i in range(1, n + 1)]
    cols = [[v(i, j) for i in range(1, n + 1)] for j in range(1, m + 1)]
    for group in rows + cols:
        clauses += at_most_one(group)
    for cases in grid.regions.values():
        clauses += at_most_one([v(i, j) for i, j in cases])

    for i in range(1, n):
        for j in range(1, m + 1):
            if j < m:
                clauses.append([-v(i, j), -v(i + 1, j + 1)])
            if j > 1:
                clauses.append([-v(i, j), -v(i + 1, j - 1)])

    if redundant and n == m == len(grid.zones):
        clauses += [list(g) for g in rows + cols]

    return n * m, clauses


def to_dimacs(num_vars: int, clauses: list[Clause], comments: tuple[str, ...] = ()) -> str:
    """Texte DIMACS CNF : commentaires, en-tête `p cnf`, une clause par ligne terminée par 0."""
    out = [f"c {c}" for c in comments]
    out.append(f"p cnf {num_vars} {len(clauses)}")
    out.extend(" ".join(map(str, c)) + " 0" for c in clauses)
    return "\n".join(out) + "\n"


def decode_model(grid: Grid, model) -> set[tuple[int, int]]:
    """Cases (i, j) portant un chat, d'après un modèle (littéraux signés ou variables vraies)."""
    return {cell(l, grid.n_cols) for l in model if 0 < l <= grid.n_rows * grid.n_cols}
