"""Validation du parseur, des instances fournies (expected.json) et de la CLI `sat.py`."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from src.cnf import normaliser, parse_dimacs, read_dimacs, verifier_modele
from src.dpll import dpll_v1, dpll_v2
from src.optimized import PORTEFEUILLE, resoudre

RACINE = Path(__file__).resolve().parent.parent
ATTENDU = json.loads((RACINE / "expected.json").read_text())
# Instances publiques résolues en moins d'une seconde par le DPLL de la Q2
RAPIDES = [n for n in ATTENDU if not n.startswith("public-")] + [
    f"public-{i:02d}.cnf" for i in (1, 2, 5, 7, 9, 10, 13, 14, 16, 17, 20, 23, 24, 26, 28, 29)
]


class TestParseur(unittest.TestCase):
    def test_entete_incoherent(self):
        cnf = parse_dimacs("p cnf 2 5\n1 -2 0\n3 0\n")
        self.assertEqual(cnf.nb_vars, 3)  # indice 3 au-delà de l'en-tête
        self.assertEqual(cnf.clauses, [[1, -2], [3]])  # nombre de clauses = celui lu, pas 5

    def test_clause_sur_plusieurs_lignes_et_espaces(self):
        cnf = parse_dimacs("p cnf 3 2\n1   -2\n 3 0 2\n0\n")
        self.assertEqual(cnf.clauses, [[1, -2, 3], [2]])

    def test_plusieurs_clauses_sur_une_ligne(self):
        self.assertEqual(parse_dimacs("p cnf 2 2\n1 0 -2 0\n").clauses, [[1], [-2]])

    def test_clause_vide_et_formule_vide(self):
        self.assertEqual(parse_dimacs("p cnf 1 1\n0\n").clauses, [[]])
        self.assertEqual(parse_dimacs("p cnf 3 0\n").clauses, [])

    def test_commentaires_pourcent_et_zero_final_manquant(self):
        cnf = parse_dimacs("c x\np cnf 2 2\n1 2 0\n-1 -2\n%\n0\n")
        self.assertEqual(cnf.clauses, [[1, 2], [-1, -2]])

    def test_normaliser(self):
        self.assertEqual(normaliser([[1, -1, 2], [3, 3, 4]]), [frozenset({3, 4})])


class TestInstancesQ2(unittest.TestCase):
    def test_v1_v2_statut_et_modele(self):
        for nom in RAPIDES:
            with self.subTest(instance=nom):
                cnf = read_dimacs(str(RACINE / "instances" / nom))
                m = dpll_v2(cnf)
                self.assertEqual("SAT" if m is not None else "UNSAT", ATTENDU[nom])
                self.assertEqual(dpll_v1(cnf), m is not None)
                if m is not None:
                    self.assertEqual(set(m), set(range(1, cnf.nb_vars + 1)))
                    self.assertTrue(verifier_modele(cnf, m))


class TestOptimise(unittest.TestCase):
    """Le portefeuille (Q6) doit rendre le même statut qu'`expected.json`, avec un modèle valide."""

    def test_portefeuille_complet(self):
        for nom in RAPIDES:
            with self.subTest(instance=nom):
                cnf = read_dimacs(str(RACINE / "instances" / nom))
                m = resoudre(cnf, jobs=len(PORTEFEUILLE))
                self.assertEqual("SAT" if m is not None else "UNSAT", ATTENDU[nom])
                if m is not None:
                    self.assertTrue(verifier_modele(cnf, m))

    def test_un_seul_solveur(self):
        cnf = read_dimacs(str(RACINE / "instances" / "public-16.cnf"))
        self.assertIsNone(resoudre(cnf, jobs=1))


class TestCli(unittest.TestCase):
    def lancer(self, instance, *options):
        return subprocess.run([sys.executable, str(RACINE / "sat.py"), str(RACINE / "instances" / instance),
                               *options], capture_output=True, text=True, timeout=60)

    def test_sortie_exacte_sat_avec_modele(self):
        for mode in ("dpll", "optimized"):
            with self.subTest(mode=mode):
                r = self.lancer("cli_model_sat.cnf", "--mode", mode, "--output-model")
                lignes = r.stdout.splitlines()
                self.assertEqual(lignes[0], "s SATISFIABLE")
                self.assertEqual(len(lignes), 2)
                self.assertTrue(lignes[1].startswith("v ") and lignes[1].endswith(" 0"))
                cnf = read_dimacs(str(RACINE / "instances" / "cli_model_sat.cnf"))
                lits = [int(x) for x in lignes[1].split()[1:-1]]
                self.assertTrue(verifier_modele(cnf, {abs(l): l > 0 for l in lits}))

    def test_unsat_sans_modele_et_sans_mode(self):
        for options in ([], ["--mode", "dpll"], ["--mode", "optimized"]):
            with self.subTest(options=options):
                r = self.lancer("smoke_02_unsat.cnf", *options, "--output-model")
                self.assertEqual(r.stdout, "s UNSATISFIABLE\n")

    def test_sat_sans_option_modele(self):
        r = self.lancer("smoke_01_sat.cnf", "--mode", "optimized")
        self.assertEqual(r.stdout, "s SATISFIABLE\n")


if __name__ == "__main__":
    unittest.main()
