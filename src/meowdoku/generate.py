"""Q1 — Générateur de grilles Meowdoku solubles par construction (N = M = K = n).

Méthode « solution d'abord » :
  1. placer n chats (un par ligne et par colonne, sans adjacence diagonale)
     par backtracking aléatoire ;
  2. faire pousser n régions connexes, chacune à partir d'un chat : elle contient
     donc exactement un chat, et la grille a au moins une solution ;
  3. nommer les régions dans un ordre aléatoire (pour ne pas trahir la solution).

La construction garantit l'existence d'une solution, pas son unicité.
Il n'existe aucune solution pour n = 2 ou n = 3.

Usage : python -m src.meowdoku.generate --n 8 --seed 3 --output grids/g8.txt
"""

import argparse
import random
import sys

from .grid import Grid, format_grid

Position = tuple[int, int]


def place_cats(n: int, rng: random.Random) -> list[int] | None:
    """Colonne du chat de chaque ligne (index 0 = ligne 1), ou None s'il n'y a pas de solution.

    Contraintes : colonnes toutes distinctes et écart d'au moins 2 colonnes
    entre deux lignes consécutives (pas d'adjacence diagonale).
    """
    cols: list[int] = []

    def rec() -> bool:
        if len(cols) == n:
            return True
        candidats = list(range(1, n + 1))
        rng.shuffle(candidats)
        for c in candidats:
            if c in cols or (cols and abs(c - cols[-1]) <= 1):
                continue
            cols.append(c)
            if rec():
                return True
            cols.pop()
        return False

    return cols if rec() else None


def region_name(k: int) -> str:
    """Nom du k-ième label (k >= 0) : A..Z, puis AA, AB, ..."""
    nom = ""
    k += 1
    while k > 0:
        k, r = divmod(k - 1, 26)
        nom = chr(ord("A") + r) + nom
    return nom


def grow_regions(n: int, cats: list[Position], rng: random.Random) -> list[list[int]]:
    """Étiquette chaque case par l'indice de région (0..n-1), chaque région partant d'un chat.

    On tire au hasard une case vide voisine (4-voisinage) d'une région déjà
    construite, et on l'ajoute à cette région : les régions restent connexes.
    """
    label = [[-1] * n for _ in range(n)]
    frontier: list[tuple[int, int, int]] = []

    def etendre(i: int, j: int, r: int) -> None:
        label[i][j] = r
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = i + di, j + dj
            if 0 <= a < n and 0 <= b < n and label[a][b] == -1:
                frontier.append((a, b, r))

    for r, (i, j) in enumerate(cats):
        etendre(i - 1, j - 1, r)
    while frontier:
        k = rng.randrange(len(frontier))
        frontier[k], frontier[-1] = frontier[-1], frontier[k]
        i, j, r = frontier.pop()
        if label[i][j] == -1:
            etendre(i, j, r)
    return label


def generate(n: int, seed: int | None = None) -> tuple[Grid, set[Position]]:
    """Retourne (grille, solution connue) pour une grille n x n ; reproductible via `seed`."""
    if n != 1 and n < 4:
        raise ValueError("aucune grille n'existe pour n = 2 ou 3 (n = 1 ou n >= 4)")
    rng = random.Random(seed)
    colonnes = place_cats(n, rng)
    assert colonnes is not None
    cats = [(i + 1, c) for i, c in enumerate(colonnes)]

    label = grow_regions(n, cats, rng)
    ordre = list(range(n))
    rng.shuffle(ordre)
    noms = [region_name(ordre[r]) for r in range(n)]
    zones = tuple(sorted(noms, key=lambda x: (len(x), x)))
    cells = tuple(tuple(noms[label[i][j]] for j in range(n)) for i in range(n))
    return Grid(n, n, zones, cells), set(cats)


def main(argv: list[str] | None = None) -> None:
    """Point d'entrée en ligne de commande : écrit la grille générée (stdout ou --output)."""
    ap = argparse.ArgumentParser(description="Génère une grille Meowdoku soluble n x n.")
    ap.add_argument("--n", type=int, required=True, help="taille (N = M = K)")
    ap.add_argument("--seed", type=int, default=None, help="graine (aléatoire si omise)")
    ap.add_argument("--output", default=None, help="fichier de sortie (défaut : stdout)")
    args = ap.parse_args(argv)

    seed = args.seed if args.seed is not None else random.randrange(2**32)
    try:
        grid, _ = generate(args.n, seed)
    except ValueError as e:
        sys.exit(str(e))
    texte = format_grid(grid, (f"Grille generee : n={args.n} seed={seed}",))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(texte)
    else:
        sys.stdout.write(texte)


if __name__ == "__main__":
    main()
