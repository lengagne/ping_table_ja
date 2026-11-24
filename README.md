# Double KO 32

Génère le placement de 32 joueurs dans un tableau double élimination à partir
d'un classement de poules stocké dans un fichier Excel.

## Installation automatique

Sous Linux :

```bash
chmod +x install_linux.sh
./install_linux.sh
```

Sous Windows, double-cliquez sur `install_windows.bat` ou lancez :

```bat
install_windows.bat
```

Les deux scripts créent un environnement virtuel `.venv` et y installent
automatiquement le projet ainsi que ses dépendances.

## Installation manuelle

```bash
python -m venv .venv
source .venv/bin/activate       # Windows : .venv\\Scripts\\activate
pip install -e .
```

## Utilisation

### Interface graphique

Après l'installation, lancez :

```bash
./lancer_interface.sh       # Linux
```

Sous Windows, double-cliquez sur `lancer_interface.bat`.

Pour ouvrir directement l'éditeur de configuration sans l'écran de calcul :

```bash
./configurer_tableau.sh
```

Sous Windows, double-cliquez sur `configurer_tableau.bat`.

L'interface :

1. affiche au démarrage le dernier fichier de configuration utilisé ;
2. permet de choisir un autre fichier JSON ;
3. permet de choisir le fichier Excel des classements ;
4. lance la résolution avec le bouton **Calculer**.

La méthode de recherche et l'objectif du calcul se choisissent séparément :

- **Rapide — retour arrière aléatoire** utilise le solveur historique et fait
  varier l'ordre des candidats. Cette méthode convient pour obtenir rapidement
  un aperçu valide ;
- **Intelligent — contraction de Hall et séparation 1/reste** représente les
  positions par des domaines de joueurs possibles. Il retire les valeurs
  incompatibles, réserve automatiquement les groupes de joueurs imposés par la
  contrainte `all-different`, puis sépare le domaine le plus contraint en un
  candidat prioritaire et tous les autres. Cette séparation dissymétrique
  permet de zoomer rapidement vers une solution. Jusqu'à huit régions sont
  explorées à tour de rôle afin que les premières solutions proviennent de
  parties différentes de l'espace de recherche, tout en gardant une file de
  recherche de taille bornée.

Avec l'une ou l'autre méthode, on peut demander **1 solution**, **N solutions**
ou **toutes les solutions**. Une limite N arrête automatiquement la recherche
dès que N tirages ont été conservés. Le bouton d'arrêt reste disponible pendant
le calcul. L'énumération de toutes les solutions est exhaustive, mais peut être
très longue et consommer beaucoup de mémoire puisque les tirages sont conservés
pour l'export Excel.

Pour obtenir rapidement quelques tirages, utilisez **Rapide** avec **Calculer N
solutions**. Les contraintes sont indexées par position et les participants
possibles des matchs sont mémorisés pendant chaque essai. En mode Intelligent,
un objectif limité suit une seule trajectoire prioritaire ; les huit régions ne
sont utilisées que pour une exploration exhaustive.

Les contraintes équivalentes sont aussi regroupées uniquement en mémoire. Par
exemple, tant que les résultats ne sont pas connus, le vainqueur et le perdant
d'un même match ont le même ensemble de joueurs possibles : une même règle sur
le match des vainqueurs et sur celui des perdants n'est donc évaluée qu'une
fois. Les deux définitions restent présentes dans le JSON et dans l'éditeur.

Le bouton **Construire le problème** compile ces règles en relations unaires et
binaires entre positions, puis crée un fichier `.ptjaplan` à côté du JSON. Ce
plan dépend uniquement de la configuration : il reste donc utilisable après le
chargement d'un autre fichier Excel ou le remplacement de tous les joueurs. Il
est chargé automatiquement pendant les calculs. Une modification du JSON
invalide son empreinte et provoque sa reconstruction automatique.

L'onglet **Détails du calcul** suit séparément le chargement des fichiers, la
construction du problème, la résolution et la création du résultat. Pendant
la résolution, il affiche le nombre de solutions et, selon la méthode, les
branches évaluées ou les boîtes explorées, les séparations 1/reste et les
réductions de domaines, dont celles obtenues par la contraction de Hall. Tout
calcul peut être arrêté en conservant les solutions déjà calculées.

Les boutons **Créer…** et **Éditer…** ouvrent l'éditeur graphique des
configurations JSON v2. Ses onglets permettent de régler les paramètres
généraux, de générer une structure standard, de partir de zéro, puis
d'ajouter, modifier ou supprimer les matchs et les contraintes. Un dernier
onglet affiche le JSON produit avant son enregistrement.

Le menu **Fichier** de l'éditeur permet de créer une nouvelle configuration,
d'ouvrir un autre JSON, d'enregistrer ou d'enregistrer sous un nouveau nom.

L'onglet **Visualisation** dessine le tableau : places des joueurs de haut en
bas, matchs répartis par tour et liaisons `V` (vainqueur) ou `P` (perdant).
Le dessin est défilable et dispose de commandes de zoom. Un panneau latéral
permet aussi de voir, ajouter, modifier ou supprimer les contraintes. Les
matchs concernés sont signalés sur le dessin et mis en évidence quand une
contrainte est sélectionnée.

Une position ou un match peut être sélectionné directement sur le dessin.
`Ctrl+clic` compose un ensemble de matchs et un clic sur l'en-tête d'une
colonne sélectionne tous ses matchs. Le bouton **Ajouter** reprend cette cible
automatiquement. Une position accepte notamment une contrainte sur les rangs
de poule autorisés.

Le formulaire d'ajout et de modification affiche une aide contextuelle : effet
de la contrainte, format de la cible, exemple de valeurs et champs à remplir.
Les champs sans rapport avec le type sélectionné sont automatiquement grisés.

Quand une position, un match ou une colonne est sélectionné, le panneau de la
visualisation ne montre que les contraintes correspondantes. Le bouton
**Afficher toutes les contraintes du tableau** retire ce filtre. Le chemin
complet du fichier JSON ouvert est visible en bas de la fenêtre.

Une même contrainte peut cibler plusieurs matchs du même niveau. Une contrainte
appliquée à un niveau accepte aussi une liste de matchs exclus. Depuis la
visualisation d'un match, supprimer une contrainte héritée du niveau crée cette
exception au lieu de supprimer la règle pour tous les autres matchs.

La portée est affichée avec des libellés explicites : contrainte directe,
groupe de matchs, niveau entier ou contrainte héritée d'un niveau. Le JSON ne
contient qu'une définition pour une contrainte de niveau ; le chargeur la
développe en règles par match uniquement en mémoire pendant le calcul.
L'option générale **Aucune contrainte** enregistre simplement une liste
`contraintes` vide, sans ajouter de drapeau particulier au JSON.

Une contrainte peut recevoir un champ `nom` lisible, affiché dans l'éditeur à
la place du type technique. Les cibles `positions` et `niveaux` regroupent
plusieurs positions ou plusieurs colonnes dans une seule règle. Pour une
contrainte `rangs_match`, l'option `ordonne: true` signifie que le premier rang
est imposé au participant 1 et le second au participant 2 ; elle évite de
compter l'inversion verticale d'un même match comme un nouveau tirage.

L'éditeur prend en charge les tailles 8, 16, 32, 64, 128, 256 ou une puissance
de deux supérieure et le classement intégral. Si les barrages 1er-4e ne sont
pas activés, les 2es et 3es jouent un barrage : le gagnant rejoint un 1er dans
le tableau supérieur et le perdant rejoint un 4e dans le tableau inférieur.
Une poule de trois est automatiquement complétée par un 4e joueur vide.
Chaque participant d'un match se note sous la forme `position:1`,
`vainqueur:2` ou `perdant:2`.

Le résultat est créé à côté du fichier Excel avec le suffixe
`_solution.xlsx`.

La configuration livrée par défaut est
`ping_table_ja/configurations/tableau_integral_32.json`.

### Ligne de commande

```bash
python -m ping_table_ja classement.xlsx
python -m ping_table_ja classement.xlsx --onglet "classement poules" --sortie resultat.xlsx
```

Après installation, les commandes `ping-table-ja` et `ping-table-ja-gui`
peuvent également être utilisées.

## Organisation

```text
double_ko32/
├── configuration.py     # Graphe des matchs et liste des contraintes
├── configuration_fichier.py # Chargement du JSON de configuration
├── configurations/      # Configurations livrées avec l'application
├── modele.py             # Match, ResultatMatch, PositionTableau
├── evaluation_contraintes.py # Compilation et sauvegarde du plan de contraintes
├── solveur.py            # Algorithme de placement
├── solveur_bissection.py # Contraction de Hall et séparation 1/reste
├── excel.py              # Entrées/sorties Excel
├── utilitaires.py        # Normalisation et nettoyage
├── cli.py                # Interface en ligne de commande
├── gui.py                # Interface graphique
└── contraintes/
    ├── base.py           # Contrat commun et vérification
    ├── placement.py      # Contraintes de position
    └── matchs.py         # Contraintes liées aux matchs
```

Le fichier JSON sélectionne le générateur et les paramètres du tournoi. La
définition métier actuelle reste isolée dans `configuration.py`.
