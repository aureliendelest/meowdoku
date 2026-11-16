"""Q3 — Analyse de l'arbre, deroulage des boucles et simplification.

Deux passes.

**Declarations.** On remplit la table des symboles : constantes, types
enumeres et leurs valeurs, tableaux de donnees, variables, tableaux de
variables. Les tailles de tableaux et les bornes de domaines doivent etre des
valeurs connues, donc elles sont calculees ici.

**Contraintes.** On parcourt les instructions dans l'ordre. Chaque `forall`
est remplace par ses instances, chaque tranche par la liste des cases qu'elle
designe, et toute partie calculable est calculee. Le resultat est une liste de
contraintes sans boucle, qui ne portent plus que sur des cases de variables.

Le calcul est **paresseux**, comme l'exige l'enonce. Dans

    forall i in 1..N { constraint i < N -> grid[i + 1][1] != grid[i][1]; }

la condition `i < N` est fausse pour i = N : l'implication est vraie, la
contrainte disparait, et `grid[N + 1][1]`, hors du tableau, n'est jamais
evalue. Une condition sur des valeurs connues joue donc le role d'un filtre.
En revanche un acces hors bornes reellement evalue est une erreur.

La simplification est faite au vol plutot qu'en une passe separee : `booleen`
renvoie `True`, `False`, ou une expression, et chaque connecteur exploite
immediatement ce que ses operandes ont donne. C'est ce qui rend le
court-circuit naturel : pour `->`, on ne regarde la droite que si la gauche
n'est pas fausse.
"""

import sys
from dataclasses import dataclass, field

from .ir import OPPOSE, Case, Cmp, Glob
from .symbols import BOOL, Domaine, Entree, ErreurModele, Table, Val, erreur
from .syntax import (And, ArrayDecl, ArrayLit, BinOp, BoolDomain, Call, Compare,
                     Compr, ConstArrayDecl, ConstDecl, Constraint, EnumDecl,
                     Forall, Implies, Index, IntLit, NamedDomain, NamedSet, Neg,
                     Not, Or, Program, RangeDomain, RangeSet, Var, VarDecl,
                     Wildcard, pretty_expr)

GLOBALES_BOOLEENNES = ("atLeastOne", "atMostOne", "exactlyOne")
GLOBALES_TERMES = ("allDifferent",)
GLOBALES = GLOBALES_BOOLEENNES + GLOBALES_TERMES


@dataclass(frozen=True)
class Dim:
    """Une dimension d'un tableau : une taille (indices 1..n) ou un type enumere."""

    type: str            # "int" ou le nom d'un type enumere
    taille: int

    @property
    def indices(self) -> range:
        return range(1, self.taille + 1) if self.type == "int" else range(self.taille)


@dataclass
class Modele:
    """Resultat de l'analyse : la table et les contraintes deroulees."""

    table: Table
    contraintes: list = field(default_factory=list)
    insatisfiable: bool = False   # une contrainte s'est simplifiee en faux


def cases_de(entree: Entree) -> list[Case]:
    """Toutes les cases d'une declaration, dans l'ordre ligne par ligne."""
    if entree.genre == "var":
        return [Case(entree.nom, ())]
    produit = [()]
    for d in entree.dims:
        produit = [t + (i,) for t in produit for i in d.indices]
    return [Case(entree.nom, t) for t in produit]


class Analyseur:
    def __init__(self):
        self.table = Table()
        self.modele = Modele(self.table)

    # ------------------------------------------------------------------
    # Declarations
    # ------------------------------------------------------------------

    def declarations(self, programme: Program) -> None:
        for s in programme.statements:
            if isinstance(s, ConstDecl):
                self.table.declarer(s, Entree(s.name, "const", valeur=self.valeur(s.value)))
            elif isinstance(s, EnumDecl):
                self.declarer_enum(s)
            elif isinstance(s, ConstArrayDecl):
                self.declarer_tableau_constant(s)
            elif isinstance(s, VarDecl):
                self.table.declarer(s, Entree(s.name, "var", domaine=self.domaine(s.domain)))
            elif isinstance(s, ArrayDecl):
                self.table.declarer(s, Entree(s.name, "array",
                                              dims=self.dimensions(s.dims),
                                              domaine=self.domaine(s.domain)))

    def declarer_enum(self, s: EnumDecl) -> None:
        if len(set(s.values)) != len(s.values):
            raise erreur(s, f"valeurs dupliquees dans le type '{s.name}'")
        self.table.declarer(s, Entree(s.name, "enum_type", valeurs_enum=tuple(s.values)))
        for i, v in enumerate(s.values):
            self.table.declarer(s, Entree(v, "enum_value", valeur=Val(s.name, i)))

    def declarer_tableau_constant(self, s: ConstArrayDecl) -> None:
        dims = self.dimensions(s.dims)
        donnees = self.lire_donnees(s.value, dims, s)
        self.table.declarer(s, Entree(s.name, "const_array", dims=dims, donnees=donnees))

    def lire_donnees(self, valeur, dims: tuple[Dim, ...], noeud):
        """Verifie la forme d'un tableau de donnees et evalue ses cases."""
        if not dims:
            return self.valeur(valeur)
        if not isinstance(valeur, ArrayLit):
            raise erreur(noeud, f"{len(dims)} dimension(s) attendue(s), valeur simple trouvee")
        attendu = dims[0].taille
        if len(valeur.items) != attendu:
            raise erreur(valeur, f"{len(valeur.items)} element(s), {attendu} attendu(s)")
        return [self.lire_donnees(x, dims[1:], valeur) for x in valeur.items]

    def dimensions(self, exprs) -> tuple[Dim, ...]:
        """Chaque dimension est une taille connue ou un type enumere."""
        dims = []
        for e in exprs:
            if isinstance(e, Var) and e.name in self.table \
                    and self.table[e.name].genre == "enum_type":
                dims.append(Dim(e.name, len(self.table[e.name].valeurs_enum)))
                continue
            v = self.valeur(e)
            if v.type != "int":
                raise erreur(e, "une taille de tableau doit etre un entier")
            if v.n < 1:
                raise erreur(e, f"taille de tableau invalide : {v.n}")
            dims.append(Dim("int", v.n))
        return tuple(dims)

    def domaine(self, d) -> Domaine:
        if isinstance(d, BoolDomain):
            return BOOL
        if isinstance(d, RangeDomain):
            bas, haut = self.valeur(d.low), self.valeur(d.high)
            if bas.type != "int" or haut.type != "int":
                raise erreur(d, "les bornes d'un intervalle doivent etre des entiers")
            if bas.n > haut.n:
                raise erreur(d, f"intervalle vide : {bas.n}..{haut.n}")
            return Domaine("int", tuple(range(bas.n, haut.n + 1)))
        if isinstance(d, NamedDomain):
            e = d.expr
            if not isinstance(e, Var):
                raise erreur(d, "domaine invalide")
            entree = self.table.chercher(e, e.name)
            if entree.genre != "enum_type":
                raise erreur(e, f"'{e.name}' n'est pas un type enumere")
            return Domaine(e.name, tuple(range(len(entree.valeurs_enum))))
        raise erreur(d, "domaine invalide")

    # ------------------------------------------------------------------
    # Valeurs connues
    # ------------------------------------------------------------------

    def valeur(self, e) -> Val:
        """Valeur connue a la compilation, ou erreur."""
        t = self.terme(e)
        if isinstance(t, Case):
            raise erreur(e, f"'{pretty_expr(e)}' n'est pas une valeur connue a la compilation")
        return t

    def entier(self, e) -> int:
        v = self.valeur(e)
        if v.type != "int":
            raise erreur(e, "une valeur entiere est attendue ici")
        return v.n

    def terme(self, e):
        """Valeur connue (`Val`) ou case de variable (`Case`)."""
        if isinstance(e, IntLit):
            return Val("int", e.value)
        if isinstance(e, Var):
            return self.terme_nom(e)
        if isinstance(e, Index):
            return self.terme_indice(e)
        if isinstance(e, Neg):
            return Val("int", -self.entier(e.expr))
        if isinstance(e, BinOp):
            g, d = self.entier(e.left), self.entier(e.right)
            return Val("int", {"+": g + d, "-": g - d, "*": g * d}[e.op])
        if isinstance(e, Call):
            if e.name == "abs":
                if len(e.args) != 1:
                    raise erreur(e, f"abs attend 1 argument, {len(e.args)} fourni(s)")
                return Val("int", abs(self.entier(e.args[0])))
            if e.name in GLOBALES:
                raise erreur(e, f"'{e.name}' est une contrainte, pas une valeur")
            raise erreur(e, f"fonction inconnue : '{e.name}'")
        if isinstance(e, Wildcard):
            raise erreur(e, "une tranche n'est permise qu'en argument d'une contrainte globale")
        if isinstance(e, Compr):
            raise erreur(e, "une comprehension n'est permise qu'en argument "
                            "d'une contrainte globale")
        raise erreur(e, "expression invalide dans une valeur")

    def terme_nom(self, e: Var):
        entree = self.table.chercher(e, e.name)
        if entree.genre in ("const", "enum_value", "index"):
            return entree.valeur
        if entree.genre == "var":
            return Case(e.name, ())
        if entree.genre in ("array", "const_array"):
            raise erreur(e, f"'{e.name}' est un tableau : des indices sont attendus")
        raise erreur(e, f"'{e.name}' est un type, pas une valeur")

    def terme_indice(self, e: Index):
        base, indices = aplatir_index(e)
        if not isinstance(base, Var):
            raise erreur(e, "seul un tableau peut etre indice")
        entree = self.table.chercher(base, base.name)
        if entree.genre not in ("array", "const_array"):
            raise erreur(base, f"'{base.name}' n'est pas un tableau")
        if len(indices) != len(entree.dims):
            raise erreur(e, f"'{base.name}' a {len(entree.dims)} dimension(s), "
                            f"{len(indices)} indice(s) fourni(s)")

        valeurs = []
        for rang, (expr_i, dim) in enumerate(zip(indices, entree.dims), start=1):
            if isinstance(expr_i, Wildcard):
                raise erreur(expr_i,
                             "une tranche n'est permise qu'en argument d'une contrainte globale")
            v = self.valeur(expr_i)
            if v.type != dim.type:
                raise erreur(expr_i, f"indice {rang} de '{base.name}' : type {v.type} fourni, "
                                     f"{dim.type} attendu")
            if v.n not in dim.indices:
                borne = f"{dim.indices.start}..{dim.indices.stop - 1}"
                raise erreur(expr_i, f"index {rang} of '{base.name}' is {v.n}, "
                                     f"out of range {borne}")
            valeurs.append(v.n)

        if entree.genre == "array":
            return Case(base.name, tuple(valeurs))
        donnees = entree.donnees
        for rang, (v, dim) in enumerate(zip(valeurs, entree.dims)):
            donnees = donnees[v - 1 if dim.type == "int" else v]
        return donnees

    # ------------------------------------------------------------------
    # Types
    # ------------------------------------------------------------------

    def type_de(self, t) -> str:
        return t.type if isinstance(t, Val) else self.domaine_de(t).type

    def domaine_de(self, case: Case) -> Domaine:
        return self.table[case.nom].domaine

    # ------------------------------------------------------------------
    # Expressions booleennes
    # ------------------------------------------------------------------

    def booleen(self, e):
        """`True`, `False`, ou une expression booleenne de la representation intermediaire.

        Les connecteurs sont court-circuites : pour `and`, une gauche fausse
        suffit ; pour `->`, une gauche fausse rend la contrainte vraie sans que
        la droite soit regardee.
        """
        if isinstance(e, Not):
            v = self.booleen(e.expr)
            if isinstance(v, bool):
                return not v
            if isinstance(v, Cmp):
                return Cmp(OPPOSE[v.op], v.gauche, v.droite)   # not (x = 2) -> x != 2
            return Not(v)

        if isinstance(e, And):
            g = self.booleen(e.left)
            if g is False:
                return False
            d = self.booleen(e.right)
            if d is False:
                return False
            if g is True:
                return d
            if d is True:
                return g
            return And(g, d)

        if isinstance(e, Or):
            g = self.booleen(e.left)
            if g is True:
                return True
            d = self.booleen(e.right)
            if d is True:
                return True
            if g is False:
                return d
            if d is False:
                return g
            return Or(g, d)

        if isinstance(e, Implies):
            g = self.booleen(e.left)
            if g is False:
                return True            # court-circuit : la droite n'est pas evaluee
            d = self.booleen(e.right)
            if d is True:
                return True
            if g is True:
                return d
            if d is False:
                return self.booleen(Not(e.left))
            return Implies(g, d)

        if isinstance(e, Compare):
            return self.comparaison(e)

        if isinstance(e, Call):
            return self.globale(e)

        # expression atomique : une variable booleenne ou une constante booleenne
        t = self.terme(e)
        if isinstance(t, Val):
            if t.type != "bool":
                raise erreur(e, f"valeur de type {t.type} la ou un booleen est attendu")
            return bool(t.n)
        if self.domaine_de(t).type != "bool":
            raise erreur(e, f"'{pretty_expr(e)}' n'est pas booleen")
        return t

    def comparaison(self, e: Compare):
        g, d = self.terme(e.left), self.terme(e.right)
        tg, td = self.type_de(g), self.type_de(d)
        if tg != td:
            raise erreur(e, f"comparaison entre {tg} et {td}")
        if tg == "bool" and e.op not in ("=", "!="):
            raise erreur(e, f"'{e.op}' ne s'applique pas aux booleens")
        if isinstance(g, Val) and isinstance(d, Val):
            return compare_entiers(e.op, g.n, d.n)
        return Cmp(e.op, g, d)

    # ------------------------------------------------------------------
    # Contraintes globales et tranches
    # ------------------------------------------------------------------

    def globale(self, e: Call):
        if e.name not in GLOBALES:
            raise erreur(e, f"contrainte globale inconnue : '{e.name}'")
        if not e.args:
            raise erreur(e, f"'{e.name}' attend au moins un argument")

        # Les arguments melangent librement expressions, tranches et
        # comprehensions ; chacun donne une liste de termes ou de booleens.
        booleenne = e.name in GLOBALES_BOOLEENNES
        finaux = []
        for a in e.args:
            if isinstance(a, Compr):
                finaux.extend(self.comprehension(a, booleenne))
                continue
            cases = self.developper_tranche(a)
            if cases is not None:
                finaux.extend(self.booleen_de_case(c) if booleenne else c for c in cases)
            else:
                finaux.append(self.booleen(a) if booleenne else self.terme(a))

        if booleenne:
            return simplifier_cardinalite(e, e.name, finaux)

        types = {self.type_de(x) for x in finaux}
        if len(types) > 1:
            raise erreur(e, f"allDifferent melange les types {sorted(types)}")
        if "bool" in types:
            raise erreur(e, "allDifferent ne s'applique pas aux booleens")
        return simplifier_all_different(e, finaux)

    def comprehension(self, c: Compr, booleenne: bool) -> list:
        """Developpe `e for i in S, j in T where cond` (extension du langage).

        La condition porte sur des valeurs connues : c'est un filtre evalue a
        la compilation, comme la condition d'un `forall`.
        """
        sortie = []

        def parcourir(rang: int) -> None:
            if rang == len(c.iterators):
                if c.condition is not None:
                    garde = self.booleen(c.condition)
                    if garde is False:
                        return
                    if garde is not True:
                        raise erreur(c.condition, "la condition d'une comprehension doit "
                                                  "etre connue a la compilation")
                sortie.append(self.booleen(c.expr) if booleenne else self.terme(c.expr))
                return
            nom, ensemble = c.iterators[rang]
            for valeur in self.valeurs_iterees(ensemble):
                self.table.declarer(c, Entree(nom, "index", valeur=valeur))
                try:
                    parcourir(rang + 1)
                finally:
                    del self.table.entrees[nom]

        parcourir(0)
        return sortie

    def booleen_de_case(self, c: Case):
        if self.domaine_de(c).type != "bool":
            raise erreur_case(c, "argument non booleen")
        return c

    def developper_tranche(self, e):
        """Liste des cases designees par une tranche, ou None si `e` n'en est pas une."""
        if not contient_joker(e):
            return None
        base, indices = aplatir_index(e)
        if not isinstance(base, Var):
            raise erreur(e, "seul un tableau peut etre tranche")
        entree = self.table.chercher(base, base.name)
        if entree.genre != "array":
            raise erreur(base, f"'{base.name}' n'est pas un tableau de variables")
        if len(indices) != len(entree.dims):
            raise erreur(e, f"'{base.name}' a {len(entree.dims)} dimension(s), "
                            f"{len(indices)} indice(s) fourni(s)")

        combinaisons = [()]
        for expr_i, dim in zip(indices, entree.dims):
            if isinstance(expr_i, Wildcard):
                combinaisons = [t + (i,) for t in combinaisons for i in dim.indices]
            else:
                v = self.valeur(expr_i)
                if v.type != dim.type:
                    raise erreur(expr_i, f"indice de type {v.type}, {dim.type} attendu")
                if v.n not in dim.indices:
                    raise erreur(expr_i, f"indice {v.n} hors bornes")
                combinaisons = [t + (v.n,) for t in combinaisons]
        return [Case(base.name, t) for t in combinaisons]

    # ------------------------------------------------------------------
    # Instructions et deroulage
    # ------------------------------------------------------------------

    def contraintes(self, programme: Program) -> None:
        for s in programme.statements:
            self.instruction(s)

    def instruction(self, s) -> None:
        if isinstance(s, Constraint):
            b = self.booleen(s.expr)
            if b is True:
                return                              # contrainte toujours vraie : elle disparait
            if b is False:
                print(f"avertissement: {s.ou()}contrainte toujours fausse, "
                      "le modele est insatisfiable", file=sys.stderr)
                self.modele.insatisfiable = True
                return
            self.modele.contraintes.append(b)
        elif isinstance(s, Forall):
            self.derouler(s, 0)
        elif isinstance(s, (ConstDecl, ConstArrayDecl, EnumDecl, VarDecl, ArrayDecl)):
            return                                   # deja traitee par la passe des declarations
        else:
            raise erreur(s, "instruction inattendue")

    def derouler(self, boucle: Forall, rang: int) -> None:
        """Remplace un `forall` par ses instances, un iterateur apres l'autre."""
        if rang == len(boucle.iterators):
            for s in boucle.body:
                if isinstance(s, (ConstDecl, ConstArrayDecl, EnumDecl, VarDecl, ArrayDecl)):
                    raise erreur(s, "une declaration ne peut pas figurer dans un forall")
                self.instruction(s)
            return
        nom, ensemble = boucle.iterators[rang]
        for valeur in self.valeurs_iterees(ensemble):
            self.table.declarer(boucle, Entree(nom, "index", valeur=valeur))
            try:
                self.derouler(boucle, rang + 1)
            finally:
                del self.table.entrees[nom]

    def valeurs_iterees(self, ensemble) -> list[Val]:
        """Valeurs parcourues par un iterateur : un intervalle ou un type enumere."""
        if isinstance(ensemble, RangeSet):
            bas, haut = self.entier(ensemble.low), self.entier(ensemble.high)
            return [Val("int", n) for n in range(bas, haut + 1)]   # vide si bas > haut
        e = ensemble.expr
        if isinstance(e, Var) and e.name in self.table \
                and self.table[e.name].genre == "enum_type":
            entree = self.table[e.name]
            return [Val(e.name, i) for i in range(len(entree.valeurs_enum))]
        raise erreur(ensemble, "un ensemble d'iteration est un intervalle ou un type enumere")


# ------------------------------------------------------------
# Utilitaires
# ------------------------------------------------------------

def aplatir_index(e):
    """Index(Index(Var('grid'), i), j) -> (Var('grid'), [i, j])."""
    indices = []
    while isinstance(e, Index):
        indices.append(e.index)
        e = e.base
    indices.reverse()
    return e, indices


def contient_joker(e) -> bool:
    while isinstance(e, Index):
        if isinstance(e.index, Wildcard):
            return True
        e = e.base
    return False


def compare_entiers(op: str, g: int, d: int) -> bool:
    return {"=": g == d, "!=": g != d, "<": g < d,
            "<=": g <= d, ">": g > d, ">=": g >= d}[op]


def erreur_case(case: Case, message: str) -> ErreurModele:
    indices = "".join(f"[{i}]" for i in case.indices)
    return ErreurModele(f"{case.nom}{indices} : {message}")


def simplifier_cardinalite(noeud, nom: str, args: list):
    """Elimine les arguments deja connus de atLeastOne / atMostOne / exactlyOne."""
    vrais = sum(1 for a in args if a is True)
    restants = [a for a in args if not isinstance(a, bool)]
    if nom == "atLeastOne":
        if vrais:
            return True
        return False if not restants else Glob(nom, restants)
    if nom == "atMostOne":
        if vrais > 1:
            return False
        if vrais == 1:
            return Not(Glob("atLeastOne", restants)) if restants else True
        return True if len(restants) <= 1 else Glob(nom, restants)
    # exactlyOne
    if vrais > 1:
        return False
    if vrais == 1:
        return Not(Glob("atLeastOne", restants)) if restants else True
    return False if not restants else Glob(nom, restants)


def simplifier_all_different(noeud, args: list):
    """Deux valeurs connues egales rendent allDifferent faux."""
    connues = [a.n for a in args if isinstance(a, Val)]
    if len(set(connues)) != len(connues):
        return False
    return True if len(args) <= 1 else Glob("allDifferent", args)


def analyser(programme: Program) -> Modele:
    """Arbre de syntaxe -> table des symboles et contraintes deroulees."""
    a = Analyseur()
    a.declarations(programme)
    a.contraintes(programme)
    return a.modele
