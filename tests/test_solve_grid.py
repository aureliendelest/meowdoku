"""Tests de Q3 : grille -> solution (src/meowdoku/solve_grid.py)."""

import unittest

from src.meowdoku.check import verifier
from src.meowdoku.generate import generate
from src.meowdoku.grid import format_grid, parse_grid, read_grid
from src.meowdoku.solve_grid import dessiner, ecrire_solution, resoudre

FIGURE1 = "grids/figure1.txt"
# Solution de la figure 2 de l'énoncé
FIGURE2 = {(3, 2), (2, 5), (1, 3), (5, 6), (4, 4), (6, 1)}


class TestSolveGrid(unittest.TestCase):
    def test_figure1_donne_la_solution_de_l_enonce(self):
        grid = read_grid(FIGURE1)
        chats = resoudre(grid)
        self.assertEqual(verifier(grid, chats), [])
        self.assertEqual(chats, FIGURE2)

    def test_format_de_sortie(self):
        grid = read_grid(FIGURE1)
        with open(FIGURE1, encoding="utf-8") as f:
            texte = f.read()
        sortie = ecrire_solution(texte, grid, FIGURE2).splitlines()
        n_entree = len(texte.splitlines())
        self.assertEqual(sortie[:n_entree], texte.splitlines())  # recopie de l'entrée
        self.assertEqual(sortie[n_entree:n_entree + 6],
                         ["A 3 2", "B 2 5", "C 1 3", "D 5 6", "E 4 4", "F 6 1"])
        self.assertEqual(sortie[n_entree + 6], ". . * . . .")
        self.assertEqual(len(sortie), n_entree + 12)

    def test_grilles_generees_toujours_resolues(self):
        for n in (1, 4, 5, 6, 7, 8, 9):
            for seed in range(5):
                with self.subTest(n=n, seed=seed):
                    grid, _ = generate(n, seed)
                    chats = resoudre(grid)
                    self.assertIsNotNone(chats)
                    self.assertEqual(verifier(grid, chats), [])

    def test_grille_sans_solution(self):
        # 2x2 : deux cases quelconques sont toujours voisines
        grid = parse_grid("GRID 2 2\nZONES A B\nA A\nB B\n")
        self.assertIsNone(resoudre(grid))
        self.assertTrue(ecrire_solution("GRID 2 2\n", grid, None).endswith("UNSAT\n"))

    def test_dessin(self):
        grid = read_grid(FIGURE1)
        self.assertEqual(dessiner(grid, FIGURE2).splitlines()[5], "* . . . . .")


if __name__ == "__main__":
    unittest.main()
