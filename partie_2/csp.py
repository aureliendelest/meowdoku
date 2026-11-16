"""Ligne de commande du compilateur.

A lancer depuis la racine du depot, pour que `src` (partie I) soit importable :

    python -m partie_2.csp modele.csp                 # FNC au format DIMACS sur stdout
    python -m partie_2.csp modele.csp --dimacs f.cnf  # FNC ecrite dans f.cnf
    python -m partie_2.csp modele.csp --solve         # resolution par le solveur de la partie I
    python -m partie_2.csp modele.csp --ast           # arbre de syntaxe (comportement du code de depart)

Les erreurs (syntaxe, nom non declare, nom declare deux fois) sont signalees sur
stderr avec un code de retour 1, jamais par une exception Python.
"""

import argparse
import sys

from lark.exceptions import UnexpectedInput

from .dimacs import ecrire
from .solve import compiler_texte, formater, resoudre
from .symbols import ErreurModele
from .syntax import parse, pretty


def executer(args) -> None:
    with open(args.model, encoding="utf-8") as f:
        texte = f.read()

    if args.ast:
        print(pretty(parse(texte)))
        return

    compilation = compiler_texte(texte)

    if args.solve:
        print(formater(resoudre(compilation)), end="")
        return

    sortie = ecrire(compilation.fnc, compilation.encodeur,
                    (f"compile depuis {args.model}",))
    if args.dimacs:
        with open(args.dimacs, "w", encoding="utf-8") as f:
            f.write(sortie)
    else:
        sys.stdout.write(sortie)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="python -m partie_2.csp",
        description="Compile un modele de contraintes en FNC et le resout.",
    )
    ap.add_argument("model", help="fichier modele (.csp)")
    ap.add_argument("--dimacs", default=None, help="ecrit la FNC dans ce fichier")
    ap.add_argument("--solve", action="store_true", help="resout avec le solveur de la partie I")
    ap.add_argument("--ast", action="store_true", help="affiche l'arbre de syntaxe et s'arrete")
    args = ap.parse_args(argv)

    try:
        executer(args)
    except UnexpectedInput as e:
        sys.exit(f"{args.model}: {e}")
    except ErreurModele as e:
        sys.exit(f"{args.model}: {e}")
    except OSError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    # Pas de thread ici : le solveur optimise de la partie I cree lui-meme des
    # processus, chacun avec sa pile large, et on evite de forker depuis un
    # programme multi-thread (meme raison que dans sat.py).
    main()
