"""Q3 — Tests de l'analyse semantique, du deroulage et de la simplification."""

import io
import unittest
from contextlib import redirect_stderr

from ..analyze import analyser
from ..ir import Case, Cmp, Glob
from ..symbols import ErreurModele, Val
from ..syntax import parse


def modele(texte: str):
    return analyser(parse(texte))


def contraintes(texte: str):
    return modele(texte).contraintes


class TestTableDesSymboles(unittest.TestCase):
    def test_constantes_et_enums(self):
        m = modele("const N = 3; enum Color = { Red, Green };")
        self.assertEqual(m.table["N"].valeur, Val("int", 3))
        self.assertEqual(m.table["Red"].valeur, Val("Color", 0))
        self.assertEqual(m.table["Green"].valeur, Val("Color", 1))

    def test_espace_de_noms_unique(self):
        """Constantes, types, valeurs enumerees et variables se partagent un espace."""
        for texte in ("const N = 1; var N : bool;",
                      "enum C = { Red }; const Red = 2;",
                      "var x : bool; array x[2] : bool;",
                      "enum C = { A, A };"):
            with self.subTest(texte), self.assertRaises(ErreurModele):
                modele(texte)

    def test_indice_de_boucle_dans_l_espace_de_noms(self):
        with self.assertRaises(ErreurModele):
            modele("const i = 1; forall i in 1..2 { constraint i < 3; }")

    def test_nom_non_declare(self):
        with self.assertRaises(ErreurModele) as ctx:
            modele("var x : bool; constraint x and w;")
        self.assertIn("'w' n'est pas declare", str(ctx.exception))


class TestTypes(unittest.TestCase):
    def rejeter(self, texte: str, fragment: str = ""):
        with self.assertRaises(ErreurModele, msg=texte) as ctx:
            modele(texte)
        if fragment:
            self.assertIn(fragment, str(ctx.exception))

    def test_comparer_une_couleur_a_un_entier(self):
        self.rejeter("enum C = { Red }; var c : C; constraint c = 3;", "comparaison entre")

    def test_additionner_des_booleens(self):
        self.rejeter("var b : bool; constraint b + 1 = 2;")

    def test_ordre_sur_les_booleens(self):
        self.rejeter("var a : bool; var b : bool; constraint a < b;",
                     "ne s'applique pas aux booleens")

    def test_valeur_inconnue_dans_l_arithmetique(self):
        self.rejeter("var x : 1..3; var y : 1..3; constraint x + 1 = y;",
                     "n'est pas une valeur connue")

    def test_mauvais_nombre_d_indices(self):
        self.rejeter("const N = 3; array g[N][N] : 1..N; constraint g[1] = 1;",
                     "2 dimension(s), 1 indice(s)")

    def test_indice_hors_bornes(self):
        self.rejeter("const N = 3; array a[N] : 1..N; constraint a[4] = 1;",
                     "out of range 1..3")

    def test_position_dans_le_message(self):
        with self.assertRaises(ErreurModele) as ctx:
            modele("const N = 3;\narray a[N] : 1..N;\nconstraint a[4] = 1;\n")
        self.assertIn("line 3", str(ctx.exception))

    def test_contrainte_globale_inconnue(self):
        self.rejeter("var b : bool; constraint allTheSame(b);", "contrainte globale inconnue")

    def test_abs_mauvais_nombre_d_arguments(self):
        self.rejeter("const N = abs(1, 2);", "abs attend 1 argument")

    def test_tranche_hors_contrainte_globale(self):
        self.rejeter("const N = 2; array a[N] : 1..N; constraint a[*] = 1;",
                     "tranche n'est permise")


class TestDeroulage(unittest.TestCase):
    def test_forall_remplace_par_ses_instances(self):
        c = contraintes("const N = 3; array a[N] : 1..N; "
                        "forall i in 1..N { constraint a[i] != 1; }")
        self.assertEqual(c, [Cmp("!=", Case("a", (i,)), Val("int", 1)) for i in (1, 2, 3)])

    def test_iterateurs_imbriques_et_bornes_dependantes(self):
        c = contraintes("const N = 3; array a[N] : 1..N; "
                        "forall i in 1..N, j in i..N { constraint a[i] != a[j]; }")
        self.assertEqual(len(c), 6)        # (1,1) (1,2) (1,3) (2,2) (2,3) (3,3)

    def test_intervalle_vide(self):
        self.assertEqual(contraintes("var b : bool; forall i in 3..1 { constraint b; }"), [])

    def test_iteration_sur_un_type_enumere(self):
        c = contraintes("enum C = { Red, Green }; array u[C] : bool; "
                        "forall z in C { constraint u[z]; }")
        self.assertEqual(c, [Case("u", (0,)), Case("u", (1,))])


class TestSimplification(unittest.TestCase):
    def test_contrainte_toujours_vraie_disparait(self):
        self.assertEqual(contraintes("const N = 3; constraint N = 3;"), [])

    def test_contrainte_toujours_fausse_avertit(self):
        flux = io.StringIO()
        with redirect_stderr(flux):
            m = modele("const N = 3; constraint N = 4;")
        self.assertTrue(m.insatisfiable)
        self.assertIn("insatisfiable", flux.getvalue())

    def test_connecteur_a_operande_connu(self):
        # `N = 4` est faux : `faux and e` donne faux, la contrainte disparait
        flux = io.StringIO()
        with redirect_stderr(flux):
            m = modele("const N = 3; var b : bool; constraint N = 4 and b;")
        self.assertTrue(m.insatisfiable)

    def test_not_d_une_comparaison_est_normalise(self):
        c = contraintes("var x : 1..3; constraint not x = 2;")
        self.assertEqual(c, [Cmp("!=", Case("x", ()), Val("int", 2))])

    def test_court_circuit_protege_un_acces_hors_bornes(self):
        """Exemple de l'enonce : la condition fausse empeche d'evaluer grid[N+1]."""
        c = contraintes("const N = 3; array g[N][N] : 1..N; "
                        "forall i in 1..N { constraint i < N -> g[i + 1][1] != g[i][1]; }")
        self.assertEqual(len(c), 2)        # i = 3 filtre, aucune erreur

    def test_acces_hors_bornes_non_protege_est_signale(self):
        with self.assertRaises(ErreurModele):
            modele("const N = 3; array g[N][N] : 1..N; "
                   "forall i in 1..N { constraint g[i + 1][1] != g[i][1]; }")

    def test_court_circuit_du_and(self):
        """`faux and e` donne faux sans evaluer e, meme si e est hors bornes.

        Le `or` englobant evite que la contrainte entiere devienne fausse : on
        verifie bien le court-circuit du `and`, pas la disparition du tout.
        """
        c = contraintes("const N = 3; var b : bool; array g[N] : 1..N; "
                        "forall i in 1..N { constraint b or (i > N and g[i + 1] = 1); }")
        self.assertEqual(c, [Case("b", ())] * 3)


class TestTranchesEtGlobales(unittest.TestCase):
    def test_tranche_developpee(self):
        c = contraintes("const N = 3; array a[N] : 1..N; constraint allDifferent(a[*]);")
        self.assertEqual(c, [Glob("allDifferent", [Case("a", (i,)) for i in (1, 2, 3)])])

    def test_tranche_partielle(self):
        c = contraintes("const N = 2; array g[N][N] : 1..N; constraint allDifferent(g[1][*]);")
        self.assertEqual(c, [Glob("allDifferent", [Case("g", (1, 1)), Case("g", (1, 2))])])

    def test_arguments_melanges(self):
        c = contraintes("const N = 2; array a[N] : 1..N; constraint allDifferent(a[*], 2);")
        self.assertEqual(c[0].args, [Case("a", (1,)), Case("a", (2,)), Val("int", 2)])

    def test_all_different_sur_booleens_refuse(self):
        with self.assertRaises(ErreurModele):
            modele("var a : bool; var b : bool; constraint allDifferent(a, b);")

    def test_all_different_valeurs_connues_egales(self):
        flux = io.StringIO()
        with redirect_stderr(flux):
            m = modele("var x : 1..3; constraint allDifferent(x, 2, 2);")
        self.assertTrue(m.insatisfiable)

    def test_comprehension(self):
        c = contraintes("const N = 2; array c[N][N] : bool; "
                        "constraint atLeastOne(c[i][j] for i in 1..N, j in 1..N where i = j);")
        self.assertEqual(c, [Glob("atLeastOne", [Case("c", (1, 1)), Case("c", (2, 2))])])

    def test_condition_de_comprehension_doit_etre_connue(self):
        with self.assertRaises(ErreurModele):
            modele("const N = 2; array c[N] : bool; var b : bool; "
                   "constraint atLeastOne(c[i] for i in 1..N where b);")


if __name__ == "__main__":
    unittest.main()
