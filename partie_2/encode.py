"""Q4 — Des contraintes sur des cases a une formule propositionnelle.

Apres la question 3, les contraintes ne portent plus que sur des cases de
variables, mais celles-ci ne sont pas toutes booleennes : une variable de
domaine 1..9 ne peut pas etre donnee telle quelle a un solveur SAT.

**Encodage direct.** Une variable x de domaine {v1, ..., vk} est representee
par k variables booleennes x_v1, ..., x_vk, ou x_v est vraie si et seulement si
x vaut v. Toute valuation de ces k variables ne represente pas une valeur de x :
on ajoute les clauses qui imposent qu'exactement une soit vraie (au moins une :
une clause large ; au plus une : une clause binaire par couple).

Une variable `bool` reste **une seule** variable booleenne : x_1 est la
variable elle-meme et x_0 son oppose. Aucune clause de domaine n'est donc
necessaire, et on economise une variable et quatre clauses par case booleenne.

Les valeurs d'un type enumere sont numerotees 0, 1, ... dans l'ordre de
declaration et traitees comme des entiers.

**Comparaisons.** Plusieurs traductions sont souvent possibles ; les choix
retenus sont expliques devant chaque fonction.

**Contraintes globales.** `atMostOne` utilise l'encodage deux a deux impose par
l'enonce : une clause binaire par couple, n(n-1)/2 clauses, aucune variable
auxiliaire. `allDifferent` se ramene a « pour chaque valeur v, au plus une des
variables vaut v ».
"""

from .analyze import Modele, cases_de
from .ir import SYMETRIQUE, Case, Cmp, Glob
from .symbols import Domaine, Val
from .syntax import And, Implies, Not, Or
from .tseitin import Fnc, Tseitin, au_moins_une, et, non, ou, toutes


class Encodeur:
    """Attribue les variables SAT et traduit les contraintes."""

    def __init__(self, modele: Modele):
        self.modele = modele
        self.table = modele.table
        self.litteraux: dict[tuple[Case, int], int] = {}
        self.cases: list[tuple[Case, Domaine]] = []
        self.compteur = 0
        self.declarer()

    # ------------------------------------------------------------------
    # Encodage direct des domaines
    # ------------------------------------------------------------------

    def declarer(self) -> None:
        """Une variable booleenne par couple (case, valeur) ; une seule si le domaine est bool."""
        for entree in self.table.declarations_de_variables:
            domaine = entree.domaine
            for case in cases_de(entree):
                self.cases.append((case, domaine))
                if domaine.type == "bool":
                    self.compteur += 1
                    self.litteraux[(case, 1)] = self.compteur
                    self.litteraux[(case, 0)] = -self.compteur
                else:
                    for v in domaine.valeurs:
                        self.compteur += 1
                        self.litteraux[(case, v)] = self.compteur

    def clauses_de_domaine(self, tseitin: Tseitin) -> None:
        """exactlyOne(x_v1, ..., x_vk) pour chaque case de domaine non booleen."""
        for case, domaine in self.cases:
            if domaine.type == "bool":
                continue
            lits = [self.litteraux[(case, v)] for v in domaine.valeurs]
            tseitin.ajouter_clause(list(lits))                     # au moins une
            for i, a in enumerate(lits):                           # au plus une, deux a deux
                for b in lits[i + 1:]:
                    tseitin.ajouter_clause([-a, -b])

    def lit(self, case: Case, v: int):
        """Litteral « `case` vaut `v` », ou False si `v` n'est pas dans son domaine."""
        return self.litteraux.get((case, v), False)

    def domaine(self, case: Case) -> Domaine:
        return self.table[case.nom].domaine

    # ------------------------------------------------------------------
    # Traduction des contraintes
    # ------------------------------------------------------------------

    def traduire(self, e):
        """Expression de la representation intermediaire -> formule propositionnelle."""
        if isinstance(e, bool):
            return e
        if isinstance(e, Case):
            return self.lit(e, 1)                     # case booleenne
        if isinstance(e, Not):
            return non(self.traduire(e.expr))
        if isinstance(e, And):
            return et(self.traduire(e.left), self.traduire(e.right))
        if isinstance(e, Or):
            return ou(self.traduire(e.left), self.traduire(e.right))
        if isinstance(e, Implies):
            return ou(non(self.traduire(e.left)), self.traduire(e.right))
        if isinstance(e, Cmp):
            return self.comparaison(e)
        if isinstance(e, Glob):
            return self.globale(e)
        raise TypeError(f"expression intermediaire inattendue : {e!r}")

    # -- comparaisons ---------------------------------------------------

    def comparaison(self, c: Cmp):
        gauche, droite = c.gauche, c.droite
        if isinstance(gauche, Val):                   # on met toujours la case a gauche
            return self.comparaison(Cmp(SYMETRIQUE[c.op], droite, gauche))
        if isinstance(droite, Val):
            return self.case_valeur(c.op, gauche, droite.n)
        return self.case_case(c.op, gauche, droite)

    def case_valeur(self, op: str, case: Case, v: int):
        """Comparaison d'une case a une valeur connue.

        `x = 2` devient x_2 et `x != 2` devient non x_2 : un seul litteral.

        Pour un ordre, deux ecritures sont possibles : la disjonction des
        bonnes valeurs (`x <= 2` donne x_1 ou x_2, **une** clause) ou la
        conjonction des negations des mauvaises (`non x_3`, ici **une clause
        unitaire**). On choisit la plus courte des deux, a egalite la seconde,
        parce qu'une conjonction de litteraux negatifs donne des clauses
        unitaires, que DPLL propage immediatement.
        """
        domaine = self.domaine(case)
        if op == "=":
            return self.lit(case, v)
        if op == "!=":
            return non(self.lit(case, v))

        test = {"<": lambda u: u < v, "<=": lambda u: u <= v,
                ">": lambda u: u > v, ">=": lambda u: u >= v}[op]
        bonnes = [u for u in domaine.valeurs if test(u)]
        mauvaises = [u for u in domaine.valeurs if not test(u)]
        if not bonnes:
            return False
        if not mauvaises:
            return True
        if len(mauvaises) <= len(bonnes):
            return toutes([non(self.lit(case, u)) for u in mauvaises])
        return au_moins_une([self.lit(case, u) for u in bonnes])

    def case_case(self, op: str, x: Case, y: Case):
        """Comparaison entre deux cases.

        `x != y` s'ecrit comme dans l'enonce : non (x_v et y_v) pour chaque
        valeur v commune, soit |D| clauses binaires.

        `x = y` s'ecrit par double implication, x_v -> y_v et y_v -> x_v, ce
        qui reste clausal (2|D| clauses binaires). L'ecriture « disjonction des
        (x_v et y_v) » serait plus courte a lire mais imposerait Tseitin, donc
        des variables auxiliaires.

        Pour un ordre, on interdit les couples : non (x_u et y_v) pour tout
        couple (u, v) qui viole la comparaison. Cela donne O(|D|^2) clauses
        binaires, mais toutes de taille 2, donc tres propagatrices. Une
        alternative serait un encodage par ordre (variables « x <= v »), qui
        donnerait O(|D|) clauses au prix de nouvelles variables : voir le
        rapport.
        """
        dx, dy = self.domaine(x), self.domaine(y)
        if op == "=":
            parties = [implique_lit(self.lit(x, v), self.lit(y, v)) for v in dx.valeurs]
            parties += [implique_lit(self.lit(y, v), self.lit(x, v)) for v in dy.valeurs]
            return toutes(parties)
        if op == "!=":
            communes = [v for v in dx.valeurs if v in dy.valeurs]
            return toutes([ou(non(self.lit(x, v)), non(self.lit(y, v))) for v in communes])

        test = {"<": lambda u, v: u < v, "<=": lambda u, v: u <= v,
                ">": lambda u, v: u > v, ">=": lambda u, v: u >= v}[op]
        interdits = [(u, v) for u in dx.valeurs for v in dy.valeurs if not test(u, v)]
        return toutes([ou(non(self.lit(x, u)), non(self.lit(y, v))) for u, v in interdits])

    # -- contraintes globales --------------------------------------------

    def globale(self, g: Glob):
        if g.nom == "allDifferent":
            return self.all_different(g.args)
        formules = [self.traduire(a) for a in g.args]
        if g.nom == "atLeastOne":
            return au_moins_une(formules)
        if g.nom == "atMostOne":
            return au_plus_une(formules)
        if g.nom == "exactlyOne":
            return et(au_moins_une(formules), au_plus_une(formules))
        raise TypeError(f"contrainte globale inconnue : {g.nom}")

    def all_different(self, args):
        """Pour chaque valeur v, au plus une des expressions vaut v.

        Un argument qui est une valeur connue contribue un indicateur constant :
        vrai pour sa propre valeur, faux pour les autres.
        """
        valeurs = set()
        for a in args:
            valeurs |= set(self.domaine(a).valeurs) if isinstance(a, Case) else {a.n}
        parties = []
        for v in sorted(valeurs):
            indicateurs = [self.lit(a, v) if isinstance(a, Case) else (a.n == v) for a in args]
            parties.append(au_plus_une(indicateurs))
        return toutes(parties)


def implique_lit(a, b):
    """`a -> b` sous forme de clause quand a et b sont des litteraux ou des constantes."""
    return ou(non(a), b)


def au_plus_une(formules):
    """Encodage deux a deux impose par l'enonce : n(n-1)/2 clauses binaires.

    Les constantes sont absorbees d'abord : si deux arguments sont deja vrais,
    la contrainte est fausse ; si un seul l'est, tous les autres doivent etre
    faux.
    """
    vrais = sum(1 for f in formules if f is True)
    restants = [f for f in formules if not isinstance(f, bool)]
    if vrais > 1:
        return False
    if vrais == 1:
        return toutes([non(f) for f in restants])
    parties = []
    for i, a in enumerate(restants):
        for b in restants[i + 1:]:
            parties.append(ou(non(a), non(b)))
    return toutes(parties)


def encoder(modele: Modele) -> tuple[Fnc, Encodeur]:
    """Modele analyse -> FNC prete pour le solveur."""
    encodeur = Encodeur(modele)
    tseitin = Tseitin(encodeur.compteur)
    encodeur.clauses_de_domaine(tseitin)
    if modele.insatisfiable:
        tseitin.ajouter_clause([])
    for contrainte in modele.contraintes:
        tseitin.ajouter(encodeur.traduire(contrainte))
    return tseitin.resultat(), encodeur
