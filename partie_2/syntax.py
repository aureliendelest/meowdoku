r"""Q2 — Syntaxe du langage complet : grammaire Lark (LALR), AST, affichage.

    texte --(Lark)--> arbre d'analyse --(ASTBuilder)--> AST

Extension de la grammaire du fragment propositionnel fournie avec l'enonce.
Les priorites et associativites restent encodees *par la grammaire elle-meme*,
par niveaux successifs, du plus lache au plus serre :

    ->  <  or  <  and  <  not  <  comparaison  <  + -  <  *  <  - unaire  <  [ ]  <  atome

Consequences voulues, conformes a l'enonce :
  - `not x = 2` se lit `not (x = 2)` (la comparaison est plus prioritaire) ;
  - `a = b = c` est une erreur de syntaxe (la regle `comparison` n'est pas
    recursive, les comparaisons ne s'enchainent donc pas) ;
  - `a -> b -> c` se lit `a -> (b -> c)` (recursion a droite) ;
  - `a or b or c` se lit `(a or b) or c` (recursion a gauche).

Deux endroits demandent une remarque sur LALR(1) :

  - Un domaine ou un ensemble d'iteration s'ecrit `1..N` ou `Color`. Apres
    avoir lu une expression, le lexeme suivant (`..` ou autre) decide : c'est
    un conflit decalage/reduction que LALR resout en faveur du decalage, ce qui
    est le bon choix. On ne distingue donc pas un intervalle d'un type enumere
    dans la grammaire, mais a l'analyse (`analyze.py`).
  - `*` est a la fois la multiplication et le joker des tranches. Aucune
    expression ne commence par `*`, donc apres `[` ce lexeme ne peut etre qu'un
    joker : un seul lexeme de lecture avant suffit.

Les mots-cles de l'enonce (const, enum, var, array, bool, constraint, forall,
in, not, and, or) restent reserves : le lexeur "basic" les reconnait avant
NAME, donc `var and : bool;` est une erreur de syntaxe. Les noms de contraintes
globales (allDifferent, atMostOne, ...) et `abs` ne sont pas des mots-cles mais
de simples appels de fonction : en ajouter une ne touche pas a la grammaire.
"""

from dataclasses import dataclass

from lark import Lark, Transformer, v_args

GRAMMAR = r"""
?start: program

program: statement*

?statement: const_decl
          | enum_decl
          | var_decl
          | array_decl
          | constraint_decl
          | forall_stmt

// -------------------- DECLARATIONS --------------------

// const N = 9;  |  const region[2][3] = [[1, 1, 2], [3, 3, 2]];
const_decl: "const" NAME EQ value ";"                   -> const_decl
          | "const" NAME dim_list EQ value ";"          -> const_array_decl

// enum Color = { Red, Green, Blue };
enum_decl: "enum" NAME EQ "{" NAME ("," NAME)* "}" ";"

// var b : bool;  |  var x : 1..N;  |  var c : Color;
var_decl: "var" NAME ":" domain ";"

// array grid[N][N] : 1..N;  |  array used[Color] : bool;
array_decl: "array" NAME dim_list ":" domain ";"

dim_list: dim+
dim: "[" expr "]"

?domain: "bool"                                         -> bool_domain
       | sum ".." sum                                   -> range_domain
       | sum                                            -> named_domain

constraint_decl: "constraint" expr ";"

// forall i in 1..N, j in i..N { ... }
forall_stmt: "forall" iterator ("," iterator)* "{" statement* "}"
iterator: NAME "in" iter_set
?iter_set: sum ".." sum                                 -> range_set
         | sum                                          -> named_set

// valeur d'une constante : un entier, un nom, ou un tableau de donnees
?value: expr
      | array_lit
array_lit: "[" [value ("," value)*] "]"

// -------------------- EXPRESSIONS --------------------

?expr: implication

?implication: or_expr
            | or_expr "->" implication                  -> implies

?or_expr: and_expr
        | or_expr "or" and_expr                         -> or_op

?and_expr: not_expr
         | and_expr "and" not_expr                      -> and_op

// la comparaison est plus prioritaire que not : `not x = 2` = `not (x = 2)`
?not_expr: "not" not_expr                               -> not_op
         | comparison

// non recursive : `a = b = c` est une erreur de syntaxe
?comparison: sum
           | sum COMPOP sum                             -> compare
           | sum EQ sum                                 -> compare_eq

?sum: product
    | sum PLUS product                                  -> binop
    | sum MINUS product                                 -> binop

?product: unary
        | product "*" unary                             -> mul_op

?unary: MINUS unary                                     -> neg
      | postfix

?postfix: atom
        | postfix "[" index "]"                         -> index_op

?index: expr
      | "*"                                             -> wildcard

?atom: NAME                                             -> var_ref
     | INT                                              -> int_lit
     | NAME "(" [expr ("," expr)*] ")"                  -> call
     | NAME "(" compr ")"                               -> call_compr
     | "(" expr ")"

// Extension : liste en comprehension en argument d'une contrainte globale
//   atLeastOne(cat[i][j] for i in 1..N, j in 1..M where region[i][j] = z)
// `for` et `where` deviennent des mots reserves.
compr: expr "for" iterator ("," iterator)* ["where" expr]

// Terminaux nommes : "=" et "-" apparaissent a deux endroits de la grammaire
// (declaration et comparaison, somme et moins unaire). Les nommer evite que
// Lark cree deux terminaux anonymes concurrents pour le meme caractere.
EQ: "="
PLUS: "+"
MINUS: "-"
COMPOP: "!=" | "<=" | ">=" | "<" | ">"

%import common.CNAME -> NAME
%import common.INT
%import common.WS
%import common.CPP_COMMENT
%ignore WS
%ignore CPP_COMMENT
"""


# ------------------------------------------------------------
# AST
# ------------------------------------------------------------
# Une dataclass par construction. `pos` est pose comme attribut ordinaire
# (et non comme champ) par ASTBuilder : l'egalite des dataclasses reste
# structurelle, donc les tests peuvent comparer des arbres sans se soucier
# des positions.


class Noeud:
    """Base commune : porte la position (ligne, colonne) dans le texte."""

    pos: tuple[int, int] | None = None

    def ou(self) -> str:
        """Position formatee pour un message d'erreur, ou chaine vide."""
        return f"line {self.pos[0]}, column {self.pos[1]}: " if self.pos else ""


# -- instructions ---------------------------------------------------------

@dataclass
class Program(Noeud):
    statements: list


@dataclass
class ConstDecl(Noeud):
    name: str
    value: object


@dataclass
class ConstArrayDecl(Noeud):
    name: str
    dims: list
    value: object


@dataclass
class EnumDecl(Noeud):
    name: str
    values: list


@dataclass
class VarDecl(Noeud):
    name: str
    domain: object


@dataclass
class ArrayDecl(Noeud):
    name: str
    dims: list
    domain: object


@dataclass
class Constraint(Noeud):
    expr: object


@dataclass
class Forall(Noeud):
    iterators: list      # [(nom, ensemble)]
    body: list


# -- domaines et ensembles d'iteration ------------------------------------

class Domain(Noeud):
    pass


@dataclass
class BoolDomain(Domain):
    pass


@dataclass
class RangeDomain(Domain):
    low: object
    high: object


@dataclass
class NamedDomain(Domain):
    """Domaine donne par un nom : un type enumere. Verifie a l'analyse."""
    expr: object


@dataclass
class RangeSet(Noeud):
    low: object
    high: object


@dataclass
class NamedSet(Noeud):
    expr: object


# -- expressions -----------------------------------------------------------

@dataclass
class Var(Noeud):
    """Un nom employe comme valeur : variable, constante, valeur enumeree..."""
    name: str


@dataclass
class IntLit(Noeud):
    value: int


@dataclass
class Not(Noeud):
    expr: object


@dataclass
class And(Noeud):
    left: object
    right: object


@dataclass
class Or(Noeud):
    left: object
    right: object


@dataclass
class Implies(Noeud):
    left: object
    right: object


@dataclass
class Compare(Noeud):
    op: str              # = != < <= > >=
    left: object
    right: object


@dataclass
class BinOp(Noeud):
    op: str              # + - *
    left: object
    right: object


@dataclass
class Neg(Noeud):
    expr: object


@dataclass
class Index(Noeud):
    base: object
    index: object        # expression, ou Wildcard


@dataclass
class Wildcard(Noeud):
    """Le joker `*` d'une tranche : grid[1][*]."""


@dataclass
class Call(Noeud):
    name: str
    args: list


@dataclass
class ArrayLit(Noeud):
    items: list


@dataclass
class Compr(Noeud):
    """Liste en comprehension : `e for i in S, j in T where c` (extension)."""
    expr: object
    iterators: list
    condition: object | None


# ------------------------------------------------------------
# Construction de l'AST
# ------------------------------------------------------------

@v_args(meta=True)
class ASTBuilder(Transformer):
    """Arbre d'analyse de Lark -> AST, de bas en haut.

    `meta` porte la position de chaque noeud (Lark, propagate_positions=True),
    recopiee dans l'AST pour les messages d'erreur de la question 3.
    """

    @staticmethod
    def _pose(noeud, meta):
        if not getattr(meta, "empty", True):
            noeud.pos = (meta.line, meta.column)
        return noeud

    # instructions

    def program(self, meta, items):
        return self._pose(Program(list(items)), meta)

    # EQ est un terminal nomme : il reste dans `items`, d'ou les indices qui
    # sautent la position 1 (ou 2 pour un tableau constant).

    def const_decl(self, meta, items):
        return self._pose(ConstDecl(str(items[0]), items[2]), meta)

    def const_array_decl(self, meta, items):
        return self._pose(ConstArrayDecl(str(items[0]), items[1], items[3]), meta)

    def enum_decl(self, meta, items):
        return self._pose(EnumDecl(str(items[0]), [str(x) for x in items[2:]]), meta)

    def var_decl(self, meta, items):
        return self._pose(VarDecl(str(items[0]), items[1]), meta)

    def array_decl(self, meta, items):
        return self._pose(ArrayDecl(str(items[0]), items[1], items[2]), meta)

    def dim_list(self, meta, items):
        return list(items)

    def dim(self, meta, items):
        return items[0]

    def constraint_decl(self, meta, items):
        return self._pose(Constraint(items[0]), meta)

    def forall_stmt(self, meta, items):
        iterateurs = [x for x in items if isinstance(x, tuple)]
        corps = [x for x in items if not isinstance(x, tuple)]
        return self._pose(Forall(iterateurs, corps), meta)

    def iterator(self, meta, items):
        return (str(items[0]), items[1])

    def range_set(self, meta, items):
        return self._pose(RangeSet(items[0], items[1]), meta)

    def named_set(self, meta, items):
        return self._pose(NamedSet(items[0]), meta)

    # domaines

    def bool_domain(self, meta, items):
        return self._pose(BoolDomain(), meta)

    def range_domain(self, meta, items):
        return self._pose(RangeDomain(items[0], items[1]), meta)

    def named_domain(self, meta, items):
        return self._pose(NamedDomain(items[0]), meta)

    # expressions

    def var_ref(self, meta, items):
        return self._pose(Var(str(items[0])), meta)

    def int_lit(self, meta, items):
        return self._pose(IntLit(int(items[0])), meta)

    def not_op(self, meta, items):
        return self._pose(Not(items[0]), meta)

    def and_op(self, meta, items):
        return self._pose(And(items[0], items[1]), meta)

    def or_op(self, meta, items):
        return self._pose(Or(items[0], items[1]), meta)

    def implies(self, meta, items):
        return self._pose(Implies(items[0], items[1]), meta)

    def compare(self, meta, items):
        return self._pose(Compare(str(items[1]), items[0], items[2]), meta)

    def compare_eq(self, meta, items):
        return self._pose(Compare("=", items[0], items[2]), meta)

    def binop(self, meta, items):
        return self._pose(BinOp(str(items[1]), items[0], items[2]), meta)

    def mul_op(self, meta, items):
        return self._pose(BinOp("*", items[0], items[1]), meta)

    def neg(self, meta, items):
        return self._pose(Neg(items[-1]), meta)

    def index_op(self, meta, items):
        return self._pose(Index(items[0], items[1]), meta)

    def wildcard(self, meta, items):
        return self._pose(Wildcard(), meta)

    def call(self, meta, items):
        return self._pose(Call(str(items[0]), [x for x in items[1:] if x is not None]), meta)

    def array_lit(self, meta, items):
        return self._pose(ArrayLit([x for x in items if x is not None]), meta)

    def compr(self, meta, items):
        corps = items[0]
        iterateurs = [x for x in items[1:] if isinstance(x, tuple)]
        condition = items[-1] if not isinstance(items[-1], tuple) else None
        return self._pose(Compr(corps, iterateurs, condition), meta)

    def call_compr(self, meta, items):
        return self._pose(Call(str(items[0]), [items[1]]), meta)


parser = Lark(GRAMMAR, parser="lalr", lexer="basic", propagate_positions=True)


def parse(text: str) -> Program:
    """Texte d'un modele -> AST. Leve UnexpectedInput en cas d'erreur de syntaxe."""
    return ASTBuilder().transform(parser.parse(text))


# ------------------------------------------------------------
# Affichage
# ------------------------------------------------------------

def pretty_expr(e) -> str:
    """Expression entierement parenthesee : rend les priorites visibles."""
    if isinstance(e, Var):
        return e.name
    if isinstance(e, IntLit):
        return str(e.value)
    if isinstance(e, Wildcard):
        return "*"
    if isinstance(e, Not):
        return f"(!{pretty_expr(e.expr)})"
    if isinstance(e, Neg):
        return f"(-{pretty_expr(e.expr)})"
    if isinstance(e, And):
        return f"({pretty_expr(e.left)} /\\ {pretty_expr(e.right)})"
    if isinstance(e, Or):
        return f"({pretty_expr(e.left)} \\/ {pretty_expr(e.right)})"
    if isinstance(e, Implies):
        return f"({pretty_expr(e.left)} -> {pretty_expr(e.right)})"
    if isinstance(e, (Compare, BinOp)):
        return f"({pretty_expr(e.left)} {e.op} {pretty_expr(e.right)})"
    if isinstance(e, Index):
        return f"{pretty_expr(e.base)}[{pretty_expr(e.index)}]"
    if isinstance(e, Call):
        return f"{e.name}({', '.join(pretty_expr(a) for a in e.args)})"
    if isinstance(e, ArrayLit):
        return f"[{', '.join(pretty_expr(x) for x in e.items)}]"
    if isinstance(e, Compr):
        iters = ", ".join(f"{n} in {pretty_set(s)}" for n, s in e.iterators)
        ou = f" where {pretty_expr(e.condition)}" if e.condition is not None else ""
        return f"{pretty_expr(e.expr)} for {iters}{ou}"
    raise TypeError(f"expression inattendue : {e!r}")


def pretty_domain(d) -> str:
    if isinstance(d, BoolDomain):
        return "bool"
    if isinstance(d, RangeDomain):
        return f"{pretty_expr(d.low)}..{pretty_expr(d.high)}"
    if isinstance(d, NamedDomain):
        return pretty_expr(d.expr)
    raise TypeError(f"domaine inattendu : {d!r}")


def pretty_set(s) -> str:
    if isinstance(s, RangeSet):
        return f"{pretty_expr(s.low)}..{pretty_expr(s.high)}"
    return pretty_expr(s.expr)


def pretty(noeud, indent: int = 0) -> str:
    """Affichage de l'arbre, une instruction par ligne."""
    marge = "  " * indent
    if isinstance(noeud, Program):
        lignes = ["Program"] if indent == 0 else []
        lignes += [pretty(s, indent + 1) for s in noeud.statements]
        return "\n".join(lignes)
    if isinstance(noeud, ConstDecl):
        return f"{marge}Const {noeud.name} = {pretty_expr(noeud.value)}"
    if isinstance(noeud, ConstArrayDecl):
        dims = "".join(f"[{pretty_expr(d)}]" for d in noeud.dims)
        return f"{marge}ConstArray {noeud.name}{dims} = {pretty_expr(noeud.value)}"
    if isinstance(noeud, EnumDecl):
        return f"{marge}Enum {noeud.name} = {{{', '.join(noeud.values)}}}"
    if isinstance(noeud, VarDecl):
        return f"{marge}Var {noeud.name} : {pretty_domain(noeud.domain)}"
    if isinstance(noeud, ArrayDecl):
        dims = "".join(f"[{pretty_expr(d)}]" for d in noeud.dims)
        return f"{marge}Array {noeud.name}{dims} : {pretty_domain(noeud.domain)}"
    if isinstance(noeud, Constraint):
        return f"{marge}Constraint {pretty_expr(noeud.expr)}"
    if isinstance(noeud, Forall):
        iters = ", ".join(f"{n} in {pretty_set(s)}" for n, s in noeud.iterators)
        lignes = [f"{marge}Forall {iters}"]
        lignes += [pretty(s, indent + 1) for s in noeud.body]
        return "\n".join(lignes)
    raise TypeError(f"instruction inattendue : {noeud!r}")
