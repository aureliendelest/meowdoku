"""Q4/Q5 — Tests de l'encodage en FNC et de la chaine complete.

Le coeur du fichier est `TestEquisatisfiabilite` : sur des modeles tires au
hasard a peu de variables, on compare la FNC produite a une reference calculee
par enumeration de toutes les affectations. C'est le filet de securite de tout
le compilateur, puisqu'il controle d'un coup l'analyse, l'encodage des domaines
et la mise en FNC.
"""

import itertools
import random
import unittest
from pathlib import Path

from src.cnf import Cnf, verifier_modele

from ..analyze import analyser, cases_de
from ..dimacs import correspondance, ecrire, lire_correspondance
from ..encode import encoder
from ..solve import compiler_texte, formater, lire_valeurs, resoudre
from ..syntax import parse

EXEMPLES = Path(__file__).resolve().parent.parent / "exemples"


def compiler(texte: str):
    return compiler_texte(texte)


def modeles_de_la_fnc(fnc):
    """Toutes les valuations qui satisfont la FNC (enumeration, petites formules)."""
    cnf = Cnf(fnc.nb_vars, fnc.clauses)
    for bits in itertools.product([False, True], repeat=fnc.nb_vars):
        valuation = {v + 1: b for v, b in enumerate(bits)}
        if verifier_modele(cnf, valuation):
            yield valuation


class TestEncodageDirect(unittest.TestCase):
    def test_exactement_une_valeur_par_case(self):
        """var x : 1..3 donne 3 variables et les 4 clauses de l'enonce."""
        c = compiler("var x : 1..3;")
        self.assertEqual(c.fnc.nb_vars, 3)
        self.assertEqual(sorted(map(sorted, c.fnc.clauses)),
                         sorted(map(sorted, [[1, 2, 3], [-1, -2], [-1, -3], [-2, -3]])))

    def test_bool_ne_coute_qu_une_variable(self):
        """Une variable booleenne reste une variable booleenne, sans clause de domaine."""
        c = compiler("var b : bool;")
        self.assertEqual((c.fnc.nb_vars, c.fnc.clauses), (1, []))

    def test_enum_numerote_dans_l_ordre_de_declaration(self):
        c = compiler("enum Color = { Red, Green, Blue }; var c : Color; constraint c = Green;")
        noms = dict(correspondance(c.encodeur))
        self.assertEqual([noms[n] for n in sorted(noms)], ["c=Red", "c=Green", "c=Blue"])

    def test_tableau_toutes_les_cases(self):
        m = analyser(parse("const N = 2; array g[N][N] : 1..2;"))
        self.assertEqual([c.indices for c in cases_de(m.table["g"])],
                         [(1, 1), (1, 2), (2, 1), (2, 2)])


class TestComparaisons(unittest.TestCase):
    """Chaque traduction est verifiee par enumeration sur un domaine minuscule."""

    def valeurs_admises(self, texte: str, noms: list[str]) -> set[tuple[int, ...]]:
        """Valeurs des cases nommees pour lesquelles la FNC est satisfiable."""
        c = compiler(texte)
        admises = set()
        for valuation in modeles_de_la_fnc(c.fnc):
            lu = dict(lire_valeurs(c.encodeur, valuation))
            admises.add(tuple(int(lu[n]) for n in noms))
        return admises

    def test_egalite_a_une_constante(self):
        self.assertEqual(self.valeurs_admises("var x : 1..3; constraint x = 2;", ["x"]), {(2,)})

    def test_difference_a_une_constante(self):
        self.assertEqual(self.valeurs_admises("var x : 1..3; constraint x != 2;", ["x"]),
                         {(1,), (3,)})

    def test_ordre_a_une_constante(self):
        for op, attendu in (("<", {1, 2}), ("<=", {1, 2, 3}), (">", {4}), (">=", {3, 4})):
            with self.subTest(op):
                self.assertEqual(
                    self.valeurs_admises(f"var x : 1..4; constraint x {op} 3;", ["x"]),
                    {(v,) for v in attendu})

    def test_valeur_a_gauche(self):
        self.assertEqual(self.valeurs_admises("var x : 1..3; constraint 2 < x;", ["x"]), {(3,)})

    def test_entre_deux_cases(self):
        for op in ("=", "!=", "<", "<=", ">", ">="):
            with self.subTest(op):
                admises = self.valeurs_admises(
                    f"var x : 1..3; var y : 1..3; constraint x {op} y;", ["x", "y"])
                attendu = {(a, b) for a in (1, 2, 3) for b in (1, 2, 3)
                           if {"=": a == b, "!=": a != b, "<": a < b,
                               "<=": a <= b, ">": a > b, ">=": a >= b}[op]}
                self.assertEqual(admises, attendu)

    def test_domaines_differents(self):
        admises = self.valeurs_admises(
            "var x : 1..3; var y : 2..4; constraint x = y;", ["x", "y"])
        self.assertEqual(admises, {(2, 2), (3, 3)})


class TestContraintesGlobales(unittest.TestCase):
    def satisfiables(self, texte: str, noms: list[str]) -> set:
        c = compiler(texte)
        sortie = set()
        for valuation in modeles_de_la_fnc(c.fnc):
            lu = dict(lire_valeurs(c.encodeur, valuation))
            sortie.add(tuple(lu[n] for n in noms))
        return sortie

    DECL = "var a : bool; var b : bool; var c : bool; "
    NOMS = ["a", "b", "c"]

    def combien_de_vrais(self, texte):
        return {sum(v == "true" for v in t) for t in self.satisfiables(texte, self.NOMS)}

    def test_at_least_one(self):
        self.assertEqual(self.combien_de_vrais(self.DECL + "constraint atLeastOne(a, b, c);"),
                         {1, 2, 3})

    def test_at_most_one(self):
        self.assertEqual(self.combien_de_vrais(self.DECL + "constraint atMostOne(a, b, c);"),
                         {0, 1})

    def test_exactly_one(self):
        self.assertEqual(self.combien_de_vrais(self.DECL + "constraint exactlyOne(a, b, c);"),
                         {1})

    def test_at_most_one_est_deux_a_deux(self):
        """L'enonce impose l'encodage par paires : n(n-1)/2 clauses, zero variable auxiliaire."""
        c = compiler("var a : bool; var b : bool; var c : bool; var d : bool; "
                     "constraint atMostOne(a, b, c, d);")
        self.assertEqual(len(c.fnc.clauses), 6)
        self.assertEqual(c.fnc.nb_auxiliaires, 0)

    def test_all_different(self):
        admises = self.satisfiables(
            "var x : 1..3; var y : 1..3; constraint allDifferent(x, y);", ["x", "y"])
        self.assertEqual(admises, {(a, b) for a in "123" for b in "123" if a != b})

    def test_all_different_avec_une_constante(self):
        admises = self.satisfiables(
            "var x : 1..3; var y : 1..3; constraint allDifferent(x, y, 2);", ["x", "y"])
        self.assertEqual(admises, {("1", "3"), ("3", "1")})

    def test_globale_sous_une_negation(self):
        """`not atMostOne(...)` : l'encodage deux a deux reste correct car il est
        logiquement equivalent (pas de variable auxiliaire a sens unique)."""
        self.assertEqual(
            self.combien_de_vrais(self.DECL + "constraint not atMostOne(a, b, c);"),
            {2, 3})


class TestEquisatisfiabilite(unittest.TestCase):
    """La FNC est satisfiable si et seulement si le modele l'est.

    La reference est calculee par enumeration de toutes les affectations des
    variables du modele, sans passer par le solveur ni par l'encodage.
    """

    GABARITS = [
        "constraint x {op} y;",
        "constraint x {op} {k};",
        "constraint x = {k} -> y != {k};",
        "constraint not (x {op} y) and y != {k};",
        "constraint allDifferent(x, y);",
        "constraint x {op} y or x = {k};",
        "constraint atLeastOne(b, c) and x {op} {k};",
        "constraint b -> x {op} y;",
        "constraint exactlyOne(b, c) and not (x = y);",
    ]
    DOMAINE = (1, 2, 3)

    def declarations(self) -> str:
        return "var x : 1..3; var y : 1..3; var b : bool; var c : bool; "

    def test_gabarits(self):
        """Chaque gabarit, instancie, donne la meme reponse que l'enumeration."""
        rng = random.Random(0)
        for gabarit in self.GABARITS:
            for _ in range(4):
                texte = gabarit.format(op=rng.choice(["=", "!=", "<", "<=", ">", ">="]),
                                       k=rng.choice(self.DOMAINE))
                with self.subTest(texte):
                    compilation = compiler_texte(self.declarations() + texte)
                    par_solveur = resoudre(compilation, jobs=1) is not None
                    par_enumeration = any(True for _ in modeles_de_la_fnc(compilation.fnc))
                    self.assertEqual(par_solveur, par_enumeration)

    def test_restriction_d_un_modele(self):
        """Tout modele de la FNC donne une affectation qui satisfait le modele."""
        texte = self.declarations() + "constraint x < y and (b -> x = 1);"
        compilation = compiler_texte(texte)
        vus = 0
        for valuation in modeles_de_la_fnc(compilation.fnc):
            lu = dict(lire_valeurs(compilation.encodeur, valuation))
            x, y, b = int(lu["x"]), int(lu["y"]), lu["b"] == "true"
            self.assertTrue(x < y and (not b or x == 1), lu)
            vus += 1
        self.assertGreater(vus, 0)


class TestDimacs(unittest.TestCase):
    def test_format(self):
        c = compiler("var x : 1..2; constraint x = 1;")
        lignes = ecrire(c.fnc, c.encodeur, ("essai",)).splitlines()
        self.assertEqual(lignes[0], "c essai")
        self.assertEqual(lignes[1:3], ["c var 1 x=1", "c var 2 x=2"])
        self.assertTrue(lignes[3].startswith("p cnf 2 "))
        self.assertTrue(all(l.endswith(" 0") for l in lignes[4:]))

    def test_correspondance_relisible(self):
        c = compiler("enum C = { Red, Blue }; array k[C] : bool;")
        texte = ecrire(c.fnc, c.encodeur)
        self.assertEqual(lire_correspondance(texte), {1: "k[Red]=true", 2: "k[Blue]=true"})


class TestChaineComplete(unittest.TestCase):
    """Les quatre modeles de l'enonce, avec les reponses du tableau 1."""

    ATTENDU = {"pigeonhole.csp": None, "queens.csp": "SAT",
               "coloring.csp": "SAT", "sudoku.csp": "SAT"}

    def resoudre_exemple(self, nom: str):
        c = compiler_texte((EXEMPLES / nom).read_text(encoding="utf-8"))
        return c, resoudre(c)

    def test_statuts(self):
        for nom, attendu in self.ATTENDU.items():
            with self.subTest(nom):
                _, valeurs = self.resoudre_exemple(nom)
                self.assertEqual("SAT" if valeurs else None, attendu)

    def test_queens_solution_valide(self):
        _, valeurs = self.resoudre_exemple("queens.csp")
        colonnes = [int(v) for _, v in valeurs]
        self.assertEqual(len(set(colonnes)), 8)
        self.assertTrue(all(abs(colonnes[i] - colonnes[j]) != abs(i - j)
                            for i in range(8) for j in range(i + 1, 8)))

    def test_coloring_solution_valide(self):
        aretes = [(1, 2), (2, 3), (3, 4), (4, 5), (5, 1), (6, 8), (8, 10), (10, 7),
                  (7, 9), (9, 6), (1, 6), (2, 7), (3, 8), (4, 9), (5, 10)]
        _, valeurs = self.resoudre_exemple("coloring.csp")
        couleur = {int(n[6:-1]): v for n, v in valeurs}
        self.assertTrue(all(couleur[a] != couleur[b] for a, b in aretes))
        self.assertEqual((couleur[1], couleur[2]), ("Red", "Green"))

    def test_sudoku_solution_valide(self):
        _, valeurs = self.resoudre_exemple("sudoku.csp")
        lu = dict(valeurs)
        grille = [[int(lu[f"grid[{i}][{j}]"]) for j in range(1, 10)] for i in range(1, 10)]
        complet = list(range(1, 10))
        self.assertTrue(all(sorted(r) == complet for r in grille))
        self.assertTrue(all(sorted(col) == complet for col in zip(*grille)))
        self.assertTrue(all(sorted(grille[i + di][j + dj] for di in range(3)
                                   for dj in range(3)) == complet
                            for i in (0, 3, 6) for j in (0, 3, 6)))

    def test_format_de_sortie(self):
        c = compiler_texte("var x : 1..2; constraint x = 2;")
        self.assertEqual(formater(resoudre(c, jobs=1)), "s SATISFIABLE\nx = 2\n")
        self.assertEqual(formater(None), "s UNSATISFIABLE\n")


if __name__ == "__main__":
    unittest.main()
