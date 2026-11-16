"""Q6.3 a 6.5 — Comparaison des deux modelisations de Meowdoku.

Le compilateur et le solveur sont les memes pour les deux modeles : seul le
modele change. Ce script mesure, pour des grilles de taille croissante :

  - la taille de la formule (variables, clauses) ;
  - le temps de compilation (texte du modele -> FNC) ;
  - le temps de resolution et les compteurs de la question 5 de la partie I
    (decisions, retours arriere, propagations unitaires, litteraux purs) ;
  - la validite de la solution, controlee par `src.meowdoku.check.verifier`,
    qui ne connait ni le modele ni l'encodage.

Usage depuis la racine du depot :

    python -m bench.p2_modeles --tailles 6 8 10 12 --graines 0 1 2
    python -m bench.p2_modeles --tailles 6 8 --sortie bench/p2_resultats.csv

Les mesures dependent de la machine : relancer avant de citer un chiffre dans
le rapport. Une seule execution par point ; les ecarts de quelques centiemes de
seconde sont du bruit.
"""

import argparse
import csv
import sys
import time

from src.cnf import Cnf
from src.dpll import Stats, dpll_h
from src.meowdoku.check import verifier
from src.meowdoku.generate import generate

from partie_2.meowdoku import modele, noms_surs, positions_depuis_valeurs
from partie_2.solve import compiler_texte, lire_valeurs

CONFIGURATIONS = (
    ("positions", dict(forme="positions")),
    ("cases", dict(forme="cases")),
    ("cases+redondant", dict(forme="cases", redondant=True)),
    ("cases-sans-comprehension", dict(forme="cases", comprehension=False)),
)


def mesurer(grid, nom: str, options: dict, heuristique: str) -> dict:
    """Compile, resout, controle. Renvoie une ligne de resultats."""
    texte = modele(grid, **options)

    t0 = time.perf_counter()
    compilation = compiler_texte(texte)
    t_compilation = time.perf_counter() - t0

    cnf = Cnf(compilation.fnc.nb_vars, compilation.fnc.clauses)
    stats = Stats()
    t0 = time.perf_counter()
    valuation = dpll_h(cnf, heuristique, stats=stats)
    t_resolution = time.perf_counter() - t0

    ligne = {
        "modele": nom,
        "n": grid.n_rows,
        "variables": compilation.fnc.nb_vars,
        "clauses": len(compilation.fnc.clauses),
        "t_compilation": round(t_compilation, 4),
        "t_resolution": round(t_resolution, 4),
        "decisions": stats.decisions,
        "backtracks": stats.backtracks,
        "unitaires": stats.unitaires,
        "purs": stats.purs,
        "statut": "SAT" if valuation else "UNSAT",
        "valide": "",
    }
    if valuation:
        chats = positions_depuis_valeurs(lire_valeurs(compilation.encodeur, valuation),
                                         noms_surs(grid.zones))
        erreurs = verifier(grid, chats)
        ligne["valide"] = "oui" if not erreurs else f"NON: {erreurs[0]}"
    return ligne


def recherche_exhaustive(grid) -> bool:
    """Question 6.5 : existe-t-il une solution ? Par enumeration, sans solveur.

    Un chat par ligne au plus : on enumere les placements « une colonne par
    ligne », plus l'absence de chat sur une ligne. Praticable jusqu'a n = 5.
    """
    import itertools

    n, m = grid.n_rows, grid.n_cols
    choix = list(range(0, m + 1))          # 0 = pas de chat sur cette ligne
    for colonnes in itertools.product(choix, repeat=n):
        positions = {(i + 1, c) for i, c in enumerate(colonnes) if c}
        if not verifier(grid, positions):
            return True
    return False


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m bench.p2_modeles")
    ap.add_argument("--tailles", type=int, nargs="+", default=[6, 8, 10])
    ap.add_argument("--graines", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--heuristique", default="H4d", help="heuristique du solveur (partie I)")
    ap.add_argument("--sortie", default=None, help="fichier CSV (defaut : affichage seul)")
    ap.add_argument("--exhaustif", action="store_true",
                    help="compare aussi avec une recherche exhaustive (petites grilles)")
    args = ap.parse_args(argv)

    lignes = []
    for n in args.tailles:
        for graine in args.graines:
            grid, _ = generate(n, graine)
            for nom, options in CONFIGURATIONS:
                if options["forme"] == "positions" and not (n == grid.n_cols == len(grid.zones)):
                    continue
                ligne = mesurer(grid, nom, options, args.heuristique)
                ligne["graine"] = graine
                lignes.append(ligne)
                print(f"n={n:3} graine={graine} {nom:26} "
                      f"{ligne['variables']:6} vars {ligne['clauses']:8} clauses "
                      f"compil {ligne['t_compilation']:7.3f}s  "
                      f"resol {ligne['t_resolution']:7.3f}s  "
                      f"dec {ligne['decisions']:6} bt {ligne['backtracks']:6}  "
                      f"{ligne['statut']} {ligne['valide']}", flush=True)
            if args.exhaustif and n <= 5:
                print(f"   recherche exhaustive : {recherche_exhaustive(grid)}")

    if args.sortie and lignes:
        with open(args.sortie, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(lignes[0]))
            w.writeheader()
            w.writerows(lignes)
        print(f"\nResultats ecrits dans {args.sortie}", file=sys.stderr)


if __name__ == "__main__":
    main()
