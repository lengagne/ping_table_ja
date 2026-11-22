"""Chargement et validation des fichiers de configuration JSON."""

import json
from dataclasses import dataclass
from pathlib import Path

from .configuration import creer_contraintes, creer_matchs


@dataclass(frozen=True)
class ConfigurationTournoi:
    matchs: dict
    contraintes: list
    nombre_positions: int = 32
    onglet_excel: str = "classement poules"
    onglet_sortie: str = "TropFortSeb"


def charger_configuration(chemin):
    """Charge un fichier JSON et construit le tournoi correspondant."""
    chemin = Path(chemin)
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except FileNotFoundError as erreur:
        raise ValueError("Fichier de configuration introuvable : {}".format(chemin)) from erreur
    except json.JSONDecodeError as erreur:
        raise ValueError(
            "Configuration JSON invalide (ligne {}, colonne {})".format(erreur.lineno, erreur.colno)
        ) from erreur

    if donnees.get("version") != 1:
        raise ValueError("Version de configuration non prise en charge")
    if donnees.get("generateur") != "double_ko32":
        raise ValueError("Générateur inconnu : {!r}".format(donnees.get("generateur")))

    nombre_positions = int(donnees.get("nombre_positions", 32))
    if nombre_positions != 32:
        raise ValueError("La configuration Double KO attend exactement 32 positions")

    matchs = creer_matchs()
    return ConfigurationTournoi(
        matchs=matchs,
        contraintes=creer_contraintes(matchs),
        nombre_positions=nombre_positions,
        onglet_excel=str(donnees.get("onglet_excel", "classement poules")),
        onglet_sortie=str(donnees.get("onglet_sortie", "TropFortSeb")),
    )


def configuration_par_defaut():
    """Retourne le fichier de configuration livré avec l'application."""
    return Path(__file__).resolve().parent / "configurations" / "double_ko32.json"
