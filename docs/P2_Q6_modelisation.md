# Partie II, question 6 — Le modèle compte plus que le solveur

## 1. Problème et enjeux

Le compilateur et le solveur sont désormais fixés. La question compare deux façons d'écrire les **mêmes** règles de Meowdoku, et demande d'expliquer les écarts observés. C'est le renversement annoncé par le titre de la question : à solveur constant, le choix du modèle peut compter davantage que les heuristiques de la partie I.

| Difficulté | Pourquoi elle compte |
|---|---|
| Écrire « au plus un chat par région » | aucune tranche ne désigne les cases d'une région |
| Écrire « au moins un chat par région » | même problème, et la contrainte est redondante : son intérêt est entièrement empirique |
| Comparer honnêtement | les deux modèles n'ont ni le même nombre de variables ni la même difficulté ; il faut mesurer décisions et retours arrière, pas seulement le temps |
| Généraliser à N, M, K libres | « exactement un par ligne » n'est vrai que si N = M = K |

## 2. Décisions de conception et implémentation

### 2.1 Le convertisseur (`partie_2/meowdoku.py`, question 6.1)

```
python -m partie_2.meowdoku grids/figure1.txt --modele cases
python -m partie_2.meowdoku grids/figure1.txt --modele positions -o m.csp
```

Il lit une grille au format de la partie I avec `src.meowdoku.grid.read_grid` — le parseur est réutilisé tel quel, avec ses contrôles de validité — et produit les déclarations (`const N`, `const M`, `const K`, `enum Zone`, `const region[N][M]`) suivies des règles, écrites une fois pour toutes.

### 2.2 « Au plus un chat par région » (question 6.2)

Aucune tranche ne désigne les cases d'une région. Deux écritures sont possibles **dans le langage** :

*Parcourir les couples de cases* et tester l'égalité des régions :

```
forall i in 1..N, j in 1..M, k in i..N, l in 1..M {
  constraint (i < k or j < l) and region[i][j] = region[k][l]
    -> not (cat[i][j] and cat[k][l]);
}
```

La condition `i < k or j < l` évite de compter deux fois chaque couple. Coût : O(N²M²) instances de boucle, soit 160 000 pour une grille 20×20, dont l'immense majorité sera jetée.

*Utiliser une liste en compréhension*, ce qui demande d'**étendre le langage** — c'est l'une des questions optionnelles de l'énoncé, et l'énoncé autorise explicitement l'extension ici :

```
forall z in Zone {
  constraint atMostOne(cat[i][j] for i in 1..N, j in 1..M where region[i][j] = z);
}
```

Coût : O(NMK) instances, et la règle se lit comme son énoncé en français. C'est cette écriture qui est retenue par défaut ; l'autre reste disponible par `--sans-comprehension`, précisément pour pouvoir mesurer l'écart.

**L'extension en elle-même.** La grammaire gagne une règle, `compr: expr "for" iterator ("," iterator)* ["where" expr]`, utilisable en argument d'un appel. `for` et `where` deviennent des mots réservés — c'est le seul coût payé. L'analyse développe la compréhension comme un `forall` : elle lie les indices, évalue la condition (qui doit être connue à la compilation, comme une condition de `forall`), et collecte les termes retenus. Une vingtaine de lignes dans `analyze.py`, parce que la machinerie d'itération existait déjà.

### 2.3 « Au moins un chat par région » (question 6.4)

Avec les compréhensions, la contrainte redondante s'écrit en changeant un seul mot : `atMostOne` devient `exactlyOne`. Sans elles, elle ne s'écrit pas du tout — c'est ce qui a motivé l'extension.

Cette règle est une **conséquence des autres** quand N = M = K : K chats occupent K lignes distinctes et K colonnes distinctes, et chacun est dans une région, donc chaque région en a exactement un. Son intérêt est uniquement de donner au solveur une information qu'il aurait dû déduire. C'est l'objet de la mesure 6.4.

### 2.4 Généralisation (question 6.5)

Quand N, M et K sont libres, « exactement un chat par ligne » devient « au plus un ». La cardinalité est alors entièrement portée par les régions : `exactlyOne` par région, `atMostOne` par ligne et par colonne. L'option `--general` produit cette variante.

### 2.5 Protocole de mesure (`bench/p2_modeles.py`)

```
python -m bench.p2_modeles --tailles 6 8 10 12 --graines 0 1 2 --sortie bench/p2_resultats.csv
```

Pour chaque grille et chaque modèle : taille de la formule, temps de compilation, temps de résolution, et les compteurs de la question 5 de la partie I (décisions, retours arrière, propagations unitaires, littéraux purs), obtenus par `dpll_h(cnf, heuristique, stats=stats)`. Les grilles viennent du générateur de la partie I, donc elles ont une solution par construction. Chaque solution est contrôlée par `src.meowdoku.check.verifier`, qui vérifie les quatre règles directement sur la grille sans rien savoir du compilateur.

## 3. Résultats et analyses

### Validation

`python -m unittest partie_2.tests.test_meowdoku` : **9 tests OK**.

| Vérification | Résultat |
|---|---|
| Les cinq variantes résolvent la figure 1 | solution valide, et c'est celle de la figure 2 de l'énoncé dans les cinq cas |
| Grilles générées, n ∈ {4, 5, 6} × 2 graines, cinq variantes | solution valide à chaque fois selon le vérificateur indépendant |
| Grille 2×2 sans solution | UNSAT |
| Accord des modèles sur le statut | identique sur toutes les grilles testées |
| Accord avec une recherche exhaustive (question 6.5) | identique sur cinq petites grilles, dont deux non carrées |

Taille des formules sur la grille de la figure 1 (6×6, 6 régions) :

| Modèle | Variables | Clauses |
|---|---|---|
| `positions` | 72 | 2 052 |
| `cases` | 36 | 342 |
| `cases` + redondant | 36 | 348 |
| `cases` sans compréhension | 36 | 342 |
| `cases` général | 36 | 408 |

Le dernier chiffre est un contrôle croisé utile : 408 clauses, c'est **exactement** ce que produisait l'encodage écrit à la main en partie I pour cette grille. Les deux chemins, programme dédié et compilateur, aboutissent à la même formule.

### 3.1 Comparaison des deux modèles (question 6.3)

`python -m bench.p2_modeles --tailles 6 8 10 12 --graines 0 1 2`, moyennes sur trois graines, données brutes dans `bench/p2_resultats.csv`.

| n | Modèle | Variables | Clauses | Compilation (s) | Résolution (s) | Décisions | Retours arrière |
|---|---|---|---|---|---|---|---|
| 6 | positions | 72 | 2 052 | 0,235 | 0,028 | 38 | 1 |
| 6 | cases | 36 | 386 | 0,018 | 0,019 | 27 | 14 |
| 8 | positions | 128 | 6 848 | 0,696 | 0,127 | 89 | 0 |
| 8 | cases | 64 | 907 | 0,026 | 0,019 | 45 | 1 |
| 10 | positions | 200 | 17 300 | 1,840 | 0,483 | 153 | 0 |
| 10 | cases | 100 | 1 765 | 0,036 | 0,061 | 91 | 21 |
| 12 | positions | 288 | 36 720 | 3,942 | 1,336 | 233 | 0 |
| 12 | cases | 144 | 3 020 | 0,055 | 0,265 | 364 | 260 |

**L'écart vient de la taille de la formule, pas de la difficulté de la recherche.** C'est le résultat le plus net, et il est contre-intuitif. À n = 12, le modèle `positions` fait **233 décisions et zéro retour arrière** là où `cases` en fait 364 avec 260 retours arrière : la recherche est *plus facile* avec `positions`. Et pourtant il est cinq fois plus lent. L'explication tient dans la colonne des clauses : 36 720 contre 3 020, soit douze fois plus. Le solveur de la partie I recopie la formule à chaque affectation (`simplifier` reconstruit la liste des clauses), donc chaque décision coûte proportionnellement à la taille de la formule. Un arbre de recherche plus petit parcouru sur une formule douze fois plus grosse reste plus lent.

**Pourquoi `positions` grossit plus vite.** Les deux règles sont de complexité différente :

| Règle | `positions` | `cases` |
|---|---|---|
| Un chat par ligne et par colonne | `allDifferent` sur 2n variables de domaine n : 2n·C(n,2) clauses binaires | `exactlyOne` sur chaque tranche : 2n·(1 + C(n,2)) clauses |
| Chat dans sa région | boucle sur (z, i, j) : K·N·M instances | implicite, il n'y a pas de variable de position |
| Pas de voisins | boucle sur (z₁, z₂, i, j, k, l) : **O(n⁴)** instances après filtrage | boucle sur (i, j, l) : **O(n²)** instances |

Les chiffres le confirment : de n = 6 à n = 12, les clauses de `positions` sont multipliées par 17,9 (soit ≈ n⁴) et celles de `cases` par 8,8 (soit ≈ n³). L'écart se creuse donc avec la taille, et le temps de compilation suit la même loi — 3,9 s contre 0,055 s à n = 12, un rapport de 70.

**Un même problème, deux espaces de recherche.** Le modèle `positions` décrit une solution par 2n nombres ; `cases` par n² booléens. Le premier encode davantage de structure dans les variables elles-mêmes (un chat par région est garanti par construction : il y a une variable `row[z]` par région), ce qui explique l'absence de retours arrière. Mais encoder cette structure dans des variables de domaine n coûte n booléens chacune, plus les clauses « exactement une valeur ».

### 3.2 Contraintes redondantes (question 6.4)

| n | | Clauses | Résolution (s) | Décisions | Retours arrière |
|---|---|---|---|---|---|
| 6 | sans | 386 | 0,019 | 27 | 14 |
| 6 | avec | 392 | **0,004** | **9** | **0** |
| 8 | sans | 907 | 0,019 | 45 | 1 |
| 8 | avec | 915 | 0,017 | 44 | 1 |
| 10 | sans | 1 765 | 0,061 | 91 | 21 |
| 10 | avec | 1 775 | 0,046 | **68** | **2** |
| 12 | sans | 3 020 | 0,265 | 364 | 260 |
| 12 | avec | 3 032 | **0,173** | **185** | **85** |

**La contrainte fonctionne, et son effet suit les retours arrière.** Elle n'enlève aucune solution : elle est logiquement impliquée par les autres quand N = M = K. Son seul rôle est de permettre au solveur de **propager plus tôt**. La clause large « au moins un chat dans la région z » devient unitaire dès que toutes les cases de z sauf une sont fausses, et force alors immédiatement la dernière ; sans elle, le solveur atteint la même conclusion par branchement et retour arrière.

Les mesures le montrent par graine, mieux encore que par moyenne :

| Grille | Sans | Avec |
|---|---|---|
| n = 6, graine 1 | 28 décisions, 23 retours arrière | **0 et 0** |
| n = 6, graine 2 | 31 et 20 | 2 et 0 |
| n = 10, graine 2 | 123 et 61 | 55 et 0 |
| n = 12, graine 2 | 608 et 509 | 229 et 142 |
| n = 10, graine 0 | 76 et 0 | 78 et 4 |
| n = 12, graine 0 | 118 et 0 | 116 et 0 |

Là où le solveur ne faisait **aucun** retour arrière, la contrainte n'apporte rien et peut même coûter quelques décisions (n = 10 graine 0). Là où il en faisait beaucoup, elle les divise par deux ou les supprime. Pour la grille n = 6 graine 1, elle rend le problème entièrement déductible : zéro décision, la propagation unitaire suffit.

**Le coût est négligeable** : une clause large par région, soit +12 clauses sur 3 020 à n = 12 (0,4 %). Le compromis est donc très favorable, et **il s'améliore avec la taille**, puisque le nombre de retours arrière du modèle sans contrainte redondante croît vite (0 à n = 8, 260 à n = 12).

**Réserve.** La variance entre graines est du même ordre que l'effet mesuré (à n = 12 : 118, 367 et 608 décisions pour la même taille). Trois graines par taille ne suffisent pas pour affirmer un facteur précis ; elles suffisent à établir le sens de l'effet et sa condition de déclenchement.

### 3.3 Coût de l'écriture sans compréhension

| n | Avec compréhension (s) | Sans (s) | Rapport | Clauses |
|---|---|---|---|---|
| 6 | 0,018 | 0,036 | 2,0× | identiques |
| 8 | 0,026 | 0,087 | 3,3× | identiques |
| 10 | 0,036 | 0,127 | 3,5× | identiques |
| 12 | 0,055 | 0,218 | 4,0× | identiques |

**La formule produite est rigoureusement la même** — même nombre de variables, même nombre de clauses, et des temps de résolution indiscernables. Seule la compilation diffère, dans un rapport qui croît avec n, conformément au O(N²M²) contre O(NMK) attendu. C'est un résultat sur le compilateur, pas sur le solveur, et c'est ce qui justifie l'extension du langage : à n = 12, le parcours de couples examine 12⁴ ≈ 20 000 instances dont presque toutes sont jetées par le test d'égalité des régions, là où la compréhension en examine 12² × 12 = 1 728.

### 3.4 Conclusion (question 6.6)

**Dans ces expériences, le choix du modèle pèse plus lourd que le solveur.** Les deux effets se mesurent sur la même échelle :

| Levier | Gain observé |
|---|---|
| Heuristiques du solveur (partie I, Q5–Q6) | 48 → 52 instances résolues, temps total divisé par 4,7 ; portefeuille parallèle : −40 % de plus |
| Choix du modèle (`positions` → `cases`, n = 12) | temps divisé par **5**, formule divisée par **12** |
| Contrainte redondante (n = 12) | temps divisé par **1,5**, retours arrière par **3** |

Le gain du modèle est au moins du même ordre que celui des heuristiques, et **il croît avec la taille du problème** alors que le gain des heuristiques est à peu près constant. Pour une grille de taille 20, l'écart `positions`/`cases` dépasserait largement tout ce qu'une heuristique peut récupérer.

**Mais les deux effets ne sont pas de même nature**, et la conclusion doit le dire. Une heuristique change l'ordre d'exploration **à formule donnée** : elle agit sur le nombre de décisions. Un modèle change la formule elle-même, donc à la fois l'espace de recherche et le coût de chaque pas. C'est exactement ce que montre le cas `positions` : il réduit le nombre de décisions, ce qu'une bonne heuristique ferait, mais il augmente tellement la taille de la formule que le bilan est négatif. Les deux leviers ne sont donc pas substituables — ils ne jouent pas sur la même quantité.

**Et ils se composent.** La contrainte redondante est un cas intéressant : elle n'est ni une heuristique ni un changement de modèle, mais une information ajoutée au modèle pour aider la propagation du solveur. C'est le point de rencontre des deux parties du projet.

**Portée de la conclusion.** Elle vaut pour des grilles de 6 à 12, carrées, engendrées aléatoirement par le générateur de la partie I, avec l'heuristique H4d. Les grilles aléatoires sont probablement plus faciles que de vrais puzzles, et nous n'avons pas testé au-delà de n = 12 : le modèle `positions` y demande déjà 4 s de compilation, ce qui rendrait la comparaison pénible sans un compilateur plus rapide.

### Limites

- Le générateur de la partie I produit des grilles aléatoires, probablement plus faciles que de vrais puzzles ; les conclusions ne se généralisent pas sans mesure.
- Le modèle `positions` suppose N = M = K ; la comparaison 6.3 ne porte donc que sur des grilles carrées.
- Une seule exécution par point, trois graines par taille, tailles 6 à 12. Les écarts de quelques centièmes de seconde sont du bruit, et la variance entre graines est du même ordre que l'effet de la contrainte redondante.
- Les mesures ont été faites sous Windows, où `multiprocessing` utilise `spawn` : les temps absolus ne sont pas comparables à ceux de la partie I, mesurés sous Linux. Seuls les rapports entre modèles, mesurés dans les mêmes conditions, sont exploitables.
- Le temps de compilation du modèle `positions` (4 s à n = 12) devient le facteur limitant avant le temps de résolution. Un déroulage plus malin des boucles à six indices serait nécessaire pour aller plus loin.
