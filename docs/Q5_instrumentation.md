# Question 5 — Instrumentation et comparaison des heuristiques

## 1. Problème et enjeux

La Q4 fournit 16 variantes de DPLL_H (H0, H1, H2s..H7d, MJs, MJd). La Q5 demande de **mesurer** ce qu'elles valent, pas de le supposer. Trois questions d'analyse sont posées par l'énoncé :

1. Les résultats observés sont-ils en adéquation ou en désaccord avec nos attentes ?
2. En quelle mesure une heuristique améliore-t-elle l'algorithme 2 (DPLL à choix aléatoire) ?
3. En quelle mesure le recalcul dynamique améliore-t-il la qualité d'une heuristique, au regard de son coût ?

Exemple minuscule : deux heuristiques résolvent la même instance en 100 décisions. L'une y met 1 ms, l'autre 50 ms parce qu'elle recalcule ses scores à chaque décision. Le nombre de décisions seul les juge égales ; le temps seul ne dit pas *pourquoi*. Il faut les deux, et il faut aussi un coût indépendant de la machine.

Difficultés :

| Difficulté | Pourquoi ça compte |
|---|---|
| Mesurer sans fausser | un compteur ou un chronomètre trop coûteux change le temps qu'on veut mesurer |
| Timeouts | une instance non résolue n'a pas de nombre de décisions ; la moyenner avec des résolues serait trompeur |
| SAT et UNSAT ne se comportent pas pareil | sur UNSAT tout l'arbre est exploré, la polarité du choix ne compte plus ; sur SAT, une bonne polarité peut éviter presque tout |
| Hasard de H0 | un seul tirage ne représente pas H0 : plusieurs graines |
| Temps dépendant de la machine | le temps CPU change d'un ordinateur à l'autre ; un compteur d'opérations non |

## 2. Décisions de conception et implémentation

### Compteurs (`src/dpll.py`, classe `Stats`)

Compteurs demandés par l'énoncé, plus deux critères de notre choix (critère 7 de l'énoncé) :

| Compteur | Définition | Origine |
|---|---|---|
| `decisions` | appels à l'heuristique (ligne 17) | énoncé, critère 1 |
| `backtracks` | exécutions de la branche *else* (ligne 21) | énoncé, critère 2 |
| `unitaires` | propagations unitaires (ligne 5) | énoncé, critère 3 |
| `purs` | littéraux purs (ligne 11) | énoncé, critère 4 |
| temps CPU | `time.process_time` autour de `dpll_h` | énoncé, critère 5 |
| `t_heuristique` | temps CPU passé dans `choisir` (`process_time`, même horloge que le temps total) ; ratio = `t_heuristique` / temps CPU | énoncé, critère 6 |
| `conflits` | clauses vides rencontrées | complément |
| **propagations par décision** | `unitaires / decisions` | **notre critère 1** |
| **clauses visitées** | `visites` + `visites_heuristique` | **notre critère 2** |

Ce sont de simples incréments entiers ; aucun profilage n'est actif pendant les mesures.

### Pourquoi ces deux critères

**Propagations par décision.** Elle mesure la *qualité* d'un choix : une bonne décision déclenche beaucoup de propagation unitaire derrière elle, donc élague vite. Elle sépare « mauvais choix » (peu de propagation par décision) de « choix coûteux à calculer » (ratio de temps de l'énoncé). Elle ne coûte rien : c'est le rapport de deux compteurs.

**Clauses visitées.** Elle mesure un *coût indépendant de la machine*. Le temps CPU dépend de l'ordinateur et de sa charge ; le nombre de clauses parcourues est reproductible exactement. Il permet de répondre à la question 3 (coût contre pertinence) sans que le résultat dépende du matériel.
- `visites` : clauses parcourues par la propagation et `simplifier`. Compté par `len(formule)` à l'entrée de chaque parcours ; un conflit détecté en cours de parcours compte donc la formule entière (légère surestimation).
- `visites_heuristique` : `len(formule)` à chaque décision, soit **au moins un parcours**. MOMS et JW en font deux (taille minimale ou maximale, puis comptage) : leur coût est **sous-estimé** pour H4 à H7. Cette approximation est assumée et sera rappelée avec les résultats.

**Profondeur maximale : écartée.** Elle décrit la forme de l'arbre, pas la qualité du choix, et sera presque toujours proche du nombre de variables décidées : peu discriminante.

### Protocole de mesure (`bench/q5_heuristiques.py`)

| Choix | Justification |
|---|---|
| 16 variantes ; H0 avec 3 graines (0, 1, 2) | H0 est aléatoire : un tirage unique n'a pas de sens |
| Instances : 30 `public-*` + 12 grilles Meowdoku (n = 8, 12, 16, 20 ; 3 graines chacune) | formes variées ; les grilles relient la mesure au jeu (Q1) |
| Un processus par exécution, timeout de 10 s (temps réel) | un timeout ne produit jamais de réponse ; le processus est tué |
| 6 exécutions en parallèle | durée totale raisonnable |
| Temps CPU = `process_time` | ne compte pas l'attente quand la machine est partagée |
| Chaque réponse contrôlée : statut = `expected.json` (ou SAT pour les grilles) **et** modèle vérifié sur les clauses d'origine | la correction prime ; colonne `resultat` = OK / ECHEC / TIMEOUT |

Sortie : `bench/q5_resultats.csv`, une ligne par (instance, heuristique, graine).

### Règles d'agrégation (`bench/q5_analyse.py`)

- SAT et UNSAT sont **séparés**, ainsi que les grilles Meowdoku.
- Les moyennes ne portent que sur le **jeu commun** : les instances résolues par toutes les heuristiques comparées. Les timeouts sont comptés à part (tableau « instances résolues »), jamais moyennés avec des temps.
- **Moyenne géométrique** : les valeurs s'étalent sur plusieurs ordres de grandeur, la moyenne arithmétique serait dominée par une seule instance.
- H0 : moyenne géométrique de ses 3 graines, et résolue seulement si les 3 le sont.

### Limites connues de la méthode

- Le timeout de 10 s est bas devant celui de la compétition (60 s) : des instances « difficiles » sont comptées en timeout.
- Plusieurs exécutions tournent en parallèle sur une machine à plusieurs cœurs : le temps CPU est peu sensible à la charge, mais pas totalement (cache, mémoire partagée). Les écarts de quelques pour cent ne sont pas significatifs ; les compteurs, eux, sont exacts.
- Une seule mesure de temps par (instance, heuristique) hors H0 : les heuristiques non aléatoires sont déterministes en compteurs, seul le temps varie.
- **Erreur corrigée en cours de route.** Une première exécution mesurait `t_heuristique` avec `perf_counter` (temps réel) et le total avec `process_time` (temps CPU) : sous charge parallèle, le ratio dépassait 100 % (112 % pour MJd sur les grilles). Les deux utilisent maintenant `process_time`, et tout le benchmark a été relancé. Les chiffres ci-dessous viennent de cette seconde exécution.

## 3. Résultats et analyses

Reproduction :

```
python -m bench.q5_heuristiques 10 6 > bench/q5_resultats.csv   # ~20 min
python -m bench.q5_analyse > bench/q5_synthese.md                # tableaux complets
```

### Correction

756 exécutions (42 instances × 16 variantes, H0 en 3 graines) : **0 échec**. Toute réponse a le statut attendu et, si SAT, un modèle qui satisfait toutes les clauses. 116 exécutions (15 %) atteignent le timeout de 10 s ; elles ne produisent aucune réponse.

### Instances résolues en moins de 10 s

| heuristique | public SAT (19) | public UNSAT (11) | Meowdoku (12) | total (42) |
|---|---|---|---|---|
| H0 (3 graines, toutes résolues) | 14 | 9 | 9 | 32 |
| H1 | 16 | 10 | 10 | 36 |
| H2s / H2d | 15 / 15 | 10 / 10 | 8 / 12 | 33 / 37 |
| H3s / H3d | 16 / 13 | 10 / 10 | 8 / 12 | 34 / 35 |
| H4s / H4d | 17 / 17 | 10 / 10 | 8 / 12 | 35 / **39** |
| H5s / H5d | 16 / 14 | 10 / 10 | 8 / 12 | 34 / 36 |
| H6s / H6d | 17 / 15 | 10 / 10 | 8 / 12 | 35 / 37 |
| H7s / H7d | 15 / 13 | 10 / 10 | 8 / 12 | 33 / 35 |
| MJs / MJd | 17 / 17 | 10 / 10 | 8 / 12 | 35 / **39** |

`public-03` et `public-27` ne sont résolues par aucune variante (16 sur 16 en timeout) ; `public-12` l'est seulement par deux.
**Précaution :** une première exécution a donné des totaux décalés de ±1 pour plusieurs variantes (instances proches de 10 s). Un écart d'**une** instance entre deux heuristiques n'est donc pas significatif.

### Instances SAT publiques (jeu commun : 11 instances sur 19)

| heuristique | décisions | backtracks | propagations / décision | t CPU (ms) | part du temps en heuristique |
|---|---|---|---|---|---|
| H0 | 47.1 | 2.2 | 17.8 | 48.9 | 7.0 % |
| H1 | 63.6 | 0.7 | 13.1 | 53.8 | 11.9 % |
| H2s / H2d | 16.8 / 17.8 | 1.2 / 0.2 | 21.0 / 16.3 | 20.6 / 21.2 | 5.7 / 10.6 % |
| H3s / H3d | 16.7 / 19.0 | 0.0 / 0.1 | 16.5 / 11.6 | 18.1 / 16.8 | 6.4 / 12.2 % |
| H4s / H4d | 16.2 / 13.2 | 0.1 / 0.0 | 15.2 / 13.6 | 16.1 / 13.3 | 6.6 / 9.7 % |
| H5s / H5d | 15.1 / 17.8 | 0.1 / 0.0 | 12.3 / 8.8 | 12.6 / 13.1 | 6.6 / 10.8 % |
| H6s / H6d | 13.9 / 14.0 | 0.0 / 0.0 | 16.2 / 13.8 | 15.3 / 15.6 | 6.1 / 15.2 % |
| H7s / H7d | 17.2 / 15.9 | 0.1 / 0.0 | 12.9 / 11.4 | 15.3 / 14.9 | 6.4 / 16.5 % |
| MJs / MJd | 11.8 / 12.6 | 0.0 / 0.0 | 16.3 / 13.0 | 12.7 / 14.0 | 5.6 / 23.3 % |

### Instances UNSAT publiques (jeu commun : 9 instances sur 11)

Sur UNSAT, `backtracks = décisions` : tout l'arbre est parcouru, donc la branche *else* suit chaque décision.

| heuristique | décisions | propagations / décision | t CPU (ms) | part du temps en heuristique |
|---|---|---|---|---|
| H0 | 552.4 | 13.4 | 352.8 | 7.2 % |
| H1 | 255.9 | 13.7 | 184.1 | 9.9 % |
| H2s / H2d | 120.4 / 79.5 | 14.9 / 14.7 | 89.8 / 66.4 | 7.0 / 13.7 % |
| H3s / H3d | 182.0 / 143.6 | 13.7 / 14.0 | 122.7 / 110.0 | 7.2 / 12.1 % |
| H4s / H4d | 46.5 / 29.5 | 15.2 / 16.3 | 35.9 / 26.8 | 7.7 / 11.0 % |
| H5s / H5d | 55.4 / 36.8 | 15.7 / 15.8 | 45.3 / 31.5 | 7.7 / 9.0 % |
| H6s / H6d | 46.1 / 30.5 | 16.3 / 17.4 | 38.6 / 32.2 | 7.3 / 16.7 % |
| H7s / H7d | 62.0 / 43.5 | 15.0 / 16.1 | 50.7 / 41.2 | 7.4 / 15.4 % |
| MJs / MJd | 46.3 / 30.9 | 15.8 / 16.2 | 38.6 / 32.9 | 7.3 / 24.6 % |

### Grilles Meowdoku (jeu commun : 7 grilles sur 12, toutes de taille ≤ 16)

| heuristique | décisions | backtracks | propagations / décision | t CPU (ms) | part du temps en heuristique |
|---|---|---|---|---|---|
| H0 | 38.7 | 6.3 | 9.2 | 43.4 | 7.0 % |
| H1 | 58.4 | 34.8 | 10.0 | 69.6 | 9.0 % |
| H2s = H3s = H4s = H5s = H7s | 151.2 | 96.9 | 7.8 | ≈ 121 | 10 % |
| H6s = MJs | 158.7 | 105.4 | 7.9 | ≈ 122 | 10 % |
| H2d = H3d = H5d = H7d | 154.8 | 0.1 | 1.7 | 67 à 79 | 44 à 52 % |
| H4d | 127.5 | 0.0 | 1.7 | 69.3 | 51.7 % |
| H6d = MJd | 108.4 | 0.0 | 0.7 | 68.2 / 104.7 | 60.5 / 73.9 % |

Temps CPU (ms) sur les grilles, T = timeout (pour H0, T si au moins une des 3 graines échoue) :

| grille | H0 | H1 | H2s | H2d | H4d | H6d | MJd |
|---|---|---|---|---|---|---|---|
| 12, graine 1 | 176 | 2974 | 259 | 224 | 207 | 113 | 183 |
| 16, graine 0 | T | T | 310 | 374 | 426 | 493 | 778 |
| 16, graine 2 | 240 | 477 | T | 688 | 653 | 5100 | 6431 |
| 20, graine 0 | 658 | 6458 | T | 1257 | 1410 | 2515 | 3657 |
| 20, graine 1 | T | T | T | 3155 | 2484 | 1773 | 2772 |
| 20, graine 2 | T | 793 | T | 1263 | 1394 | 1591 | 2520 |

(Les 12 grilles sont dans `bench/q5_synthese.md`.)

### Statique et dynamique, rapport d/s (< 1 : le dynamique gagne)

| paire | SAT : décisions | SAT : t CPU | UNSAT : décisions | UNSAT : t CPU | Meowdoku : visites | Meowdoku : t CPU |
|---|---|---|---|---|---|---|
| H2 | 1.06 | 1.03 | 0.66 | 0.74 | 0.33 | 0.55 |
| H3 | 1.14 | 0.93 | 0.79 | 0.90 | 0.33 | 0.57 |
| H4 | 0.82 | 0.82 | 0.63 | 0.75 | 0.31 | 0.57 |
| H5 | 1.18 | 1.04 | 0.66 | 0.70 | 0.33 | 0.59 |
| H6 | 1.00 | 1.02 | 0.66 | 0.84 | 0.26 | 0.57 |
| H7 | 0.93 | 0.97 | 0.70 | 0.81 | 0.33 | 0.65 |
| MJ | 1.07 | 1.10 | 0.67 | 0.85 | 0.26 | 0.85 |

### Question 1 — Les résultats correspondent-ils à nos attentes ?

**Conformes :**
- Sur UNSAT, l'ordre est celui attendu : H0 est la pire (552 décisions), les heuristiques fondées sur les clauses courtes (MOMS, JW) sont les meilleures (30 à 46 décisions).
- Les heuristiques *variable* battent leur version *littéral* sur UNSAT (H2d 79.5 contre H3d 143.6 ; H4d 29.5 contre H5d 36.8 ; H6d 30.5 contre H7d 43.5). Sur UNSAT, tout l'arbre est exploré, donc la polarité ne compte pas ; seul compte le choix de la variable.
- Le départage par JW n'améliore pas MOMS (hypothèse de la Q4, **non confirmée**) : MJd 30.9 contre H4d 29.5 décisions sur UNSAT, et 17 résolues chacune sur les SAT. MJd coûte plus cher (24.6 % du temps en heuristique contre 11.0 %). Seul MJs semble un peu meilleur que H4s sur SAT (11.8 contre 16.2 décisions), sur 11 instances : trop peu pour conclure.
- Hypothèse « H4s et H5s moins bonnes que leurs versions dynamiques » : **vraie sur UNSAT** (46.5 contre 29.5 ; 55.4 contre 36.8) et pour H4 sur les grilles, **fausse pour H5 sur SAT** (15.1 contre 17.8).
- Le blocage de H2s et H2d sur `public-21`, observé ponctuellement en Q4, est **reproduit** : ce sont les deux seules variantes en timeout, alors que H0 la résout en 0,16 s.

**Surprises :**
1. **Sur les grilles Meowdoku, H0 et H1 battent les heuristiques à base de comptage sur le jeu commun** (H0 : 38.7 décisions et 43 ms ; les autres : 108 à 159 décisions, 67 à 122 ms). Notre explication, vérifiée sur une grille : toutes les clauses binaires sont de la forme `(¬a ∨ ¬b)`, donc les littéraux positifs n'apparaissent que dans les clauses « un chat par région ». Toutes les heuristiques de comptage choisissent donc `¬x` (« pas de chat ici ») sur la même case : c'est pourquoi les compteurs de H2s, H3s, H4s, H5s, H7s sont identiques. Poser « pas de chat » propage peu (0,7 à 1,7 propagation par décision pour les dynamiques, contre 9 à 10 pour H0 et H1 qui posent « chat » une fois sur deux ou toujours). Cette lecture est plausible mais nous n'avons pas fait l'expérience qui la prouverait (une variante qui force la polarité positive).
2. **Mais H0 et H1 ne passent pas à l'échelle** : H0 résout 9 grilles sur 12 et H1 10, contre 12 pour toutes les heuristiques dynamiques (statiques : 8). Le jeu commun est biaisé vers les petites grilles. Pour les dynamiques, le nombre de retours arrière reste proche de 0 (0,0 à 0,1) : l'heuristique ne se trompe presque jamais, au prix de plus de décisions.
3. **Sur SAT, les heuristiques littéral dynamiques résolvent moins** (H3d 13, H7d 13, H5d 14, contre 17 pour H4d, MJd). Une mauvaise polarité n'est corrigée que bien plus tard : DPLL n'a ni redémarrage ni apprentissage, donc une erreur au sommet de l'arbre est payée par un sous-arbre entier. Cette explication est une hypothèse.
4. **Sur SAT, H0 varie beaucoup d'une graine à l'autre** (`public-05` : 269, 490, 552 décisions ; `public-01` : 3, 3, 4), ce qui justifie les 3 graines.

### Question 2 — Apport d'une heuristique face à l'algorithme 2

L'algorithme 2 est H0. Sur le jeu commun :

| Instances | H0 | meilleure heuristique | gain |
|---|---|---|---|
| UNSAT publiques | 552 décisions, 353 ms | H4d : 29.5 décisions, 26.8 ms | ×19 en décisions, ×13 en temps |
| SAT publiques | 47 décisions, 49 ms | MJs : 11.8 décisions, 12.7 ms | ×4 en décisions, ×4 en temps |
| Meowdoku (petites grilles) | 38.7 décisions, 43 ms | aucune ne fait mieux | gain nul, voire perte (×1,5 à ×2,8 en temps) |
| Résolues au total (sur 42) | 32 | 39 (H4d, MJd) | +7 |

Une bonne heuristique améliore donc fortement DPLL sur les instances publiques, surtout UNSAT, où le choix de variable décide de la taille de l'arbre. Sur les grilles, la réponse dépend de la taille : plus lente sur les petites, indispensable sur les grandes (les 12 grilles ne sont résolues que par les dynamiques). Toute heuristique n'est pas bonne : H2 et H3 résolvent moins de SAT que MOMS et JW, et H1 (la plus simple) résout 36 instances, soit plus que H0 et que les statiques de comptage sur les grilles.

### Question 3 — Le recalcul dynamique vaut-il son coût ?

Le coût existe : la part du temps passée dans l'heuristique passe de **5,6 à 7,7 %** (statique) à **9 à 25 %** (dynamique) sur les instances publiques, et à **44 à 74 %** sur les grilles. Ce qu'il rapporte dépend du type d'instance :

| Cas | Effet du recalcul dynamique | Verdict |
|---|---|---|
| UNSAT publiques | 21 à 37 % de décisions en moins, temps CPU de 0,70 à 0,90 du statique pour les 7 paires | **gagnant**, partout |
| SAT publiques | décisions entre 0,82 et 1,18, temps entre 0,82 et 1,10 | **neutre** : pas de différence au-delà du bruit, sauf H4 (0,82 / 0,82) |
| Meowdoku | visites de clauses divisées par 3 à 4 (0,26 à 0,33), temps de 0,55 à 0,85 du statique, 12 grilles résolues contre 8 | **gagnant**, malgré un coût de heuristique de 44 à 74 % du temps |

Sur les grilles, le gain ne vient pas de choix plus pertinents (le nombre de décisions reste ≈ 1,0 du statique pour H2, H3, H5, H7), mais de l'**absence de retours arrière** : 97 pour le statique contre 0,1 pour le dynamique. Le classement initial devient faux dès qu'on a affecté quelques cases ; le recalcul le corrige.

Le coût peut être réduit. Le recalcul parcourt toute la formule à chaque décision, alors qu'une décision n'en modifie qu'une petite partie (0,7 à 1,7 propagation seulement sur les grilles). Un comptage **incrémental** (mise à jour des scores uniquement pour les clauses touchées) devrait faire disparaître l'essentiel des 44 à 74 %. C'est la piste principale pour la Q6.

### Limites

- Timeout de 10 s (60 s en compétition) ; les écarts d'une instance résolue sont dans le bruit.
- Jeux communs petits (11, 9 et 7 instances) et biaisés vers les instances faciles : ils ne représentent pas les instances difficiles, où l'on ne dispose que du nombre d'instances résolues.
- Les visites de clauses de l'heuristique sont sous-estimées pour H4 à H7 (voir section 2).
- Une seule machine ; les temps absolus ne se transposent pas, les rapports et les compteurs oui.
- Les explications des surprises 1 et 3 sont des hypothèses, pas des résultats testés.
