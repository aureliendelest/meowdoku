Réponses fausses ou sortie mal formée (ECHEC) : 0 []

## Instances correctement résolues en 60 s

| configuration | fichiers (41) | grilles (12) | total |
|---|---|---|---|
| dpll | 38 | 10 | 48 |
| h4d_seul | 40 | 12 | 52 |
| optimized | 40 | 12 | 52 |

## Temps sur les 48 instances résolues par les trois configurations

| configuration | temps total (s) | médiane (s) | plus lente (s) |
|---|---|---|---|
| dpll | 78.4 | 0.15 | 33.4 |
| h4d_seul | 16.6 | 0.08 | 4.4 |
| optimized | 10.0 | 0.09 | 2.0 |

## Instances non résolues par au moins une configuration (T = timeout, s)

| instance | dpll | h4d_seul | optimized |
|---|---|---|---|
| grille-24-s10 | T | 2.1 | 1.1 |
| grille-24-s11 | T | 3.8 | 5.8 |
| public-03 | T | T | T |
| public-12 | T | 11.4 | 1.9 |
| public-27 | T | 12.2 | 3.5 |

## Instances les plus lentes pour le mode optimized (s)

| instance | dpll | h4d_seul | optimized |
|---|---|---|---|
| grille-24-s11 | T | 3.8 | 5.8 |
| public-27 | T | 12.2 | 3.5 |
| public-11 | 33.4 | 2.0 | 2.0 |
| public-12 | T | 11.4 | 1.9 |
| public-19 | 10.2 | 1.0 | 1.3 |
| grille-24-s10 | T | 2.1 | 1.1 |
| grille-24-s12 | 5.5 | 4.4 | 0.9 |
| grille-20-s10 | 0.3 | 2.8 | 0.5 |

## Surcoût sur les instances triviales (temps réel, s)

| configuration | médiane |
|---|---|
| dpll | 0.080 |
| h4d_seul | 0.070 |
| optimized | 0.070 |

(29 instances sous 0,5 s pour chaque configuration)
