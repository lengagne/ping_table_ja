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
`ping_table_ja/configurations/double_ko32.json`.

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
├── solveur.py            # Algorithme de placement
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
