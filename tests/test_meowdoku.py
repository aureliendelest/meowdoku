"""Tests de l'encodage, du générateur et du contrôleur Meowdoku (Q1).

Lancer depuis la racine : python -m unittest discover -s tests -t .
"""

import itertools
import unittest
from math import comb

from src.meowdoku.check import verifier
from src.meowdoku.encode import cell, decode_model, encode, to_dimacs, var
from src.meowdoku.generate import generate, region_name
from src.meowdoku.grid import GridError, format_grid, parse_grid, read_grid

FIGURE1 = "grids/figure1.txt"


def satisfait(clauses, positions, n_cols):
    """Vrai si l'affectation « chat exactement sur `positions` » satisfait toutes les clauses."""
    vraies = {var(i, j, n_cols) for i, j in positions}
    return all(any((l > 0) == (abs(l) in vraies) for l in c) for c in clauses)


def nb_clauses_attendu(grid):
    """Nombre de clauses prévu par la formule du rapport (N = M = K)."""
    n, m = grid.n_rows, grid.n_cols
    return (
        len(grid.zones)
        + n * comb(m, 2)
        + m * comb(n, 2)
        + sum(comb(len(c), 2) for c in grid.regions.values())
        + 2 * (n - 1) * (m - 1)
    )


def connexe(cases):
    """Vrai si l'ensemble de cases est connexe pour le 4-voisinage."""
    cases = set(cases)
    vus, pile = set(), [next(iter(cases))]
    while pile:
        i, j = pile.pop()
        if (i, j) in vus:
            continue
        vus.add((i, j))
        pile += [p for p in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)) if p in cases]
    return vus == cases


class TestGrid(unittest.TestCase):
    """Lecture, validation et réécriture des grilles."""

    def test_lecture_figure1(self):
        g = read_grid(FIGURE1)
        self.assertEqual((g.n_rows, g.n_cols, len(g.zones)), (6, 6, 6))
        self.assertEqual(g.region_of(3, 3), "B")
        self.assertEqual(g.regions["E"], [(4, 4)])
        self.assertEqual(g.regions["F"], [(6, 1)])

    def test_aller_retour(self):
        g = read_grid(FIGURE1)
        self.assertEqual(parse_grid(format_grid(g, ("test",))), g)

    def test_grilles_illicites(self):
        cas = {
            "region inconnue": "GRID 2 2\nZONES A B\nA B\nA C\n",
            "region vide": "GRID 2 2\nZONES A B\nA A\nA A\n",
            "lignes manquantes": "GRID 2 2\nZONES A\nA A\n",
            "colonnes en trop": "GRID 1 2\nZONES A\nA A A\n",
            "pas de GRID": "ZONES A\nA\n",
            "pas de ZONES": "GRID 1 1\nA\n",
            "zones dupliquees": "GRID 1 2\nZONES A A\nA A\n",
            "zone c": "GRID 1 1\nZONES c\nc\n",
        }
        for nom, texte in cas.items():
            with self.subTest(nom):
                with self.assertRaises(GridError):
                    parse_grid(texte)

    def test_commentaires_et_noms_en_c(self):
        g = parse_grid("c commentaire\nGRID 1 2\nZONES cyan rose\nc autre\ncyan rose\n")
        self.assertEqual(g.cells, (("cyan", "rose"),))


class TestEncode(unittest.TestCase):
    """Encodage CNF : taille, numérotation, équivalence avec les règles du jeu."""

    def test_numerotation(self):
        for i, j in itertools.product(range(1, 5), range(1, 7)):
            self.assertEqual(cell(var(i, j, 6), 6), (i, j))
        self.assertEqual(var(1, 1, 6), 1)
        self.assertEqual(var(4, 6, 6), 24)

    def test_comptage_figure1(self):
        g = read_grid(FIGURE1)
        nv, cl = encode(g)
        self.assertEqual((nv, len(cl)), (36, 408))
        self.assertEqual(len(cl), nb_clauses_attendu(g))
        self.assertEqual(len(encode(g, redundant=True)[1]), 408 + 12)

    def test_format_dimacs(self):
        g = read_grid(FIGURE1)
        nv, cl = encode(g)
        lignes = to_dimacs(nv, cl, ("x",)).splitlines()
        self.assertEqual(lignes[0], "c x")
        self.assertEqual(lignes[1], "p cnf 36 408")
        self.assertTrue(all(ln.endswith(" 0") for ln in lignes[2:]))
        self.assertEqual(len(lignes), 2 + 408)

    def equivalence_par_force_brute(self, grid):
        """Pour tout placement « un chat par ligne », clauses satisfaites <=> contrôleur content."""
        n, m = grid.n_rows, grid.n_cols
        _, cl = encode(grid)
        nb_solutions = 0
        for cols in itertools.product(range(1, m + 1), repeat=n):
            pos = {(i + 1, c) for i, c in enumerate(cols)}
            ok = not verifier(grid, pos)
            self.assertEqual(satisfait(cl, pos, m), ok, pos)
            nb_solutions += ok
        return nb_solutions

    def test_equivalence_figure1(self):
        self.assertEqual(self.equivalence_par_force_brute(read_grid(FIGURE1)), 1)

    def test_equivalence_grilles_generees(self):
        for seed in range(5):
            with self.subTest(seed=seed):
                grid, _ = generate(5, seed)
                self.assertGreaterEqual(self.equivalence_par_force_brute(grid), 1)

    def test_grille_insoluble_donne_aucun_placement(self):
        # Région B = coins opposés : aucune des deux cases ne complète un placement valide.
        g = parse_grid("GRID 2 2\nZONES A B\nA B\nB A\n")
        self.assertEqual(self.equivalence_par_force_brute(g), 0)

    def test_decode_model(self):
        g = read_grid(FIGURE1)
        modele = [-1, 2, -3, 29, -30]
        self.assertEqual(decode_model(g, modele), {(1, 2), (5, 5)})
        self.assertEqual(decode_model(g, [37, 100]), set())  # variables auxiliaires ignorées


class TestControleur(unittest.TestCase):
    """Le contrôleur accepte une vraie solution et refuse chaque type de violation."""

    SOLUTION = {(1, 3), (2, 5), (3, 2), (4, 4), (5, 6), (6, 1)}  # figure 2 de l'énoncé

    def setUp(self):
        self.g = read_grid(FIGURE1)

    def test_solution_figure2(self):
        self.assertEqual(verifier(self.g, self.SOLUTION), [])

    def test_violations(self):
        s = self.SOLUTION
        cas = {
            "deux chats sur une ligne": s | {(1, 5)},
            "deux chats sur une colonne": s | {(3, 3)},
            "region sans chat": s - {(6, 1)},
            "region avec deux chats": (s - {(5, 6)}) | {(5, 5), (6, 5)},
            "adjacence diagonale": (s - {(2, 5)}) | {(2, 4)},
            "adjacence orthogonale": (s - {(2, 5)}) | {(2, 3)},
            "hors grille": s | {(7, 7)},
        }
        for nom, pos in cas.items():
            with self.subTest(nom):
                self.assertNotEqual(verifier(self.g, pos), [])


class TestGenerateur(unittest.TestCase):
    """Le générateur produit des grilles licites, solubles et reproductibles."""

    TAILLES = (1, 4, 5, 6, 8, 12, 20, 30)

    def test_grilles_licites_et_solubles(self):
        for n in self.TAILLES:
            for seed in range(5):
                with self.subTest(n=n, seed=seed):
                    grid, sol = generate(n, seed)
                    self.assertEqual(parse_grid(format_grid(grid)), grid)  # format valide
                    self.assertEqual((grid.n_rows, grid.n_cols, len(grid.zones)), (n, n, n))
                    self.assertEqual(verifier(grid, sol), [])
                    _, cl = encode(grid)
                    self.assertTrue(satisfait(cl, sol, n))

    def test_regions_connexes(self):
        for n in (6, 12, 30):
            grid, _ = generate(n, seed=n)
            for nom, cases in grid.regions.items():
                self.assertTrue(connexe(cases), f"n={n} région {nom}")

    def test_reproductible(self):
        self.assertEqual(generate(8, seed=42), generate(8, seed=42))
        self.assertNotEqual(generate(8, seed=1)[0], generate(8, seed=2)[0])

    def test_tailles_impossibles(self):
        for n in (-1, 0, 2, 3):
            with self.assertRaises(ValueError):
                generate(n)

    def test_noms_de_regions(self):
        self.assertEqual([region_name(k) for k in (0, 25, 26, 27, 51, 52)],
                         ["A", "Z", "AA", "AB", "AZ", "BA"])
        grid, _ = generate(30, seed=0)
        self.assertEqual(len(set(grid.zones)), 30)


if __name__ == "__main__":
    unittest.main()
