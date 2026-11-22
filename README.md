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

L'interface :

1. affiche au démarrage le dernier fichier de configuration utilisé ;
2. permet de choisir un autre fichier JSON ;
3. permet de choisir le fichier Excel des classements ;
4. lance la résolution avec le bouton **Calculer**.

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
