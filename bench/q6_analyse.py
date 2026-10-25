"""Q6 — Synthèse Markdown de bench/q6_resultats.csv.

Usage : python -m bench.q6_analyse > bench/q6_synthese.md

Classement de la compétition : (1) instances correctement résolues, (2) temps total sur celles-ci.
Le temps total n'est comparé que sur les instances résolues par les trois configurations.
"""

import csv
from collections import defaultdict
from pathlib import Path

CHEMIN = Path(__file__).resolve().parent / "q6_resultats.csv"
CONFIGS = ("dpll", "h4d_seul", "optimized")


def main() -> None:
    lignes = list(csv.DictReader(open(CHEMIN, encoding="utf-8")))
    res = defaultdict(dict)  # instance -> config -> (resultat, t)
    classe = {}
    for r in lignes:
        res[r["instance"]][r["config"]] = (r["resultat"], float(r["t_s"]))
        classe[r["instance"]] = r["classe"]
    groupes = {"fichiers (41)": [i for i in res if classe[i] == "fichiers"],
               "grilles (12)": [i for i in res if classe[i] == "meowdoku"]}

    echecs = [(i, c) for i in res for c, (ok, _) in res[i].items() if ok == "ECHEC"]
    print(f"Réponses fausses ou sortie mal formée (ECHEC) : {len(echecs)} {echecs}\n")
    print("## Instances correctement résolues en 60 s\n")
    print("| configuration | " + " | ".join(groupes) + " | total |")
    print("|---|" + "---|" * (len(groupes) + 1))
    for c in CONFIGS:
        n = [sum(res[i][c][0] == "OK" for i in v) for v in groupes.values()]
        print(f"| {c} | " + " | ".join(map(str, n)) + f" | {sum(n)} |")

    communes = [i for i in res if all(res[i][c][0] == "OK" for c in CONFIGS)]
    print(f"\n## Temps sur les {len(communes)} instances résolues par les trois configurations\n")
    print("| configuration | temps total (s) | médiane (s) | plus lente (s) |")
    print("|---|---|---|---|")
    for c in CONFIGS:
        ts = sorted(res[i][c][1] for i in communes)
        print(f"| {c} | {sum(ts):.1f} | {ts[len(ts) // 2]:.2f} | {ts[-1]:.1f} |")

    print("\n## Instances non résolues par au moins une configuration (T = timeout, s)\n")
    print("| instance | " + " | ".join(CONFIGS) + " |")
    print("|---|" + "---|" * len(CONFIGS))
    for i in sorted(res):
        if any(res[i][c][0] != "OK" for c in CONFIGS):
            print(f"| {i} | " + " | ".join(
                f"{res[i][c][1]:.1f}" if res[i][c][0] == "OK" else res[i][c][0][0] for c in CONFIGS) + " |")

    print("\n## Instances les plus lentes pour le mode optimized (s)\n")
    print("| instance | dpll | h4d_seul | optimized |")
    print("|---|---|---|---|")
    lentes = sorted((i for i in res if res[i]["optimized"][0] == "OK"),
                    key=lambda i: -res[i]["optimized"][1])[:8]
    for i in lentes:
        print(f"| {i} | " + " | ".join(
            f"{res[i][c][1]:.1f}" if res[i][c][0] == "OK" else "T" for c in CONFIGS) + " |")

    print("\n## Surcoût sur les instances triviales (temps réel, s)\n")
    petites = [i for i in res if classe[i] == "fichiers" and all(res[i][c][1] < 0.5 for c in CONFIGS)]
    if petites:
        print("| configuration | médiane |")
        print("|---|---|")
        for c in CONFIGS:
            ts = sorted(res[i][c][1] for i in petites)
            print(f"| {c} | {ts[len(ts) // 2]:.3f} |")
        print(f"\n({len(petites)} instances sous 0,5 s pour chaque configuration)")


if __name__ == "__main__":
    main()
