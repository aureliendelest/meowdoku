"""Q6 — Tests des deux modelisations de Meowdoku.

Chaque solution est controlee par `src.meowdoku.check.verifier`, qui verifie
les quatre regles du jeu directement sur la grille : il ne connait ni le
langage, ni le compilateur, ni l'encodage SAT. Une erreur de modelisation ne
peut donc pas se masquer elle-meme.
"""

import unittest

from src.meowdoku.check import verifier
from src.meowdoku.generate import generate
from src.meowdoku.grid import parse_grid, read_grid

from ..meowdoku import modele, noms_surs, positions_depuis_valeurs
from ..solve import compiler_texte, resoudre
from ..syntax import parse

FIGURE1 = "grids/figure1.txt"
SOLUTION_FIGURE2 = {(1, 3), (2, 5), (3, 2), (4, 4), (5, 6), (6, 1)}

VARIANTES = (
    ("positions", dict(forme="positions")),
    ("cases", dict(forme="cases")),
    ("cases redondant", dict(forme="cases", redondant=True)),
    ("cases sans comprehension", dict(forme="cases", comprehension=False)),
    ("cases general", dict(forme="cases", general=True)),
)


def resoudre_grille(grid, **options):
    texte = modele(grid, **options)
    valeurs = resoudre(compiler_texte(texte))
    if valeurs is None:
        return None
    return positions_depuis_valeurs(valeurs, noms_surs(grid.zones))


class TestConversion(unittest.TestCase):
    def test_les_modeles_produits_sont_analysables(self):
        grid = read_grid(FIGURE1)
        for nom, options in VARIANTES:
            with self.subTest(nom):
                self.assertTrue(parse(modele(grid, **options)).statements)

    def test_declarations_reprennent_la_grille(self):
        texte = modele(read_grid(FIGURE1))
        self.assertIn("const N = 6;", texte)
        self.assertIn("enum Zone = { A, B, C, D, E, F };", texte)
        self.assertIn("[A, B, C, B, B, D]", texte)

    def test_noms_sans_collision_avec_les_regions(self):
        """Une grille de 11 regions en nomme une « K » : le modele doit s'adapter.

        Les noms que le modele introduit (N, M, K, Zone, region, cat, les
        indices de boucle) partagent l'espace de noms du langage avec les noms
        de regions, qui viennent du fichier de grille.
        """
        grid, _ = generate(11, 0)
        self.assertIn("K", grid.zones)
        noms = noms_surs(grid.zones)
        self.assertNotEqual(noms["K"], "K")
        chats = resoudre_grille(grid)
        self.assertEqual(verifier(grid, chats), [])

    def test_noms_de_regions_en_minuscules(self):
        """Un nom de region peut aussi entrer en collision avec un indice de boucle."""
        grid = parse_grid("GRID 2 2\nZONES i j\ni i\nj j\n")
        noms = noms_surs(grid.zones)
        self.assertNotIn(noms["i"], grid.zones)
        self.assertTrue(parse(modele(grid)).statements)

    def test_positions_refuse_une_grille_non_carree(self):
        grid = parse_grid("GRID 1 2\nZONES A\nA A\n")
        with self.assertRaises(ValueError):
            modele(grid, forme="positions")


class TestResolution(unittest.TestCase):
    def test_figure1_toutes_variantes(self):
        grid = read_grid(FIGURE1)
        for nom, options in VARIANTES:
            with self.subTest(nom):
                chats = resoudre_grille(grid, **options)
                self.assertIsNotNone(chats)
                self.assertEqual(verifier(grid, chats), [])

    def test_figure1_donne_la_solution_de_l_enonce(self):
        """La grille de la figure 1 n'a qu'une solution : celle de la figure 2."""
        for nom, options in VARIANTES:
            with self.subTest(nom):
                self.assertEqual(resoudre_grille(read_grid(FIGURE1), **options),
                                 SOLUTION_FIGURE2)

    def test_grilles_generees(self):
        for n in (4, 5, 6, 11):
            for graine in range(2):
                grid, _ = generate(n, graine)
                for nom, options in VARIANTES:
                    with self.subTest(n=n, graine=graine, modele=nom):
                        chats = resoudre_grille(grid, **options)
                        self.assertIsNotNone(chats)
                        self.assertEqual(verifier(grid, chats), [])

    def test_grille_sans_solution(self):
        # 2x2 : deux cases quelconques sont toujours voisines
        grid = parse_grid("GRID 2 2\nZONES A B\nA A\nB B\n")
        self.assertIsNone(resoudre_grille(grid, forme="cases"))

    def test_les_deux_modeles_s_accordent_sur_le_statut(self):
        """Question 6.5 : meme reponse SAT/UNSAT, modele par modele."""
        grilles = [parse_grid("GRID 2 2\nZONES A B\nA A\nB B\n"),
                   parse_grid("GRID 1 1\nZONES A\nA\n"),
                   read_grid(FIGURE1)]
        for i, grid in enumerate(grilles):
            carre = grid.n_rows == grid.n_cols == len(grid.zones)
            variantes = VARIANTES if carre else VARIANTES[1:]
            statuts = {nom: resoudre_grille(grid, **o) is not None for nom, o in variantes}
            with self.subTest(grille=i):
                self.assertEqual(len(set(statuts.values())), 1, statuts)


class TestRechercheExhaustive(unittest.TestCase):
    """Question 6.5 : sur de petites grilles, on compare a une enumeration."""

    def exhaustive(self, grid) -> bool:
        import itertools
        choix = list(range(0, grid.n_cols + 1))     # 0 = pas de chat sur la ligne
        for colonnes in itertools.product(choix, repeat=grid.n_rows):
            positions = {(i + 1, c) for i, c in enumerate(colonnes) if c}
            if not verifier(grid, positions):
                return True
        return False

    def test_accord_sur_de_petites_grilles(self):
        grilles = ["GRID 2 2\nZONES A B\nA A\nB B\n",
                   "GRID 2 2\nZONES A B\nA B\nB A\n",
                   "GRID 1 1\nZONES A\nA\n",
                   "GRID 3 3\nZONES A B C\nA A B\nA B B\nC C C\n",
                   "GRID 2 3\nZONES A B\nA A B\nA B B\n"]
        for texte in grilles:
            grid = parse_grid(texte)
            with self.subTest(texte.splitlines()[0]):
                par_solveur = resoudre_grille(grid, forme="cases") is not None
                self.assertEqual(par_solveur, self.exhaustive(grid))


if __name__ == "__main__":
    unittest.main()
