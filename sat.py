"""Point d'entrée imposé : python sat.py instance.cnf [--mode dpll|optimized] [--output-model].

Sortie sur stdout uniquement : `s SATISFIABLE` / `s UNSATISFIABLE` et, si demandé, `v ... 0`.
Debug sur stderr.
"""

import argparse
import sys
import threading

from src.cnf import read_dimacs
from src.dpll import dpll_v2


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("instance")
    ap.add_argument("--mode", choices=["dpll", "optimized"])
    ap.add_argument("--output-model", action="store_true")
    args = ap.parse_args()
    if args.mode == "optimized":
        print("optimized pas encore implémenté (Q6) : repli sur dpll", file=sys.stderr)

    modele = dpll_v2(read_dimacs(args.instance))
    if modele is None:
        print("s UNSATISFIABLE")
        return
    print("s SATISFIABLE")
    if args.output_model:
        print("v " + " ".join(str(v if b else -v) for v, b in sorted(modele.items())) + " 0")


if __name__ == "__main__":
    # Pile large : la récursion DPLL peut descendre jusqu'au nombre de variables.
    threading.stack_size(512 * 1024 * 1024)
    t = threading.Thread(target=main)
    t.start()
    t.join()
