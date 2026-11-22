# Ping table JA

Génère le placement de joueurs dans un tableau double élimination à partir d'un classement de poules stocké dans un fichier Excel.

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

```bash
python -m double_ko32 classement.xlsx
python -m double_ko32 classement.xlsx --onglet "classement poules" --sortie resultat.xlsx
```

Après installation, la commande `double-ko32` peut également être utilisée.

## Organisation

```text
double_ko32/
├── configuration.py     # Graphe des matchs et liste des contraintes
├── modele.py             # Match, ResultatMatch, PositionTableau
├── solveur.py            # Algorithme de placement
├── excel.py              # Entrées/sorties Excel
├── utilitaires.py        # Normalisation et nettoyage
├── cli.py                # Interface en ligne de commande
└── contraintes/
    ├── base.py           # Contrat commun et vérification
    ├── placement.py      # Contraintes de position
    └── matchs.py         # Contraintes liées aux matchs
```

La définition du tournoi est isolée dans `configuration.py`. C'est le seul
module à modifier pour changer les matchs ou les règles du tableau.
