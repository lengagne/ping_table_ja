"""Chargement et validation des fichiers de configuration JSON."""

import json
from dataclasses import dataclass
from pathlib import Path

from .configuration import creer_contraintes, creer_matchs
from .contraintes import (
    ClubsDifferentsParticipants,
    MemePouleInterdite,
    RangsMatchImposes,
    RangsParticipantsImposes,
)
from .modele import Match, PositionTableau


@dataclass(frozen=True)
class ConfigurationTournoi:
    matchs: dict
    contraintes: list
    nombre_positions: int = 32
    onglet_excel: str = "classement poules"
    onglet_sortie: str = "TropFortSeb"
    nom: str = ""
    classement_integral: bool = False
    barrages_1_contre_4: bool = False


def _participant_depuis_json(donnees, matchs, taille_tableau):
    type_participant = donnees.get("type")
    if type_participant == "position":
        numero = int(donnees.get("numero", 0))
        if not 1 <= numero <= taille_tableau:
            raise ValueError("Position de joueur invalide : {}".format(numero))
        return PositionTableau(numero)
    if type_participant in ("vainqueur", "perdant"):
        numero_match = int(donnees.get("match", 0))
        if numero_match not in matchs:
            raise ValueError(
                "Le match {} doit être défini avant d'être référencé".format(numero_match)
            )
        return getattr(matchs[numero_match], type_participant)
    raise ValueError("Type de participant inconnu : {!r}".format(type_participant))


def _matchs_depuis_json(donnees, taille_tableau):
    matchs = {}
    for definition in donnees:
        numero = int(definition.get("numero", 0))
        if numero <= 0 or numero in matchs:
            raise ValueError("Numéro de match invalide ou dupliqué : {}".format(numero))
        participant_1 = _participant_depuis_json(
            definition.get("participant_1", {}), matchs, taille_tableau
        )
        participant_2 = _participant_depuis_json(
            definition.get("participant_2", {}), matchs, taille_tableau
        )
        matchs[numero] = Match(
            numero,
            participant_1,
            participant_2,
            niveau=str(definition.get("niveau", "")),
            places=definition.get("places", []),
        )
    return matchs


def _matchs_cibles(cible, matchs):
    type_cible = cible.get("type")
    if type_cible == "match":
        numero = int(cible.get("numero", 0))
        if numero not in matchs:
            raise ValueError("Match ciblé introuvable : {}".format(numero))
        return [matchs[numero]]
    if type_cible == "niveau":
        niveau = str(cible.get("niveau", ""))
        resultat = [match for match in matchs.values() if match.niveau == niveau]
        if not resultat:
            raise ValueError("Niveau ciblé introuvable : {!r}".format(niveau))
        return resultat
    raise ValueError("Type de cible inconnu : {!r}".format(type_cible))


def _contraintes_depuis_json(definitions, matchs):
    resultat = []
    for definition in definitions:
        type_contrainte = definition.get("type")
        cibles = _matchs_cibles(definition.get("cible", {}), matchs)
        for match in cibles:
            if type_contrainte == "poules_differentes":
                resultat.append(MemePouleInterdite(match))
            elif type_contrainte == "clubs_differents":
                resultat.append(ClubsDifferentsParticipants(
                    match.participant_1, match.participant_2
                ))
            elif type_contrainte == "rangs_match":
                rangs = definition.get("rangs", [])
                if len(rangs) != 2:
                    raise ValueError("La contrainte rangs_match attend exactement deux rangs")
                resultat.append(RangsMatchImposes(match, rangs[0], rangs[1]))
            elif type_contrainte == "rangs_participants":
                rangs_1 = definition.get("participant_1", [])
                rangs_2 = definition.get("participant_2", [])
                if not rangs_1 or not rangs_2:
                    raise ValueError("Les rangs des deux participants sont obligatoires")
                resultat.append(RangsParticipantsImposes(match, rangs_1, rangs_2))
            else:
                raise ValueError("Type de contrainte inconnu : {!r}".format(type_contrainte))
    return resultat


def _charger_configuration_v2(donnees):
    taille_tableau = int(donnees.get("taille_tableau", 0))
    if taille_tableau < 2:
        raise ValueError("La taille du tableau doit être supérieure ou égale à 2")
    matchs = _matchs_depuis_json(donnees.get("matchs", []), taille_tableau)
    if not matchs:
        raise ValueError("La configuration doit contenir au moins un match")
    return ConfigurationTournoi(
        matchs=matchs,
        contraintes=_contraintes_depuis_json(donnees.get("contraintes", []), matchs),
        nombre_positions=taille_tableau,
        onglet_excel=str(donnees.get("onglet_excel", "classement poules")),
        onglet_sortie=str(donnees.get("onglet_sortie", "TropFortSeb")),
        nom=str(donnees.get("nom", "")),
        classement_integral=bool(donnees.get("classement_integral", False)),
        barrages_1_contre_4=bool(donnees.get("barrages_1_contre_4", False)),
    )


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

    if donnees.get("version") == 2:
        return _charger_configuration_v2(donnees)
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
        nom=str(donnees.get("nom", "Double KO - 32 joueurs")),
        classement_integral=True,
    )


def enregistrer_configuration(chemin, donnees):
    """Valide puis enregistre une configuration JSON lisible."""
    chemin = Path(chemin)
    temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    temporaire.parent.mkdir(parents=True, exist_ok=True)
    temporaire.write_text(
        json.dumps(donnees, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        charger_configuration(temporaire)
        temporaire.replace(chemin)
    finally:
        if temporaire.exists():
            temporaire.unlink()


def configuration_par_defaut():
    """Retourne le fichier de configuration livré avec l'application."""
    return Path(__file__).resolve().parent / "configurations" / "double_ko32.json"
