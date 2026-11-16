"""Q6 — D'une grille Meowdoku (partie I) a un modele du langage.

Un modele se compose des **donnees** de la grille, qui changent d'une grille a
l'autre, suivies des **regles du jeu**, ecrites une fois pour toutes. Ce module
produit les deux, pour les deux modelisations comparees par l'enonce.

Modele `positions` — une variable par region
    row[z] et col[z] donnent la ligne et la colonne du chat de la region z.
    Une solution est decrite par la liste des positions des chats.
    Suppose N = M = K.

Modele `cases` — une variable booleenne par case
    cat[i][j] dit si la case (i, j) porte un chat, comme en partie I.

La regle « au plus un chat par region » (question 6.2) ne se laisse pas ecrire
avec une tranche : aucune tranche ne designe les cases d'une region. Deux
ecritures sont possibles dans le langage :

  - parcourir les couples de cases et tester l'egalite des regions, ce qui
    coute O(N^2 M^2) instances de boucle ;
  - utiliser une **liste en comprehension** (extension du langage, cf. la
    question optionnelle de l'enonce), ce qui coute O(N M K) et se lit comme la
    regle elle-meme.

C'est la seconde qui est retenue ; la premiere est disponible par l'option
`--sans-comprehension`, pour pouvoir comparer.

Usage :

    python -m partie_2.meowdoku grids/figure1.txt --modele cases
    python -m partie_2.meowdoku grids/figure1.txt --modele cases --redondant
    python -m partie_2.meowdoku grids/figure1.txt --modele positions -o m.csp
"""

import argparse
import sys

from src.meowdoku.grid import Grid, GridError, read_grid


# Noms que le modele introduit. Ils partagent l'espace de noms du langage avec
# les noms de regions, qui viennent du fichier de grille : une grille de 11
# regions en nomme une « K », qui entrerait en collision avec `const K`. On
# ecarte donc chaque nom des noms de regions avant d'ecrire le modele.
NOMS = ("N", "M", "K", "Zone", "region", "row", "col", "cat",
        "i", "j", "k", "l", "z", "z1", "z2")


def noms_surs(zones) -> dict[str, str]:
    """Nom libre pour chaque identifiant du modele, vu les noms de regions."""
    pris = set(zones)
    choisis = {}
    for base in NOMS:
        nom = base
        while nom in pris:
            nom += "_"
        choisis[base] = nom
        pris.add(nom)
    return choisis


def declarations(grid: Grid, noms: dict[str, str]) -> list[str]:
    """Donnees de la grille : dimensions, type enumere des regions, tableau region."""
    lignes = [
        f"// Grille {grid.n_rows}x{grid.n_cols}, {len(grid.zones)} regions.",
        f"const {noms['N']} = {grid.n_rows};   // lignes",
        f"const {noms['M']} = {grid.n_cols};   // colonnes",
        f"const {noms['K']} = {len(grid.zones)};   // regions",
        f"enum {noms['Zone']} = {{ {', '.join(grid.zones)} }};",
        f"const {noms['region']}[{noms['N']}][{noms['M']}] = [",
    ]
    for i, row in enumerate(grid.cells):
        virgule = "," if i < grid.n_rows - 1 else ""
        lignes.append(f"  [{', '.join(row)}]{virgule}")
    lignes.append("];")
    return lignes


REGLES_POSITIONS = """
// --- Modele 1 : la position du chat de chaque region ---
array {row}[{Zone}] : 1..{N};
array {col}[{Zone}] : 1..{M};

// au plus un chat par ligne et par colonne
constraint allDifferent({row}[*]);
constraint allDifferent({col}[*]);

// le chat de la region {z} est dans la region {z}
forall {z} in {Zone}, {i} in 1..{N}, {j} in 1..{M} {{
  constraint {region}[{i}][{j}] != {z} -> not ({row}[{z}] = {i} and {col}[{z}] = {j});
}}

// pas deux chats voisins (en diagonale : lignes et colonnes sont distinctes)
forall {z1} in {Zone}, {z2} in {Zone}, {i} in 1..{N}, {j} in 1..{M},
       {k} in ({i} - 1)..({i} + 1), {l} in ({j} - 1)..({j} + 1) {{
  constraint {z1} < {z2} and {k} != {i} and {l} != {j}
    -> not ({row}[{z1}] = {i} and {col}[{z1}] = {j}
            and {row}[{z2}] = {k} and {col}[{z2}] = {l});
}}
"""

REGLES_CASES_ENTETE = """
// --- Modele 2 : une variable booleenne par case ---
array {cat}[{N}][{M}] : bool;
"""

REGLES_CASES_LIGNES_COLONNES = """
// exactement un chat par ligne et par colonne (valable car N = M = K)
forall {i} in 1..{N} {{ constraint exactlyOne({cat}[{i}][*]); }}
forall {j} in 1..{M} {{ constraint exactlyOne({cat}[*][{j}]); }}
"""

REGLES_CASES_LIGNES_COLONNES_GENERAL = """
// au plus un chat par ligne et par colonne (cas general : N, M et K libres)
forall {i} in 1..{N} {{ constraint atMostOne({cat}[{i}][*]); }}
forall {j} in 1..{M} {{ constraint atMostOne({cat}[*][{j}]); }}
"""

REGLES_CASES_VOISINAGE = """
// pas deux chats voisins (lignes et colonnes sont deja exclusives)
forall {i} in 1..({N} - 1), {j} in 1..{M}, {l} in ({j} - 1)..({j} + 1) {{
  constraint {l} >= 1 and {l} <= {M} and {l} != {j}
    -> not ({cat}[{i}][{j}] and {cat}[{i} + 1][{l}]);
}}
"""


REGLES_REGIONS_COMPR = """
// {quantite} un chat par region
forall {z} in {Zone} {{
  constraint {cardinalite}({cat}[{i}][{j}] for {i} in 1..{N}, {j} in 1..{M}
                           where {region}[{i}][{j}] = {z});
}}
"""

REGLES_REGIONS_COUPLES = """
// au plus un chat par region, sans comprehension : on parcourt les couples de
// cases et on ne garde que ceux d'une meme region (O(N^2 M^2) instances).
forall {i} in 1..{N}, {j} in 1..{M}, {k} in {i}..{N}, {l} in 1..{M} {{
  constraint ({i} < {k} or {j} < {l})
             and {region}[{i}][{j}] = {region}[{k}][{l}]
    -> not ({cat}[{i}][{j}] and {cat}[{k}][{l}]);
}}
"""


def regles_regions(cardinalite: str, comprehension: bool, noms: dict[str, str]) -> str:
    """Regle par region : `atMostOne` seule, ou `exactlyOne` (contrainte redondante)."""
    if comprehension:
        quantite = "exactement" if cardinalite == "exactlyOne" else "au plus"
        return REGLES_REGIONS_COMPR.format(cardinalite=cardinalite, quantite=quantite, **noms)
    if cardinalite != "atMostOne":
        raise ValueError("« au moins un par region » demande les listes en comprehension")
    return REGLES_REGIONS_COUPLES.format(**noms)


def modele(grid: Grid, forme: str = "cases", redondant: bool = False,
           general: bool = False, comprehension: bool = True) -> str:
    """Texte complet d'un modele `.csp` pour cette grille."""
    noms = noms_surs(grid.zones)
    lignes = declarations(grid, noms)
    if forme == "positions":
        if not (grid.n_rows == grid.n_cols == len(grid.zones)):
            raise ValueError("le modele 'positions' suppose N = M = K")
        lignes.append(REGLES_POSITIONS.format(**noms))
        return "\n".join(lignes) + "\n"

    lignes.append(REGLES_CASES_ENTETE.format(**noms))
    carre = grid.n_rows == grid.n_cols == len(grid.zones)
    if general or not carre:
        lignes.append(REGLES_CASES_LIGNES_COLONNES_GENERAL.format(**noms))
        cardinalite = "exactlyOne"       # au cas general, la region porte toute la cardinalite
    else:
        lignes.append(REGLES_CASES_LIGNES_COLONNES.format(**noms))
        cardinalite = "exactlyOne" if redondant else "atMostOne"
    lignes.append(REGLES_CASES_VOISINAGE.format(**noms))
    lignes.append(regles_regions(cardinalite, comprehension, noms))
    return "\n".join(lignes) + "\n"


def positions_depuis_valeurs(valeurs, noms: dict[str, str] | None = None
                             ) -> set[tuple[int, int]]:
    """Cases portant un chat, d'apres la sortie de `solve.resoudre`.

    Accepte les deux modeles : `cat[i][j] = true`, ou `row[A] = 3` et
    `col[A] = 2`. `noms` donne les identifiants reellement employes (voir
    `noms_surs`) ; par defaut on prend les noms de base.
    """
    noms = noms or {b: b for b in NOMS}
    prefixe_cat, prefixe_row, prefixe_col = (f"{noms[b]}[" for b in ("cat", "row", "col"))
    chats = set()
    lignes, colonnes = {}, {}
    for nom, valeur in valeurs:
        if nom.startswith(prefixe_cat) and valeur == "true":
            i, j = (int(x) for x in nom[len(prefixe_cat):-1].split("]["))
            chats.add((i, j))
        elif nom.startswith(prefixe_row):
            lignes[nom[len(prefixe_row):-1]] = int(valeur)
        elif nom.startswith(prefixe_col):
            colonnes[nom[len(prefixe_col):-1]] = int(valeur)
    chats |= {(lignes[z], colonnes[z]) for z in lignes if z in colonnes}
    return chats


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="python -m partie_2.meowdoku",
        description="Convertit une grille Meowdoku en modele de contraintes.",
    )
    ap.add_argument("grille", help="fichier de grille au format de la partie I")
    ap.add_argument("--modele", choices=("positions", "cases"), default="cases")
    ap.add_argument("--redondant", action="store_true",
                    help="ajoute « au moins un chat par region » (question 6.4)")
    ap.add_argument("--general", action="store_true",
                    help="regles valables pour N, M et K quelconques (question 6.5)")
    ap.add_argument("--sans-comprehension", action="store_true",
                    help="ecrit la regle des regions sans liste en comprehension")
    ap.add_argument("-o", "--output", default=None, help="fichier de sortie (defaut : stdout)")
    args = ap.parse_args(argv)

    try:
        grid = read_grid(args.grille)
        texte = modele(grid, args.modele, args.redondant, args.general,
                       comprehension=not args.sans_comprehension)
    except (GridError, ValueError, OSError) as e:
        sys.exit(str(e))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(texte)
    else:
        sys.stdout.write(texte)


if __name__ == "__main__":
    main()
