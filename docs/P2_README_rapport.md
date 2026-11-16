Usage des assistants IA

Nous avons travaillé à deux sur l'ensemble du projet, parties I et II, et utilisé un assistant (Claude) tout au long de la partie II. Plutôt que de dresser un inventaire ligne à ligne, il nous paraît plus utile de dire où cet usage nous a semblé pertinent, et où il ne l'était pas.

Là où il l'était. Le compilateur de la partie II est, pour l'essentiel, du travail mécanique à partir d'une spécification précise. L'énoncé dit exactement ce que la grammaire doit accepter, quelles erreurs rejeter, quelles clauses produire pour l'encodage direct. Dans ce cadre, une dizaine de classes d'AST, une grammaire Lark par niveaux de priorité, ou les quatre familles de clauses de Tseitin ne sont pas des problèmes à résoudre : ce sont des transcriptions. L'assistant les produit vite et sans faute d'inattention, là où nous aurions passé des heures sur des erreurs de signe ou d'indice.

Même chose pour les tests. Vérifier que x < y est correctement encodé en énumérant les neuf couples d'un domaine 1..3 est fastidieux à écrire et précieux à avoir. C'est typiquement l'effort qu'on sacrifie faute de temps, et que déléguer permet de ne pas sacrifier.

Là où il ne l'était pas. Les mesures de la question 6 ne pouvaient pas être déléguées, et nous avons refusé qu'elles le soient. Un rapport qui affirme un résultat que personne n'a mesuré est faux, quel qu'en soit l'auteur. Tous les chiffres viennent de nos exécutions, sur notre machine, avec les données brutes dans bench/p2_resultats.csv.

Plus fondamentalement, il y a une chose qu'un assistant ne peut pas faire à notre place : savoir si le code marche chez nous. Les deux bugs les plus intéressants du projet ont été trouvés en exécutant, pas en relisant.

Le premier est un défaut de portabilité de notre partie I : threading.stack_size(512 Mo) lève une exception sous Windows, et notre solveur ne démarrait donc pas hors Linux. Il était là depuis le rendu de la partie I, invisible parce que nous n'avions testé que sur une plateforme.

Le second est une collision de noms, apparue à n = 11 : le générateur de grilles nomme une région K, qui entrait en conflit avec la constante const K écrite par le convertisseur. L'espace de noms unique est une exigence de l'énoncé, et c'est le croisement de nos deux parties qui l'a fait tomber. Aucune relecture ne l'aurait montré ; seule une grille d'onze régions le pouvait.

Ce contre quoi nous avons essayé de nous prémunir. L'énoncé met en garde contre la dette cognitive, et nous pensons que le risque n'est pas celui qu'on imagine. Le code produit par un assistant est rarement faux de façon visible ; il est surtout juste pour des raisons qu'on ne saurait pas énoncer. On accepte une solution parce qu'elle passe les tests, sans pouvoir dire pourquoi elle est correcte.

Notre garde-fou a été de ne considérer comme acquis que ce qu'un test vérifie indépendamment. Le plus important du rendu est à ce titre test_encode.py, qui énumère tous les modèles de la FNC produite pour chaque comparaison et confronte les valeurs obtenues à un calcul fait directement en Python. Il ne fait confiance ni au solveur, ni à l'encodage, ni à leur auteur.

Le second garde-fou est l'exigence que chaque choix de conception soit argumenté et pas seulement appliqué. Les rapports mentionnent systématiquement l'alternative écartée et sa raison : Plaisted–Greenbaum pour la mise en FNC, le compteur de Sinz pour atMostOne, l'encodage par ordre des domaines, une passe de simplification séparée plutôt qu'au vol. Un choix qu'on ne sait pas justifier contre son alternative est un choix qu'on n'a pas fait.