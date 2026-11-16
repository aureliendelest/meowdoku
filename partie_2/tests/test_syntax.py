"""Q2 — Tests de la grammaire et de l'arbre de syntaxe.

Lancer depuis la racine du depot :

    python -m unittest discover -s partie_2/tests -t .
"""

import unittest
from pathlib import Path

from lark.exceptions import UnexpectedInput

from ..syntax import (And, Compare, Constraint, Forall, Implies, IntLit, Not,
                      Or, Program, Var, parse, pretty)

EXEMPLES = Path(__file__).resolve().parent.parent / "exemples"


def expr_de(texte: str):
    """Expression de l'unique contrainte d'un modele minimal."""
    programme = parse("var a : bool; var b : bool; var c : bool;"
                      "var x : 1..9; var y : 1..9;" + texte)
    return [s.expr for s in programme.statements if isinstance(s, Constraint)][0]


class TestPriorites(unittest.TestCase):
    def test_and_plus_prioritaire_que_or(self):
        self.assertEqual(expr_de("constraint a or b and c;"),
                         Or(Var("a"), And(Var("b"), Var("c"))))

    def test_not_plus_prioritaire_que_and(self):
        self.assertEqual(expr_de("constraint not a and b;"),
                         And(Not(Var("a")), Var("b")))

    def test_comparaison_plus_prioritaire_que_not(self):
        # l'enonce : `not x = 2` se lit `not (x = 2)`
        self.assertEqual(expr_de("constraint not x = 2;"),
                         Not(Compare("=", Var("x"), IntLit(2))))

    def test_arithmetique_plus_prioritaire_que_comparaison(self):
        self.assertEqual(pretty(parse("constraint x = 1 + 2 * 3;").statements[0]),
                         "Constraint (x = (1 + (2 * 3)))")

    def test_moins_unaire(self):
        self.assertEqual(pretty(parse("constraint x = -1 + 2;").statements[0]),
                         "Constraint (x = ((-1) + 2))")


class TestAssociativites(unittest.TestCase):
    def test_and_associatif_a_gauche(self):
        self.assertEqual(expr_de("constraint a and b and c;"),
                         And(And(Var("a"), Var("b")), Var("c")))

    def test_or_associatif_a_gauche(self):
        self.assertEqual(expr_de("constraint a or b or c;"),
                         Or(Or(Var("a"), Var("b")), Var("c")))

    def test_implication_associative_a_droite(self):
        self.assertEqual(expr_de("constraint a -> b -> c;"),
                         Implies(Var("a"), Implies(Var("b"), Var("c"))))

    def test_or_moins_prioritaire_que_implication(self):
        self.assertEqual(expr_de("constraint a or b -> c;"),
                         Implies(Or(Var("a"), Var("b")), Var("c")))


class TestErreursDeSyntaxe(unittest.TestCase):
    def rejeter(self, texte: str):
        with self.assertRaises(UnexpectedInput, msg=texte):
            parse(texte)

    def test_comparaisons_ne_s_enchainent_pas(self):
        # `a = b = c` doit etre une erreur de syntaxe (enonce)
        self.rejeter("var a : 1..3; var b : 1..3; var c : 1..3; constraint a = b = c;")

    def test_mots_cles_reserves(self):
        for mot in ("var", "const", "enum", "array", "bool", "constraint",
                    "forall", "in", "not", "and", "or"):
            self.rejeter(f"var {mot} : bool;")

    def test_for_et_where_reserves(self):
        # extension : les listes en comprehension reservent deux mots de plus
        self.rejeter("var for : bool;")
        self.rejeter("var where : bool;")

    def test_point_virgule_manquant(self):
        self.rejeter("var x : bool constraint x;")

    def test_parenthese_non_fermee(self):
        self.rejeter("var a : bool; constraint (a;")


class TestStructures(unittest.TestCase):
    def test_forall_plusieurs_iterateurs(self):
        p = parse("const N = 3; array g[N] : 1..N; forall i in 1..N, j in i..N "
                  "{ constraint g[i] != g[j]; }")
        boucle = p.statements[-1]
        self.assertIsInstance(boucle, Forall)
        self.assertEqual([n for n, _ in boucle.iterators], ["i", "j"])
        self.assertEqual(len(boucle.body), 1)

    def test_tableau_constant_imbrique(self):
        p = parse("const E = 2; const edge[E][2] = [[1, 2], [3, 4]];")
        self.assertEqual(pretty(p.statements[1]), "ConstArray edge[E][2] = [[1, 2], [3, 4]]")

    def test_tranche(self):
        p = parse("const N = 3; array g[N][N] : 1..N; constraint allDifferent(g[1][*]);")
        self.assertEqual(pretty(p.statements[-1]), "Constraint allDifferent(g[1][*])")

    def test_comprehension(self):
        p = parse("const N = 3; array c[N][N] : bool; "
                  "constraint atLeastOne(c[i][j] for i in 1..N, j in 1..N where i < j);")
        self.assertEqual(pretty(p.statements[-1]),
                         "Constraint atLeastOne(c[i][j] for i in 1..N, j in 1..N where (i < j))")

    def test_positions_conservees(self):
        p = parse("var x : bool;\nconstraint x;\n")
        self.assertEqual(p.statements[1].pos[0], 2)   # ligne 2


class TestExemples(unittest.TestCase):
    def test_les_quatre_modeles_sont_acceptes(self):
        for fichier in sorted(EXEMPLES.glob("*.csp")):
            with self.subTest(fichier.name):
                programme = parse(fichier.read_text(encoding="utf-8"))
                self.assertIsInstance(programme, Program)
                self.assertTrue(programme.statements)

    def test_affichage_des_exemples(self):
        """`pretty` doit savoir afficher toutes les constructions des exemples."""
        for fichier in sorted(EXEMPLES.glob("*.csp")):
            with self.subTest(fichier.name):
                sortie = pretty(parse(fichier.read_text(encoding="utf-8")))
                self.assertTrue(sortie.startswith("Program"))


if __name__ == "__main__":
    unittest.main()
