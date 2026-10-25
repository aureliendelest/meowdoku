"""Point d'entrée imposé : python sat.py instance.cnf [--mode dpll|optimized] [--output-model].

Sortie sur stdout uniquement : `s SATISFIABLE` / `s UNSATISFIABLE` et, si demandé, `v ... 0`.
Debug sur stderr. Sans --mode, on utilise le mode optimisé.
"""

import argparse
import threading

from src.cnf import read_dimacs
from src.dpll import dpll_v2
from src.optimized import resoudre


def afficher(modele, output_model: bool) -> None:
    if modele is None:
        print("s UNSATISFIABLE")
        return
    print("s SATISFIABLE")
    if output_model:
        print("v " + " ".join(str(v if b else -v) for v, b in sorted(modele.items())) + " 0")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("instance")
    ap.add_argument("--mode", choices=["dpll", "optimized"])
    ap.add_argument("--output-model", action="store_true")
    args = ap.parse_args()
    cnf = read_dimacs(args.instance)

    if args.mode == "dpll":
        # DPLL de la Q2 (choix aléatoire). Pile large : la récursion peut descendre jusqu'au
        # nombre de variables. Un thread à part, car le mode optimisé crée des processus
        # et on évite de forker depuis un programme multi-thread.
        res = []
        threading.stack_size(512 * 1024 * 1024)
        t = threading.Thread(target=lambda: res.append(dpll_v2(cnf)))
        t.start()
        t.join()
        afficher(res[0], args.output_model)
    else:
        afficher(resoudre(cnf), args.output_model)


if __name__ == "__main__":
    main()
