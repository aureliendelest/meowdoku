"""Q6 — Compare, via la CLI réelle, DPLL (Q2), H4d seul et le portefeuille (`--mode optimized`).

Usage : python -m bench.q6_optimise [timeout_s] > bench/q6_resultats.csv

Les trois configurations tournent l'une après l'autre (le portefeuille utilise 4 CPU : pas de
parallélisme entre exécutions). Temps = temps réel du processus `sat.py` (démarrage de Python,
lecture du fichier et création des processus compris), comme le mesurera la compétition.
Instances : les 41 fichiers de instances/ + 12 grilles Meowdoku (n = 12, 16, 20, 24 ; graines 10..12,
distinctes de celles de la Q5 pour ne pas évaluer sur ce qui a servi à choisir le portefeuille).
Chaque sortie est contrôlée : format exact (stdout), statut attendu, modèle qui satisfait les clauses.
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from src.cnf import Cnf, read_dimacs, verifier_modele
from src.meowdoku.encode import encode, to_dimacs
from src.meowdoku.generate import generate

RACINE = Path(__file__).resolve().parent.parent
CONFIGS = {
    "dpll": [sys.executable, str(RACINE / "sat.py"), "{f}", "--mode", "dpll", "--output-model"],
    "h4d_seul": [sys.executable, "-m", "bench.q6_optimise", "--seul", "{f}"],
    "optimized": [sys.executable, str(RACINE / "sat.py"), "{f}", "--mode", "optimized", "--output-model"],
}
TAILLES, GRAINES = (12, 16, 20, 24), (10, 11, 12)


def seul(chemin: str) -> None:
    """H4d seul, même sortie que sat.py : isole l'effet du portefeuille de celui de l'heuristique."""
    sys.path.insert(0, str(RACINE))
    from sat import afficher
    from src.dpll import dpll_h
    cnf, res = read_dimacs(chemin), []
    threading.stack_size(512 * 1024 * 1024)
    t = threading.Thread(target=lambda: res.append(dpll_h(cnf, "H4d")))
    t.start()
    t.join()
    afficher(res[0], True)


def controle(sortie: str, cnf: Cnf, attendu: str) -> bool:
    """Format exact + statut attendu + modèle valide."""
    lignes = sortie.splitlines()
    if attendu == "UNSAT":
        return lignes == ["s UNSATISFIABLE"]
    if len(lignes) != 2 or lignes[0] != "s SATISFIABLE" or not lignes[1].startswith("v ") \
            or not lignes[1].endswith(" 0"):
        return False
    lits = [int(x) for x in lignes[1].split()[1:-1]]
    return verifier_modele(cnf, {abs(l): l > 0 for l in lits})


def lancer(config: str, chemin: str, limite: float):
    cmd = [c.replace("{f}", chemin) for c in CONFIGS[config]]
    t0 = time.perf_counter()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         cwd=RACINE, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=limite)
        return out, time.perf_counter() - t0
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)  # le processus et ses solveurs fils
        p.communicate()
        return None, time.perf_counter() - t0


def main() -> None:
    if len(sys.argv) > 2 and sys.argv[1] == "--seul":
        return seul(sys.argv[2])
    limite = float(sys.argv[1]) if len(sys.argv) > 1 else 60
    attendu = json.loads((RACINE / "expected.json").read_text())
    taches = [(nom.removesuffix(".cnf"), "fichiers", exp, str(RACINE / "instances" / nom))
              for nom, exp in sorted(attendu.items())]
    with tempfile.TemporaryDirectory() as tmp:
        for n in TAILLES:
            for s in GRAINES:
                grid, _ = generate(n, s)
                nb_vars, clauses = encode(grid)
                chemin = Path(tmp) / f"grille-{n}-s{s}.cnf"
                chemin.write_text(to_dimacs(nb_vars, clauses))
                taches.append((f"grille-{n}-s{s}", "meowdoku", "SAT", str(chemin)))
        print("instance,classe,attendu,config,statut,resultat,t_s", flush=True)
        for nom, classe, exp, chemin in taches:
            cnf = read_dimacs(chemin)
            for config in CONFIGS:
                out, t = lancer(config, chemin, limite)
                if out is None:
                    print(f"{nom},{classe},{exp},{config},,TIMEOUT,{t:.2f}", flush=True)
                    continue
                statut = "SAT" if out.startswith("s SATISFIABLE") else "UNSAT"
                ok = controle(out, cnf, exp)
                print(f"{nom},{classe},{exp},{config},{statut},{'OK' if ok else 'ECHEC'},{t:.2f}", flush=True)


if __name__ == "__main__":
    main()
