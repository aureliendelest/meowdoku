"""Tests de Q4 : scores, choix de chaque heuristique, conformité à l'algo 2 (statut + modèle)."""

import json
import unittest
from fractions import Fraction
from pathlib import Path

from src.cnf import normaliser, read_dimacs, verifier_modele
from src.dpll import dpll_h
from src.heuristics import NOMS, creer, score_frequence, score_jw, score_min

RACINE = Path(__file__).resolve().parent.parent
ATTENDU = json.loads((RACINE / "expected.json").read_text())

# Formule de l'énoncé : (x1 ∨ x2 ∨ ¬x4) ∧ (x2 ∨ x3) ∧ (x1 ∨ ¬x2 ∨ x4 ∨ ¬x5)
ENONCE = normaliser([[1, 2, -4], [2, 3], [1, -2, 4, -5]])
# Exemple du rapport : MOMS ex æquo sur x1, x2, x3 ; JW départage (x1 : 3/4)
COMBO = normaliser([[1, 2], [-1, 3], [2, -3], [1, 2, 4], [1, 3, 4]])
# Littéraux négatifs en tête (coquille de l'énoncé sur H5 : la valeur de ¬p est 0)
NEGATIF = normaliser([[-1, 2], [-1, 3], [1, 2, 3]])


class TestScores(unittest.TestCase):
    def test_exemple_enonce(self):
        f = score_frequence(ENONCE)
        self.assertEqual((f[2] + f.get(-2, 0), f[2], f[-2]), (3, 2, 1))  # #(x2)=3, #+=2, #-=1
        self.assertEqual(score_min(ENONCE), {2: 1, 3: 1})                  # seule clause de taille 2
        jw = score_jw(ENONCE)  # K = 4 : on divise par 2^K pour retrouver Σ 2^-k
        self.assertEqual(Fraction(jw[2] + jw[-2], 16), Fraction(7, 16))    # 1/2^3 + 1/2^2 + 1/2^4

    def test_jw_exemple_combo(self):
        jw = score_jw(COMBO)  # K = 3
        self.assertEqual([Fraction(jw[p] + jw.get(-p, 0), 8) for p in (1, 2, 3, 4)],
                         [Fraction(3, 4), Fraction(5, 8), Fraction(5, 8), Fraction(1, 4)])


class TestChoix(unittest.TestCase):
    def choix(self, nom, f):
        return creer(nom, f)(f)

    def test_enonce_dynamiques_et_statiques_coincident(self):
        # sur la formule initiale, statique = dynamique
        attendu = {"H2": 2, "H3": 1, "H4": 2, "H5": 2, "H6": 2, "H7": 2}
        for h, lit in attendu.items():
            for m in "sd":
                with self.subTest(h + m):
                    self.assertEqual(self.choix(h + m, ENONCE), lit)

    def test_h1_premiere_variable_valeur_vraie(self):
        self.assertEqual(self.choix("H1", normaliser([[3, -2], [5]])), 2)  # variable 2, valeur 1

    def test_combo_moms_puis_jw(self):
        self.assertEqual(self.choix("MJd", COMBO), 1)
        self.assertEqual(self.choix("MJs", COMBO), 1)

    def test_valeur_negative_h4_h5(self):
        for h in ("H4d", "H5d", "H4s", "H5s"):
            with self.subTest(h):
                self.assertEqual(self.choix(h, NEGATIF), -1)

    def test_statique_ignore_variables_disparues(self):
        # classement initial : x1 en tête ; après affectation x1←1, x1 a disparu de F
        initiale = normaliser([[1, 2], [1, 3], [-2, -3, 4]])
        courante = [frozenset({-2, -3, 4})]
        for h in ("H2s", "H4s", "H6s", "MJs"):
            with self.subTest(h):
                self.assertNotEqual(abs(creer(h, initiale)(courante)), 1)

    def test_nom_inconnu(self):
        with self.assertRaises(ValueError):
            creer("H9", [])


class TestConformite(unittest.TestCase):
    """Chaque heuristique doit donner le statut de expected.json et un modèle valide."""

    RAPIDES = [n for n in ATTENDU if not n.startswith("public-")] + [
        f"public-{i:02d}.cnf" for i in (1, 2, 5, 9, 10, 13, 14, 16, 17, 20, 23, 24, 26, 28, 29)
    ]

    def test_toutes_heuristiques(self):
        for nom in NOMS:
            for fichier in self.RAPIDES:
                with self.subTest(heuristique=nom, instance=fichier):
                    cnf = read_dimacs(str(RACINE / "instances" / fichier))
                    m = dpll_h(cnf, nom)
                    self.assertEqual("SAT" if m is not None else "UNSAT", ATTENDU[fichier])
                    if m is not None:
                        self.assertEqual(set(m), set(range(1, cnf.nb_vars + 1)))
                        self.assertTrue(verifier_modele(cnf, m))


if __name__ == "__main__":
    unittest.main()
