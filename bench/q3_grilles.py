"""Q3 — Temps de résolution de grilles générées (n, graine) avec dpll_v2.

Usage : python -m bench.q3_grilles > bench/q3_resultats.csv
Un processus par grille, timeout de 30 s.
"""

import multiprocessing as mp
import threading
import time

from src.meowdoku.check import verifier
from src.meowdoku.encode import encode
from src.meowdoku.generate import generate
from src.meowdoku.solve_grid import resoudre

LIMITE = 30
SEEDS = range(3)
TAILLES = (4, 6, 8, 10, 12)


def _travail(n, seed, q):
    threading.stack_size(512 * 1024 * 1024)

    def run():
        grid, _ = generate(n, seed)
        nb_vars, clauses = encode(grid)
        t0 = time.perf_counter()
        chats = resoudre(grid)
        q.put((nb_vars, len(clauses), chats is not None and not verifier(grid, chats),
               time.perf_counter() - t0))

    th = threading.Thread(target=run)
    th.start()
    th.join()


def main():
    print("n,graine,variables,clauses,solution_valide,temps_s")
    for n in TAILLES:
        for seed in SEEDS:
            q = mp.Queue()
            p = mp.Process(target=_travail, args=(n, seed, q))
            p.start()
            p.join(LIMITE)
            if p.is_alive():
                p.kill()
                print(f"{n},{seed},,,,TIMEOUT>{LIMITE}s", flush=True)
            else:
                v, c, ok, t = q.get()
                print(f"{n},{seed},{v},{c},{ok},{t:.3f}", flush=True)


if __name__ == "__main__":
    main()
