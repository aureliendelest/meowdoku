"""Q6 — Solveur optimisé de `--mode optimized` : portefeuille de DPLL_H en parallèle.

Plusieurs solveurs complets tournent dans des processus séparés ; le premier qui répond gagne
et les autres sont arrêtés. Tous sont complets : un `UNSAT` de n'importe lequel est valable, et
un modèle `SAT` est revérifié ici sur les clauses d'origine avant d'être rendu.

Portefeuille (cf. docs/Q6_optimise.md) :
- H4d : MOMS dynamique sur variable, la meilleure heuristique de la Q5 (39 instances sur 42) ;
- H1  : sans calcul, pas de surcoût de recalcul sur les grandes grilles ;
- H0 (graines 1 et 2) : diversification aléatoire. Sur SAT, le temps varie énormément d'une
  graine à l'autre (queue lourde) : plusieurs tirages en parallèle en coupent la queue.
Le nombre de solveurs lancés est min(4, nombre de CPU) ; l'ordre ci-dessus est l'ordre de priorité.
"""

import multiprocessing as mp
import os
import queue
import threading
import time

from .cnf import Cnf, verifier_modele
from .dpll import dpll_h

PORTEFEUILLE = (("H4d", 0), ("H1", 0), ("H0", 1), ("H0", 2))
PILE = 512 * 1024 * 1024  # la récursion de DPLL peut descendre jusqu'au nombre de variables


def _surveiller_parent(parent: int) -> None:
    """Quitte si le parent disparaît (timeout, SIGTERM) : pas de solveur orphelin qui tourne."""
    while True:
        time.sleep(0.5)
        if os.getppid() != parent:
            os._exit(0)


def _travail(cnf: Cnf, heuristique: str, graine: int, rang: int, q) -> None:
    threading.Thread(target=_surveiller_parent, args=(os.getppid(),), daemon=True).start()
    threading.stack_size(PILE)

    def run():
        try:
            q.put((rang, "ok", dpll_h(cnf, heuristique, graine)))
        except BaseException as e:  # RecursionError, MemoryError… : les autres continuent
            q.put((rang, "erreur", repr(e)))

    th = threading.Thread(target=run)
    th.start()
    th.join()


def resoudre(cnf: Cnf, portefeuille=PORTEFEUILLE, jobs: int | None = None) -> dict[int, bool] | None:
    """Valuation complète (variables 1..n) ou None si UNSAT. Même contrat que `dpll_v2`."""
    jobs = min(len(portefeuille), jobs or min(4, os.cpu_count() or 1))
    portefeuille = portefeuille[:jobs]
    if jobs == 1:  # pas de processus à créer
        return dpll_h(cnf, *portefeuille[0])
    # fork si possible (démarrage quasi instantané, pas de copie du CNF par pickle)
    ctx = mp.get_context("fork" if "fork" in mp.get_all_start_methods() else None)
    q = ctx.Queue()
    procs = [ctx.Process(target=_travail, args=(cnf, h, g, i, q), daemon=True)
             for i, (h, g) in enumerate(portefeuille)]
    for p in procs:
        p.start()
    try:
        restants = len(procs)
        while restants:
            try:
                rang, etat, valeur = q.get(timeout=0.2)
            except queue.Empty:
                if not any(p.is_alive() for p in procs) and q.empty():
                    break  # tous morts sans répondre (mémoire…) : on ne devine rien
                continue
            if etat == "ok" and (valeur is None or verifier_modele(cnf, valeur)):
                return valeur
            restants -= 1  # erreur ou modèle invalide (ne devrait pas arriver) : on attend les autres
        raise RuntimeError("aucun solveur du portefeuille n'a répondu")
    finally:
        for p in procs:
            if p.is_alive():
                p.terminate()
        for p in procs:
            p.join(1)
