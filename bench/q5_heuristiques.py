"""Q5 — Comparaison des 16 heuristiques de dpll_h (compteurs, temps CPU) sur instances/ et grilles.

Usage : python -m bench.q5_heuristiques [timeout_s] [jobs] > bench/q5_resultats.csv

Une ligne par (instance, heuristique, graine). Un processus par exécution, tué au timeout
(mesuré en temps réel). Le temps CPU est `time.process_time` dans le processus : il ne compte
pas l'attente quand plusieurs exécutions se partagent la machine. H0 est lancée avec 3 graines.
Les instances sont les 30 `public-*` et des grilles Meowdoku générées (SAT par construction).
Colonne `resultat` : OK (statut attendu + modèle valide), ECHEC (à investiguer), TIMEOUT.
"""

import json
import multiprocessing as mp
import sys
import threading
import time
from pathlib import Path

from src.cnf import Cnf, read_dimacs, verifier_modele
from src.dpll import Stats, dpll_h
from src.heuristics import NOMS
from src.meowdoku.encode import encode
from src.meowdoku.generate import generate

RACINE = Path(__file__).resolve().parent.parent
GRAINES_H0 = (0, 1, 2)
TAILLES_GRILLES = (8, 12, 16, 20)
GRAINES_GRILLES = (0, 1, 2)
CHAMPS = ("decisions", "backtracks", "unitaires", "purs", "conflits",
          "visites", "visites_heuristique")


def instances() -> list[tuple[str, str, str, tuple]]:
    """(nom, classe, statut attendu, source) ; source = ('fichier', chemin) ou ('grille', n, graine)."""
    attendu = json.loads((RACINE / "expected.json").read_text())
    out = [(nom.removesuffix(".cnf"), "public", exp, ("fichier", str(RACINE / "instances" / nom)))
           for nom, exp in sorted(attendu.items()) if nom.startswith("public-")]
    out += [(f"grille-{n}-s{s}", "meowdoku", "SAT", ("grille", n, s))
            for n in TAILLES_GRILLES for s in GRAINES_GRILLES]
    return out


def charger(source: tuple) -> Cnf:
    if source[0] == "fichier":
        return read_dimacs(source[1])
    grid, _ = generate(source[1], source[2])
    nb_vars, clauses = encode(grid)
    return Cnf(nb_vars, clauses)


def _travail(source, heuristique, graine, q):
    threading.stack_size(512 * 1024 * 1024)

    def run():
        cnf = charger(source)
        st = Stats()
        t0 = time.process_time()
        m = dpll_h(cnf, heuristique, graine, st)
        t = time.process_time() - t0
        valide = m is None or verifier_modele(cnf, m)
        q.put(("SAT" if m is not None else "UNSAT", valide, t, st))

    th = threading.Thread(target=run)
    th.start()
    th.join()


def ligne(nom, classe, exp, h, graine, rep) -> str:
    """Ligne CSV d'un résultat `rep` = (statut, valide, t_cpu, Stats) ou None (timeout)."""
    pre = f"{nom},{classe},{exp},{h},{graine}"
    if rep is None:
        return f"{pre},,TIMEOUT" + "," * (len(CHAMPS) + 2)
    statut, valide, t, st = rep
    resultat = "OK" if statut == exp and valide else "ECHEC"
    compteurs = ",".join(str(getattr(st, c)) for c in CHAMPS)
    return f"{pre},{statut},{resultat},{compteurs},{t:.4f},{st.t_heuristique:.4f}"


def main():
    limite = float(sys.argv[1]) if len(sys.argv) > 1 else 10
    jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    taches = [(nom, classe, exp, src, h, g)
              for nom, classe, exp, src in instances()
              for h in NOMS for g in (GRAINES_H0 if h == "H0" else (0,))]
    print("instance,classe,attendu,heuristique,graine,statut,resultat," + ",".join(CHAMPS)
          + ",t_cpu_s,t_heuristique_s", flush=True)
    en_cours = []  # (processus, file, tâche, début)
    suivante = 0
    while suivante < len(taches) or en_cours:
        while suivante < len(taches) and len(en_cours) < jobs:
            nom, classe, exp, src, h, g = taches[suivante]
            q = mp.Queue()
            p = mp.Process(target=_travail, args=(src, h, g, q))
            p.start()
            en_cours.append((p, q, taches[suivante], time.perf_counter()))
            suivante += 1
        time.sleep(0.05)
        for item in list(en_cours):
            p, q, (nom, classe, exp, _, h, g), debut = item
            if not q.empty() or not p.is_alive():
                rep = q.get() if not q.empty() else None
                p.join()
                en_cours.remove(item)
                print(ligne(nom, classe, exp, h, g, rep) if rep else
                      f"{nom},{classe},{exp},{h},{g},,ECHEC" + "," * (len(CHAMPS) + 2),
                      flush=True)
            elif time.perf_counter() - debut > limite:
                p.kill()
                p.join()
                en_cours.remove(item)
                print(ligne(nom, classe, exp, h, g, None), flush=True)


if __name__ == "__main__":
    main()
