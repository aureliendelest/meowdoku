"""Q3 — Grille -> DIMACS -> solveur -> fichier solution (dictionnaire + grille *).

Usage : python -m src.meowdoku.solve_grid grille.txt [--output sortie.txt] [--dimacs grille.cnf]
"""

import argparse
import sys
import threading

from ..cnf import Cnf, verifier_modele
from ..dpll import dpll_v2
from .check import verifier
from .encode import decode_model, encode, to_dimacs
from .grid import Grid, GridError, parse_grid


def positions_par_region(grid: Grid, chats) -> dict[str, tuple[int, int]]:
    """Région -> case du chat, dans l'ordre de la ligne ZONES."""
    par_region = {grid.region_of(i, j): (i, j) for i, j in chats}
    return {z: par_region[z] for z in grid.zones}


def dessiner(grid: Grid, chats) -> str:
    """Grille de `*` (chat) et `.` (case vide), une ligne par rangée."""
    chats = set(chats)
    return "\n".join(
        " ".join("*" if (i, j) in chats else "." for j in range(1, grid.n_cols + 1))
        for i in range(1, grid.n_rows + 1)
    )


def resoudre(grid: Grid) -> set[tuple[int, int]] | None:
    """Positions des chats, ou None si la grille n'a pas de solution.

    La solution est contrôlée deux fois : sur les clauses (verifier_modele) et sur les
    4 règles du jeu, indépendamment de l'encodage (verifier). Une incohérence lève une erreur.
    """
    nb_vars, clauses = encode(grid)
    cnf = Cnf(nb_vars, clauses)
    modele = dpll_v2(cnf)
    if modele is None:
        return None
    chats = decode_model(grid, [v for v, b in modele.items() if b])
    erreurs = verifier(grid, chats)
    if erreurs or not verifier_modele(cnf, modele):
        raise RuntimeError(f"solution invalide : {erreurs or 'clauses non satisfaites'}")
    return chats


def ecrire_solution(texte_entree: str, grid: Grid, chats) -> str:
    """Recopie de l'entrée, puis `Région ligne colonne` par région, puis la grille."""
    if not texte_entree.endswith("\n"):
        texte_entree += "\n"
    if chats is None:  # cas non prévu par l'énoncé : voir docs/Q3
        return texte_entree + "UNSAT\n"
    lignes = [f"{z} {i} {j}" for z, (i, j) in positions_par_region(grid, chats).items()]
    return texte_entree + "\n".join(lignes) + "\n" + dessiner(grid, chats) + "\n"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Résout une grille Meowdoku.")
    ap.add_argument("grille")
    ap.add_argument("--output", default=None, help="fichier solution (défaut : stdout)")
    ap.add_argument("--dimacs", default=None, help="écrit aussi la formule au format DIMACS")
    args = ap.parse_args(argv)

    with open(args.grille, encoding="utf-8") as f:
        texte = f.read()
    try:
        grid = parse_grid(texte)
    except GridError as e:
        sys.exit(f"grille invalide : {e}")

    if args.dimacs:
        nb_vars, clauses = encode(grid)
        with open(args.dimacs, "w", encoding="utf-8") as f:
            f.write(to_dimacs(nb_vars, clauses, (f"Meowdoku {args.grille}",)))

    sortie = ecrire_solution(texte, grid, resoudre(grid))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(sortie)
    else:
        sys.stdout.write(sortie)


if __name__ == "__main__":
    threading.stack_size(512 * 1024 * 1024)  # récursion de DPLL (voir sat.py)
    t = threading.Thread(target=main)
    t.start()
    t.join()
