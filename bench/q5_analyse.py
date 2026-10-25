"""Q5 — Tableaux de synthèse (Markdown) à partir de bench/q5_resultats.csv.

Usage : python -m bench.q5_analyse [bench/q5_resultats.csv] > bench/q5_synthese.md

Règle (CLAUDE.md §9) : les moyennes ne portent que sur les instances résolues par TOUTES les
heuristiques comparées (jeu « commun »), jamais sur un mélange de résolues et de timeouts ;
les timeouts sont comptés à part. Moyennes géométriques (les valeurs s'étalent sur plusieurs
ordres de grandeur). H0 : moyenne géométrique de ses 3 graines, exigée résolue pour les 3.
"""

import csv
import sys
from collections import defaultdict
from math import exp, log
from pathlib import Path

from src.heuristics import NOMS

CHEMIN = Path(__file__).resolve().parent / "q5_resultats.csv"
NUM = ("decisions", "backtracks", "unitaires", "purs", "conflits",
       "visites", "visites_heuristique", "t_cpu_s", "t_heuristique_s")


def gmean(xs):
    xs = [max(x, 1e-9) for x in xs]
    return exp(sum(map(log, xs)) / len(xs))


def charger(chemin):
    """{(instance, heuristique): [lignes]} ; lignes numériques converties, None si timeout."""
    donnees = defaultdict(list)
    meta = {}
    for r in csv.DictReader(open(chemin, encoding="utf-8")):
        meta[r["instance"]] = (r["classe"], r["attendu"])
        if r["resultat"] == "TIMEOUT":
            donnees[(r["instance"], r["heuristique"])].append(None)
        else:
            donnees[(r["instance"], r["heuristique"])].append(
                {k: float(r[k]) for k in NUM} | {"resultat": r["resultat"]})
    return donnees, meta


def resolue(donnees, inst, h):
    runs = donnees.get((inst, h), [])
    return bool(runs) and all(r is not None for r in runs)


def agreger(donnees, inst, h, champ):
    """Valeur de `champ` pour (instance, heuristique) : moyenne géométrique sur les graines."""
    return gmean([r[champ] for r in donnees[(inst, h)]])


def main():
    chemin = sys.argv[1] if len(sys.argv) > 1 else CHEMIN
    donnees, meta = charger(chemin)
    groupes = {
        "public SAT": [i for i, (c, e) in meta.items() if c == "public" and e == "SAT"],
        "public UNSAT": [i for i, (c, e) in meta.items() if c == "public" and e == "UNSAT"],
        "Meowdoku": [i for i, (c, _) in meta.items() if c == "meowdoku"],
    }
    echecs = [(i, h) for (i, h), rs in donnees.items() for r in rs if r and r["resultat"] != "OK"]
    print(f"Exécutions en ECHEC (statut ou modèle faux) : {len(echecs)} {echecs[:5]}\n")

    print("## Instances résolues (sur le timeout)\n")
    print("| heuristique | " + " | ".join(f"{g} ({len(v)})" for g, v in groupes.items()) + " | total |")
    print("|---|" + "---|" * (len(groupes) + 1))
    for h in NOMS:
        cases = [sum(resolue(donnees, i, h) for i in v) for v in groupes.values()]
        print(f"| {h} | " + " | ".join(map(str, cases)) + f" | {sum(cases)} |")

    non_resolues = {i: sum(not resolue(donnees, i, h) for h in NOMS) for i in meta}
    print("\nInstances non résolues par au moins une heuristique (nombre d'heuristiques en timeout sur 16) :")
    print(", ".join(f"{i} : {n}" for i, n in non_resolues.items() if n))

    print("\n## Détail Meowdoku — temps CPU (ms), T = timeout\n")
    choix = ["H0", "H1", "H2s", "H2d", "H4d", "H6d", "MJd"]
    print("| grille | " + " | ".join(choix) + " |")
    print("|---|" + "---|" * len(choix))
    for i in groupes["Meowdoku"]:
        cel = [f"{agreger(donnees, i, h, 't_cpu_s') * 1000:.0f}" if resolue(donnees, i, h) else "T" for h in choix]
        print(f"| {i} | " + " | ".join(cel) + " |")

    for g, inst in groupes.items():
        commun = [i for i in inst if all(resolue(donnees, i, h) for h in NOMS)]
        print(f"\n## {g} — jeu commun : {len(commun)}/{len(inst)} instances résolues par les 16 heuristiques\n")
        if not commun:
            continue
        print("| heuristique | décisions | backtracks | unitaires/décision | visites | + visites heur. "
              "| t CPU (ms) | part du temps en heuristique |")
        print("|---|---|---|---|---|---|---|---|")
        for h in NOMS:
            dec = gmean([agreger(donnees, i, h, "decisions") for i in commun])
            bt = gmean([agreger(donnees, i, h, "backtracks") for i in commun])
            ppd = gmean([agreger(donnees, i, h, "unitaires") / max(agreger(donnees, i, h, "decisions"), 1)
                         for i in commun])
            vis = gmean([agreger(donnees, i, h, "visites") for i in commun])
            vh = gmean([agreger(donnees, i, h, "visites_heuristique") for i in commun])
            t = gmean([agreger(donnees, i, h, "t_cpu_s") for i in commun])
            th = sum(agreger(donnees, i, h, "t_heuristique_s") for i in commun)
            tt = sum(agreger(donnees, i, h, "t_cpu_s") for i in commun)
            print(f"| {h} | {dec:.1f} | {bt:.1f} | {ppd:.2f} | {vis:.0f} | {vh:.0f} "
                  f"| {t * 1000:.1f} | {100 * th / tt:.1f} % |")

        print("\nStatique (s) contre dynamique (d), même jeu commun — rapport d/s (< 1 : le dynamique gagne) :\n")
        print("| paire | décisions | visites (heur. incluses) | t CPU |")
        print("|---|---|---|---|")
        for k in list(range(2, 8)) + ["J"]:
            s, d = (f"H{k}s", f"H{k}d") if k != "J" else ("MJs", "MJd")
            r = lambda h, ch: gmean([agreger(donnees, i, h, ch) for i in commun])
            tot = lambda h: gmean([agreger(donnees, i, h, "visites") + agreger(donnees, i, h, "visites_heuristique")
                                   for i in commun])
            print(f"| {d} / {s} | {r(d, 'decisions') / r(s, 'decisions'):.2f} "
                  f"| {tot(d) / tot(s):.2f} | {r(d, 't_cpu_s') / r(s, 't_cpu_s'):.2f} |")


if __name__ == "__main__":
    main()
