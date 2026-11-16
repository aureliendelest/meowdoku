# Partie II, questions 1 à 5 — Un compilateur vers SAT

## 1. Problème et enjeux

Dans la partie I, la formule d'une grille de Meowdoku était produite par un programme écrit pour ce jeu. Chaque nouveau problème demanderait un nouveau programme. L'objectif est d'écrire, une fois pour toutes, un **compilateur** : il lit la description d'un problème dans un petit langage de contraintes, la traduit en FNC, appelle le solveur de la partie I, puis traduit le modèle trouvé dans les termes du problème de départ.

```
texte --parse--> AST --analyser--> contraintes --encoder--> FNC --résoudre--> valeurs
       (Q2)              (Q3)                      (Q4)       (partie I)      (Q5)
```

La question 1 construit cette chaîne entière pour le seul fragment propositionnel ; les questions 2 à 5 élargissent chacune une étape. Les deux étapes de droite — mise en FNC et écriture DIMACS — ne sont plus réécrites ensuite.

| Difficulté | Pourquoi elle compte |
|---|---|
| Un modèle peut être bien formé et dépourvu de sens | la grammaire accepte `constraint w;` même si `w` n'existe pas |
| La mise en FNC naïve explose | la distribution de `ou` sur `et` peut produire 2ⁿ clauses |
| Tseitin n'est pas une équivalence | elle introduit des variables ; il faut savoir ce qu'elle préserve |
| Le calcul à la compilation doit être paresseux | un accès hors bornes protégé par une condition fausse ne doit pas être une erreur |
| Un solveur SAT ne connaît que des booléens | une variable de domaine 1..9 doit être encodée |
| Une erreur de traduction est invisible | la FNC serait satisfiable sans que le modèle le soit |

## 2. Décisions de conception et implémentation

### 2.1 Grammaire et arbre de syntaxe (Q2, `syntax.py`)

La grammaire du fragment propositionnel est étendue au langage complet, en restant **LALR(1)**. Les priorités et associativités restent encodées par la grammaire elle-même, par niveaux successifs :

```
->  <  or  <  and  <  not  <  comparaison  <  + -  <  *  <  - unaire  <  [ ]  <  atome
```

Conséquences voulues, conformes à l'énoncé : `not x = 2` se lit `not (x = 2)` puisque la comparaison est plus prioritaire ; `a = b = c` est une erreur de syntaxe parce que la règle `comparison` n'est pas récursive ; `a -> b -> c` est récursif à droite, `a or b or c` à gauche.

**Deux conflits et leur résolution.**

*Un domaine ou un ensemble d'itération s'écrit `1..N` ou `Color`.* Après avoir lu une expression, le lexème suivant (`..` ou autre) décide : c'est un conflit décalage/réduction que LALR résout en faveur du décalage, ce qui est le bon choix. On ne distingue donc pas un intervalle d'un type énuméré dans la grammaire, mais à l'analyse. Écrire deux règles séparées aurait donné un conflit réduction/réduction, plus difficile à lever.

*`*` est à la fois la multiplication et le joker des tranches.* Aucune expression ne commence par `*`, donc après `[` ce lexème ne peut être qu'un joker : un seul lexème de lecture avant suffit.

**Deux collisions de terminaux**, découvertes en faisant tourner Lark et corrigées plutôt que contournées. Les caractères `=` et `-` apparaissent chacun à deux endroits de la grammaire (déclaration et comparaison ; somme et moins unaire). Écrits comme chaînes littérales, Lark en crée deux terminaux anonymes concurrents et le lexeur en choisit un, qui n'est pas toujours celui que le parseur attend. Les nommer (`EQ`, `MINUS`, `PLUS`) règle le problème.

L'AST est une dataclass par construction. La position dans le texte est posée comme **attribut ordinaire** et non comme champ de dataclass : l'égalité reste donc structurelle, et les tests peuvent comparer des arbres sans se soucier des positions. C'est ce qui permet les messages du type `line 3, column 31: index 1 of 'a' is 4, out of range 1..3`.

### 2.2 Table des symboles (Q3, `symbols.py`)

Tous les noms partagent **un seul espace de noms**, comme l'exige l'énoncé : la table est unique et chaque entrée porte son genre (`const`, `enum_type`, `enum_value`, `const_array`, `var`, `array`, `index`). Un indice de boucle y est déclaré puis retiré, ce qui fait tomber gratuitement l'erreur `const i = 1; forall i in 1..2 {...}`.

Les valeurs connues sont des **entiers typés** (`Val`) : `Val("int", 3)`, `Val("bool", 1)`, `Val("Color", 0)`. Les valeurs d'un type énuméré sont numérotées 0, 1, … dans l'ordre de déclaration et traitées comme des entiers, mais le type est conservé à côté : c'est lui qui permet de rejeter `color[1] = 3`, qui compare une couleur à un entier.

### 2.3 Analyse, déroulage, simplification (Q3, `analyze.py`)

Deux passes : les déclarations, puis les contraintes. Le résultat est une liste de contraintes sans boucle qui ne portent plus que sur des **cases de variables** (`ir.py` : `Case`, `Cmp`, `Glob`).

**Le choix central : simplifier au vol plutôt qu'en une passe séparée.** La fonction `booleen(e)` renvoie `True`, `False`, ou une expression, et chaque connecteur exploite immédiatement ce que ses opérandes ont donné. C'est ce qui rend le court-circuit naturel : pour `->`, on ne regarde la droite que si la gauche n'est pas fausse. L'exemple de l'énoncé

```
forall i in 1..N { constraint i < N -> grid[i + 1][1] != grid[i][1]; }
```

fonctionne alors sans traitement particulier : pour i = N la condition est fausse, l'implication vaut vrai, et `grid[N + 1][1]` n'est jamais évalué. Une passe de déroulage suivie d'une passe de simplification aurait, elle, évalué l'accès hors bornes avant de pouvoir le jeter.

*Alternative écartée* : produire un arbre déroulé puis le simplifier. Plus facile à inspecter, mais incompatible avec le court-circuit exigé.

Une contrainte qui se simplifie en vrai disparaît ; une contrainte qui se simplifie en faux déclenche un avertissement sur stderr et marque le modèle insatisfiable.

**Extension : les listes en compréhension** (question optionnelle de l'énoncé), motivée par la question 6.4 — voir le rapport de la Q6.

### 2.4 Encodage en FNC (Q4, `encode.py`, `tseitin.py`)

**Encodage direct des domaines.** Une variable x de domaine {v₁…v_k} devient k variables booléennes, plus les clauses « exactement une » (une clause large, et une clause binaire par couple).

Une variable `bool` reste **une seule** variable booléenne : x₁ est la variable et x₀ son opposé. On économise une variable et quatre clauses par case booléenne, et surtout on retrouve exactement l'encodage de la partie I sur Meowdoku, ce qui rend les deux parties comparables.

**Comparaisons.** Plusieurs traductions sont possibles, et l'énoncé demande de les explorer.

| Cas | Écriture retenue | Pourquoi |
|---|---|---|
| `x = v` | x_v | un littéral |
| `x != v` | ¬x_v | un littéral |
| `x <= v` et les autres ordres | la plus courte entre la disjonction des bonnes valeurs et la conjonction des négations des mauvaises | à égalité on prend la seconde : une conjonction de littéraux négatifs donne des **clauses unitaires**, que DPLL propage immédiatement |
| `x != y` | ¬(x_v ∧ y_v) pour chaque v commun | l'écriture de l'énoncé : \|D\| clauses binaires |
| `x = y` | x_v → y_v et y_v → x_v | reste clausal (2\|D\| clauses binaires) ; l'écriture « disjonction des (x_v ∧ y_v) » imposerait Tseitin |
| `x < y` | ¬(x_u ∧ y_v) pour tout couple interdit | O(\|D\|²) clauses, mais toutes binaires, donc très propagatrices |

*Alternative non implémentée* : l'encodage par ordre (variables « x ≤ v »), qui ramènerait `x < y` à O(|D|) clauses au prix de nouvelles variables. C'est la dernière question optionnelle de l'énoncé.

**Contraintes globales.** `atMostOne` utilise l'encodage deux à deux imposé : n(n−1)/2 clauses binaires, aucune variable auxiliaire. `allDifferent` se ramène à « pour chaque valeur v, au plus une des variables vaut v ». Un argument qui est une valeur connue contribue un indicateur constant, absorbé par la simplification.

*Sur le compteur séquentiel de Sinz*, suggéré par l'énoncé : il n'est pas implémenté. L'avertissement de l'énoncé est le point important et nous le prenons au sérieux — ses clauses n'expriment « au plus un » que pour une valeur bien choisie des variables auxiliaires, donc elles ne sont **pas utilisables sous une négation** comme `b -> not atMostOne(...)`. L'encodage deux à deux, lui, est logiquement équivalent et reste correct partout ; c'est ce que vérifie le test `test_globale_sous_une_negation`.

**Mise en FNC.** La méthode naïve (De Morgan puis distribution) donne une formule équivalente mais peut exploser : `(a₁∧b₁) ∨ … ∨ (aₙ∧bₙ)` donne 2ⁿ clauses. Tseitin introduit une variable auxiliaire par nœud et reste linéaire :

| sous-formule | clauses |
|---|---|
| t ↔ (a ∧ b) | (¬t ∨ a), (¬t ∨ b), (t ∨ ¬a ∨ ¬b) |
| t ↔ (a ∨ b) | (¬t ∨ a ∨ b), (t ∨ ¬a), (t ∨ ¬b) |
| t ↔ (a → b) | (¬t ∨ ¬a ∨ b), (t ∨ a), (t ∨ ¬b) |

La FNC n'est **pas équivalente** à la formule : elle parle de variables qui n'existaient pas. Elle est **équisatisfiable**, au sens précis où tout modèle de la FNC restreint aux variables nommées est un modèle de la formule, et où tout modèle de la formule s'étend de façon unique en un modèle de la FNC.

**Les économies** évitent Tseitin quand la contrainte est déjà une clause : `a and b` au sommet vaut deux contraintes séparées ; une disjonction de littéraux est déjà une clause ; `a -> b` donne (¬a ∨ b) et `not (a and b)` donne (¬a ∨ ¬b). Deux fonctions mutuellement récursives, `clause_positive` et `clause_negative`, reconnaissent ces cas. Comme l'encodage produit presque toujours des conjonctions de clauses, **aucune variable auxiliaire n'est créée sur les quatre modèles de l'énoncé**.

*Alternative non retenue* : l'optimisation de polarité (Plaisted–Greenbaum), qui n'émet que `t → e` pour une contrainte affirmée positivement et divise environ par deux le nombre de clauses. Elle devient délicate dès qu'une sous-formule apparaît sous une négation — exactement l'écueil signalé par l'énoncé pour Sinz.

### 2.5 Jonction avec la partie I (Q5, `solve.py`, `dimacs.py`)

`src.cnf.Cnf` étant une dataclass ordinaire, on la construit en mémoire et on appelle `src.optimized.resoudre` directement : **pas de fichier temporaire**. Le `.cnf` reste disponible par `--dimacs`, et sa correspondance nom/numéro est écrite en commentaires (`c var 12 grid[1][2]=5`), pour pouvoir relire un fichier à la main ou le donner à `sat.py`.

Le modèle rendu est vérifié par `verifier_modele` (partie I) avant d'être traduit : comme en partie I question 3, une erreur de compilation ne doit pas pouvoir passer pour une solution. On retrouve ensuite la valeur de chaque variable du modèle de départ — celle des v tels que x_v est vraie — et on l'affiche sous la forme `grid[1][2] = 5` ou `color[3] = Red`.

### 2.6 Ligne de commande

```
python -m partie_2.csp modele.csp                  # FNC DIMACS sur stdout
python -m partie_2.csp modele.csp --dimacs f.cnf   # FNC dans f.cnf
python -m partie_2.csp modele.csp --solve          # résolution
python -m partie_2.csp modele.csp --ast            # arbre de syntaxe
```

Lancée avec `-m` depuis la racine, pour que `src` soit importable. Les erreurs partent sur stderr avec un code de retour 1, jamais sous forme d'exception Python.

## 3. Résultats et analyses

### Validation

`python -m unittest discover -s partie_2/tests -t .` : **88 tests OK**.

| Fichier | Ce qu'il couvre |
|---|---|
| `test_syntax.py` | priorités, associativités, non-chaînage des comparaisons, mots réservés, erreurs de syntaxe, positions, les quatre exemples |
| `test_analyze.py` | espace de noms unique, erreurs de type, valeur inconnue, indices hors bornes, déroulage, intervalle vide, itération sur un énuméré, court-circuit du `and` et du `->`, tranches, compréhensions |
| `test_encode.py` | clauses de domaine, les six comparaisons **par énumération exhaustive**, les quatre contraintes globales, équisatisfiabilité, format DIMACS, les quatre modèles de l'énoncé |
| `test_meowdoku.py` | les deux modélisations, contrôlées par le vérificateur indépendant de la partie I |

Le point important est la méthode de `test_encode.py` : pour chaque comparaison, on énumère **tous** les modèles de la FNC produite, on lit la valeur de chaque case, et on compare l'ensemble obtenu à l'ensemble calculé directement en Python. Cela vérifie d'un coup l'analyse, l'encodage des domaines et la mise en FNC, sans faire confiance au solveur.

### Les quatre modèles de l'énoncé

| Modèle | Contraintes déroulées | Variables | Auxiliaires | Clauses | Compilation | Réponse |
|---|---|---|---|---|---|---|
| `pigeonhole.csp` | 1 | 12 | 0 | 34 | 0,002 s | UNSAT |
| `queens.csp` | 281 | 64 | 0 | 736 | 0,025 s | SAT |
| `coloring.csp` | 17 | 30 | 0 | 87 | 0,004 s | SAT |
| `sudoku.csp` | 57 | 729 | 0 | 11 775 | 0,027 s | SAT |

Les quatre réponses sont celles du tableau 1 de l'énoncé. Les solutions ont été contrôlées par des vérificateurs écrits indépendamment du compilateur : colonnes distinctes et diagonales libres pour les reines, arêtes bicolores pour Petersen, lignes, colonnes et blocs complets pour le Sudoku.

### Analyse

- **Aucune variable auxiliaire n'est créée.** La reconnaissance des clauses directes suffit sur les quatre modèles, parce que l'encodage des comparaisons et des contraintes globales produit des conjonctions de clauses et non des formules arbitraires. Tseitin reste nécessaire pour les modèles qui mêlent `and` sous un `ou`, mais c'est rare dans un modèle de contraintes réaliste.
- **Le déroulage domine le temps de compilation.** `queens.csp` engendre 8⁴ = 4096 instances de boucle dont 280 survivent au filtre `i < j and abs(a-b) = j-i` : plus de 93 % du travail d'analyse est jeté. C'est le prix du filtrage par condition, et c'est ce qui rendra la question 6.2 sensible à la façon d'écrire la règle des régions.
- **Le nombre de clauses est dominé par l'encodage direct.** Pour le Sudoku, 729 variables (81 cases × 9 valeurs) et 81 × (1 + 36) = 2997 clauses rien que pour les domaines, sur 11 775 au total.
- **Le compilateur ne change pas la difficulté du problème.** `pigeonhole.csp` est insatisfiable et le reste ; le principe des tiroirs est connu pour être difficile pour un DPLL sans apprentissage de clauses, mais à cette taille (4 pigeons) il ne pose aucun problème.

### Limites

- L'encodage par ordre des domaines finis et le compteur séquentiel de Sinz ne sont pas implémentés ; l'encodage deux à deux est en O(n²) et deviendrait coûteux sur de très grands domaines.
- L'optimisation de polarité n'est pas implémentée.
- Les positions sont conservées dans l'AST et utilisées dans les messages d'erreur, mais toutes les erreurs ne sont pas également précises : certaines pointent le nœud englobant plutôt que le sous-terme fautif.
- `<->` n'est pas ajouté au langage (question optionnelle).
