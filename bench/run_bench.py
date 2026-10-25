"""Q2 — Validation + temps de dpll_v1/dpll_v2 sur instances/ (timeout par instance, processus isolé).

Usage : python -m bench.run_bench [timeout_s] > bench/q2_resultats.csv
"""

import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

from src.cnf import read_dimacs, verifier_modele
from src.dpll import dpll_v1, dpll_v2

RACINE = Path(__file__).resolve().parent.parent


def _travail(path, q):
    import threading
    threading.stack_size(512 * 1024 * 1024)

    def run():
        cnf = read_dimacs(path)
        t0 = time.perf_counter()
        r1 = dpll_v1(cnf)
        t1 = time.perf_counter()
        m = dpll_v2(cnf)
        t2 = time.perf_counter()
        ok = m is None or verifier_modele(cnf, m)
        q.put(("SAT" if r1 else "UNSAT", "SAT" if m is not None else "UNSAT", ok, t1 - t0, t2 - t1))

    th = threading.Thread(target=run)
    th.start()
    th.join()


def main():
    limite = float(sys.argv[1]) if len(sys.argv) > 1 else 60
    attendu = json.loads((RACINE / "expected.json").read_text())
    print("instance,attendu,v1,v2,modele_valide,t_v1_s,t_v2_s,verdict")
    for nom, exp in sorted(attendu.items()):
        q = mp.Queue()
        p = mp.Process(target=_travail, args=(str(RACINE / "instances" / nom), q))
        p.start()
        p.join(limite)
        if p.is_alive():
            p.kill()
            print(f"{nom},{exp},,,,,,TIMEOUT>{limite:g}s", flush=True)
            continue
        v1, v2, ok, t1, t2 = q.get()
        bon = v1 == v2 == exp and ok
        print(f"{nom},{exp},{v1},{v2},{ok},{t1:.3f},{t2:.3f},{'OK' if bon else 'ECHEC'}", flush=True)


if __name__ == "__main__":
    main()
