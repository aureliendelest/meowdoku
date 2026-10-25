"""Q1 — Lecture/écriture des fichiers de grille Meowdoku (format GRID / ZONES).

Format :
    c commentaire
    GRID N M
    ZONES A B C ...
    N lignes de M noms de région

Les coordonnées (i, j) sont numérotées à partir de 1, comme dans l'énoncé.
"""

from dataclasses import dataclass


class GridError(ValueError):
    """Grille illicite : message explicite plutôt qu'un faux résultat SAT/UNSAT."""


@dataclass(frozen=True)
class Grid:
    """Grille Meowdoku : dimensions, noms des régions et région de chaque case."""

    n_rows: int
    n_cols: int
    zones: tuple[str, ...]                # noms des régions, dans l'ordre de ZONES
    cells: tuple[tuple[str, ...], ...]    # cells[i-1][j-1] = nom de la région de (i, j)

    def region_of(self, i: int, j: int) -> str:
        """Nom de la région de la case (i, j), numérotée à partir de 1."""
        return self.cells[i - 1][j - 1]

    @property
    def regions(self) -> dict[str, list[tuple[int, int]]]:
        """Région -> liste de ses cases (i, j), dans l'ordre de lecture."""
        out: dict[str, list[tuple[int, int]]] = {z: [] for z in self.zones}
        for i in range(1, self.n_rows + 1):
            for j in range(1, self.n_cols + 1):
                out[self.region_of(i, j)].append((i, j))
        return out


def _is_comment(line: str) -> bool:
    """Vrai si la ligne est un commentaire : 'c' seul ou suivi d'un blanc.

    Un nom de région comme « cyan » reste donc une donnée.
    """
    return line == "c" or line.startswith(("c ", "c\t"))


def parse_grid(text: str) -> Grid:
    """Analyse le texte d'une grille et la valide.

    Lève GridError si le format est incorrect, si une région est inconnue,
    dupliquée ou vide, ou si les dimensions ne correspondent pas à GRID N M.
    """
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln and not _is_comment(ln)]

    if not lines or not lines[0].startswith("GRID"):
        raise GridError("ligne 'GRID N M' manquante")
    head = lines[0].split()
    if len(head) != 3 or not (head[1].isdigit() and head[2].isdigit()):
        raise GridError(f"ligne GRID invalide : {lines[0]!r}")
    n_rows, n_cols = int(head[1]), int(head[2])
    if n_rows < 1 or n_cols < 1:
        raise GridError("les dimensions doivent être strictement positives")

    if len(lines) < 2 or not lines[1].startswith("ZONES"):
        raise GridError("ligne 'ZONES ...' manquante")
    zones = tuple(lines[1].split()[1:])
    if not zones:
        raise GridError("aucune région déclarée dans ZONES")
    if len(set(zones)) != len(zones):
        raise GridError("noms de région dupliqués dans ZONES")
    if "c" in zones:
        raise GridError("le nom de région 'c' est ambigu avec les commentaires")

    rows = lines[2:]
    if len(rows) != n_rows:
        raise GridError(f"{len(rows)} lignes de grille lues, {n_rows} attendues")
    cells = []
    for r, row in enumerate(rows, start=1):
        names = row.split()
        if len(names) != n_cols:
            raise GridError(f"ligne {r} : {len(names)} cases, {n_cols} attendues")
        unknown = [x for x in names if x not in zones]
        if unknown:
            raise GridError(f"ligne {r} : région inconnue {unknown[0]!r}")
        cells.append(tuple(names))

    used = {x for row in cells for x in row}
    empty = [z for z in zones if z not in used]
    if empty:
        raise GridError(f"région déclarée mais vide : {empty[0]!r}")

    return Grid(n_rows, n_cols, zones, tuple(cells))


def read_grid(path: str) -> Grid:
    """Lit le fichier `path` et retourne la grille validée (voir parse_grid)."""
    with open(path, encoding="utf-8") as f:
        return parse_grid(f.read())


def format_grid(grid: Grid, comments: tuple[str, ...] = ()) -> str:
    """Texte au format imposé (relisible par parse_grid)."""
    out = [f"c {c}" for c in comments]
    out.append(f"GRID {grid.n_rows} {grid.n_cols}")
    out.append("ZONES " + " ".join(grid.zones))
    out.extend(" ".join(row) for row in grid.cells)
    return "\n".join(out) + "\n"
