"""Q1 — Mise en forme normale conjonctive.

Ce module travaille sur des formules propositionnelles dont les **feuilles sont
des litteraux entiers** (`3` pour la variable 3, `-3` pour sa negation), et dont
les constantes sont les booleens `True` et `False` de Python. C'est ce que
produit l'encodage de la question 4 ; c'etait deja, a la question 1, ce que
donnait la table des symboles sur le fragment propositionnel.

Deux methodes existent pour mettre une formule en FNC.

La methode naive (De Morgan puis distribution de `ou` sur `et`) donne une
formule *logiquement equivalente*, mais sa taille peut exploser :
(a1 et b1) ou ... ou (an et bn) se distribue en 2^n clauses, car il faut
choisir dans chaque paire lequel des deux litteraux on garde.

La transformation de Tseitin introduit une variable auxiliaire par noeud de
l'arbre et reste lineaire. Elle n'est pas equivalente a la formule de depart
(elle parle de variables qui n'existaient pas) mais seulement
**equisatisfiable** :

  - tout modele de la FNC, restreint aux variables nommees, est un modele de
    la formule ;
  - tout modele de la formule s'etend, de facon unique, en un modele de la FNC.

Economies. Introduire une variable auxiliaire pour une contrainte qui est deja
une clause serait absurde. Trois cas se traitent directement :

  - `a and b` au sommet vaut deux contraintes separees (aplatissement) ;
  - une disjonction de litteraux est deja une clause ;
  - `a -> b` donne (non a ou b), `not (a and b)` donne (non a ou non b).

`clause_positive` / `clause_negative` reconnaissent ces cas ; on n'appelle
Tseitin que sur ce qui reste. Comme l'encodage de la question 4 produit presque
toujours des conjonctions de clauses, cette reconnaissance suffit en pratique :
aucune variable auxiliaire n'est creee sur les quatre modeles de `exemples/`.
"""

from dataclasses import dataclass, field

from .syntax import And, Implies, Not, Or

Clause = list[int]


# ------------------------------------------------------------
# Constructeurs simplifiants
# ------------------------------------------------------------
# Ils evitent de promener des constantes dans l'arbre : une formule construite
# avec eux ne contient `True` ou `False` que si elle est entierement constante.

def non(a):
    if isinstance(a, bool):
        return not a
    if isinstance(a, int):
        return -a
    if isinstance(a, Not):
        return a.expr
    return Not(a)


def et(a, b):
    if a is False or b is False:
        return False
    if a is True:
        return b
    if b is True:
        return a
    return And(a, b)


def ou(a, b):
    if a is True or b is True:
        return True
    if a is False:
        return b
    if b is False:
        return a
    return Or(a, b)


def implique(a, b):
    if a is False or b is True:
        return True
    if a is True:
        return b
    if b is False:
        return non(a)
    return Implies(a, b)


def toutes(formules):
    """Conjonction d'une liste, simplifiee."""
    resultat = True
    for f in formules:
        resultat = et(resultat, f)
        if resultat is False:
            return False
    return resultat


def au_moins_une(formules):
    """Disjonction d'une liste, simplifiee."""
    resultat = False
    for f in formules:
        resultat = ou(resultat, f)
        if resultat is True:
            return True
    return resultat


# ------------------------------------------------------------
# FNC
# ------------------------------------------------------------

@dataclass
class Fnc:
    """Clauses et nombre total de variables.

    `nb_nommees` separe les variables issues du modele (1..nb_nommees) des
    variables auxiliaires de Tseitin, qui n'ont pas de nom et ne sont jamais
    affichees.
    """

    nb_vars: int = 0
    nb_nommees: int = 0
    clauses: list[Clause] = field(default_factory=list)

    @property
    def nb_auxiliaires(self) -> int:
        return self.nb_vars - self.nb_nommees


class Tseitin:
    """Accumule les clauses d'un ensemble de contraintes."""

    def __init__(self, nb_vars: int, nb_nommees: int | None = None):
        self.compteur = nb_vars
        self.nb_nommees = nb_vars if nb_nommees is None else nb_nommees
        self.clauses: list[Clause] = []
        self.insatisfiable = False

    # -- numerotation ---------------------------------------------------

    def fraiche(self) -> int:
        self.compteur += 1
        return self.compteur

    # -- reconnaissance des clauses deja ecrites -------------------------

    def clause_positive(self, e) -> Clause | None:
        """Litteraux d'une clause equivalente a `e`, ou None si `e` n'en est pas une."""
        if isinstance(e, bool):
            return None
        if isinstance(e, int):
            return [e]
        if isinstance(e, Not):
            return self.clause_negative(e.expr)
        if isinstance(e, Or):
            gauche = self.clause_positive(e.left)
            if gauche is None:
                return None
            droite = self.clause_positive(e.right)
            return None if droite is None else gauche + droite
        if isinstance(e, Implies):
            gauche = self.clause_negative(e.left)      # a -> b vaut (non a) ou b
            if gauche is None:
                return None
            droite = self.clause_positive(e.right)
            return None if droite is None else gauche + droite
        return None                                     # And : pas une clause

    def clause_negative(self, e) -> Clause | None:
        """Litteraux d'une clause equivalente a `not e`, ou None."""
        if isinstance(e, bool):
            return None
        if isinstance(e, int):
            return [-e]
        if isinstance(e, Not):
            return self.clause_positive(e.expr)
        if isinstance(e, And):
            gauche = self.clause_negative(e.left)      # non (a et b) vaut (non a) ou (non b)
            if gauche is None:
                return None
            droite = self.clause_negative(e.right)
            return None if droite is None else gauche + droite
        return None                 # non (a ou b) et non (a -> b) sont des conjonctions

    # -- transformation --------------------------------------------------

    def definir(self, e) -> int:
        """Litteral equivalent a `e`, en ajoutant les clauses necessaires.

        La negation ne coute aucune variable : `not e` est le litteral oppose.
        """
        if isinstance(e, int):
            return e
        if isinstance(e, Not):
            return -self.definir(e.expr)
        if isinstance(e, And):
            a, b = self.definir(e.left), self.definir(e.right)
            t = self.fraiche()
            self.clauses += [[-t, a], [-t, b], [t, -a, -b]]
            return t
        if isinstance(e, Or):
            a, b = self.definir(e.left), self.definir(e.right)
            t = self.fraiche()
            self.clauses += [[-t, a, b], [t, -a], [t, -b]]
            return t
        if isinstance(e, Implies):
            a, b = self.definir(e.left), self.definir(e.right)
            t = self.fraiche()
            self.clauses += [[-t, -a, b], [t, a], [t, -b]]
            return t
        raise TypeError(f"formule inattendue : {e!r}")

    # -- contraintes ------------------------------------------------------

    def ajouter_clause(self, clause: Clause) -> None:
        self.clauses.append(clause)

    def ajouter(self, e) -> None:
        """Impose `e` : une clause directe quand c'en est une, Tseitin sinon."""
        for morceau in aplatir(e):
            if morceau is True:
                continue
            if morceau is False:
                self.insatisfiable = True
                self.clauses.append([])          # clause vide : formule fausse
                continue
            clause = self.clause_positive(morceau)
            self.clauses.append(clause if clause is not None else [self.definir(morceau)])

    def resultat(self) -> Fnc:
        return Fnc(self.compteur, self.nb_nommees, self.clauses)


def aplatir(e) -> list:
    """Conjonctions du sommet : `a and b and c` donne [a, b, c].

    Imposer une conjonction revient a imposer chacun de ses membres, ce qui
    evite une variable auxiliaire par `and` de tete.
    """
    if isinstance(e, And):
        return aplatir(e.left) + aplatir(e.right)
    return [e]


def evaluer(e, valeur) -> bool:
    """Valeur d'une formule, `valeur` donnant celle de chaque variable.

    Sert de reference aux tests : la FNC produite doit etre satisfiable si et
    seulement si la formule l'est.
    """
    if isinstance(e, bool):
        return e
    if isinstance(e, int):
        return valeur(abs(e)) == (e > 0)
    if isinstance(e, Not):
        return not evaluer(e.expr, valeur)
    if isinstance(e, And):
        return evaluer(e.left, valeur) and evaluer(e.right, valeur)
    if isinstance(e, Or):
        return evaluer(e.left, valeur) or evaluer(e.right, valeur)
    if isinstance(e, Implies):
        return (not evaluer(e.left, valeur)) or evaluer(e.right, valeur)
    raise TypeError(f"formule inattendue : {e!r}")
