"""Q3 — Table des symboles et valeurs connues a la compilation.

Tous les noms du langage (constantes, types enumeres, valeurs enumerees,
variables, tableaux, indices de boucle) partagent **un meme espace de noms**,
comme le demande l'enonce : la table est donc unique, et chaque entree porte
son genre.

Les valeurs connues a la compilation sont des entiers types (`Val`) :

  - `Val("int", 3)` pour un entier ;
  - `Val("bool", 1)` pour vrai ;
  - `Val("Color", 0)` pour la premiere valeur declaree du type `Color`.

Les valeurs d'un type enumere sont numerotees 0, 1, ... dans l'ordre de
declaration et traitees comme des entiers (enonce, question 4). Le type est
conserve a cote de l'entier pour pouvoir rejeter `color[1] = 3`, qui compare
une couleur a un entier.
"""

from dataclasses import dataclass, field


class ErreurModele(Exception):
    """Modele syntaxiquement correct mais depourvu de sens.

    Toujours levee avec un message qui explique l'erreur, et, quand le noeud
    fautif porte sa position, prefixee par `line L, column C: `.
    """


def erreur(noeud, message: str) -> ErreurModele:
    """Construit une ErreurModele situee dans le texte du modele."""
    ou = noeud.ou() if hasattr(noeud, "ou") else ""
    return ErreurModele(f"{ou}{message}")


# ------------------------------------------------------------
# Valeurs et domaines
# ------------------------------------------------------------

@dataclass(frozen=True)
class Val:
    """Valeur connue a la compilation : un entier et son type."""

    type: str            # "int", "bool", ou le nom d'un type enumere
    n: int

    def __str__(self) -> str:
        return str(self.n)


@dataclass(frozen=True)
class Domaine:
    """Domaine fini d'une variable : un type et la liste de ses valeurs."""

    type: str
    valeurs: tuple[int, ...]

    def __len__(self) -> int:
        return len(self.valeurs)

    def contient(self, n: int) -> bool:
        return n in self.valeurs


BOOL = Domaine("bool", (0, 1))


# ------------------------------------------------------------
# Entrees de la table
# ------------------------------------------------------------

@dataclass
class Entree:
    """Ce que la table sait d'un nom.

    Selon le genre, seuls certains champs sont renseignes :

    | genre        | champs utiles            |
    |--------------|--------------------------|
    | const        | valeur                   |
    | enum_type    | valeurs_enum             |
    | enum_value   | valeur (type = l'enum)   |
    | const_array  | dims, donnees            |
    | var          | domaine                  |
    | array        | dims, domaine            |
    | index        | valeur (pose par la boucle) |
    """

    nom: str
    genre: str
    valeur: Val | None = None
    valeurs_enum: tuple[str, ...] = ()
    dims: tuple[int, ...] = ()
    domaine: Domaine | None = None
    donnees: object = None          # tableau constant, imbrique


@dataclass
class Table:
    """Noms declares, dans l'ordre de declaration."""

    entrees: dict[str, Entree] = field(default_factory=dict)

    def __contains__(self, nom: str) -> bool:
        return nom in self.entrees

    def __getitem__(self, nom: str) -> Entree:
        return self.entrees[nom]

    def __len__(self) -> int:
        return len(self.entrees)

    def declarer(self, noeud, entree: Entree) -> Entree:
        if entree.nom in self.entrees:
            raise erreur(noeud, f"'{entree.nom}' est declare deux fois")
        self.entrees[entree.nom] = entree
        return entree

    def chercher(self, noeud, nom: str) -> Entree:
        if nom not in self.entrees:
            raise erreur(noeud, f"'{nom}' n'est pas declare")
        return self.entrees[nom]

    @property
    def declarations_de_variables(self) -> list[Entree]:
        """Entrees `var` et `array`, dans l'ordre de declaration."""
        return [e for e in self.entrees.values() if e.genre in ("var", "array")]

    def nom_de_valeur(self, domaine: Domaine, n: int) -> str:
        """Nom lisible d'une valeur : `5`, `true`, `Red`."""
        if domaine.type == "bool":
            return "true" if n else "false"
        if domaine.type == "int":
            return str(n)
        return self.entrees[domaine.type].valeurs_enum[n]
