"""Compilation et indexation des contraintes du tableau."""

import hashlib
import json
from pathlib import Path

from .contraintes import (
    ClubsDifferents,
    ClubsDifferentsParticipants,
    JoueursDansPositions,
    MemePouleInterdite,
    PositionImposee,
    RangsMatchImposes,
    RangsMemePouleInterdits,
    RangsParticipantsImposes,
    RangsPositionImposes,
)
from .utilitaires import normaliser_club


def positions_participant(participant, cache=None):
    """Retourne les positions initiales pouvant alimenter un participant."""
    cache = {} if cache is None else cache
    position = getattr(participant, "position", None)
    if position is not None:
        return {int(position) - 1}

    match = getattr(participant, "match", None)
    if match is None and hasattr(participant, "participant_1"):
        match = participant
    if match is None:
        return set()
    if match not in cache:
        cache[match] = (
            positions_participant(match.participant_1, cache)
            | positions_participant(match.participant_2, cache)
        )
    return set(cache[match])


def _positions_match(match, cache):
    return positions_participant(match.participant_1, cache) | positions_participant(
        match.participant_2, cache
    )


def _sources_participant(participant, cache):
    """Décrit les joueurs possibles, en confondant vainqueur et perdant non résolus."""
    if participant in cache:
        return cache[participant]

    position = getattr(participant, "position", None)
    if position is not None:
        sources = frozenset({("position", int(position) - 1)})
        cache[participant] = sources
        return sources

    match = getattr(participant, "match", None)
    resultat = getattr(participant, "resultat", None)
    if match is not None and resultat is not None:
        joueur_reel = match.resultat_reel(resultat)
        if joueur_reel is not None:
            sources = frozenset({("joueur", id(joueur_reel))})
            cache[participant] = sources
            return sources
    if match is None and hasattr(participant, "participant_1"):
        match = participant
    if match is None:
        sources = frozenset()
    else:
        sources = _sources_participant(
            match.participant_1, cache
        ) | _sources_participant(match.participant_2, cache)
    cache[participant] = sources
    return sources


def _signature_participant(participant, cache):
    return tuple(sorted(_sources_participant(participant, cache)))


def _paire_participants(participant_1, participant_2, cache):
    return tuple(
        sorted(
            (
                _signature_participant(participant_1, cache),
                _signature_participant(participant_2, cache),
            )
        )
    )


def signature_contrainte(contrainte, cache_participants=None):
    """Produit une signature sémantique pour regrouper les règles équivalentes."""
    cache = {} if cache_participants is None else cache_participants

    if isinstance(contrainte, RangsMemePouleInterdits):
        return (
            "rangs_meme_poule_interdits",
            _paire_participants(
                contrainte.match.participant_1,
                contrainte.match.participant_2,
                cache,
            ),
            tuple(contrainte.rangs_interdits),
        )
    if isinstance(contrainte, MemePouleInterdite):
        return (
            "meme_poule_interdite",
            _paire_participants(
                contrainte.match.participant_1,
                contrainte.match.participant_2,
                cache,
            ),
        )
    if isinstance(contrainte, ClubsDifferentsParticipants):
        return (
            "clubs_differents_participants",
            _paire_participants(
                contrainte.participant_1, contrainte.participant_2, cache
            ),
        )
    if isinstance(contrainte, RangsParticipantsImposes):
        participants = (
            (
                _signature_participant(contrainte.match.participant_1, cache),
                tuple(sorted(contrainte.rangs[0])),
            ),
            (
                _signature_participant(contrainte.match.participant_2, cache),
                tuple(sorted(contrainte.rangs[1])),
            ),
        )
        return "rangs_participants_imposes", tuple(sorted(participants))
    if isinstance(contrainte, RangsMatchImposes):
        return (
            "rangs_match_imposes",
            _paire_participants(
                contrainte.match.participant_1,
                contrainte.match.participant_2,
                cache,
            ),
            tuple(contrainte.rangs_attendus),
        )
    if isinstance(contrainte, RangsPositionImposes):
        return (
            "rangs_position_imposes",
            contrainte.position,
            tuple(sorted(contrainte.rangs)),
            tuple(sorted(contrainte.poules)),
        )
    if isinstance(contrainte, ClubsDifferents):
        return (
            "clubs_differents",
            tuple(sorted((contrainte.position_1, contrainte.position_2))),
        )
    if isinstance(contrainte, PositionImposee):
        return "position_imposee", contrainte.joueur_attendu, contrainte.position
    if isinstance(contrainte, JoueursDansPositions):
        return (
            "joueurs_dans_positions",
            tuple(sorted(contrainte.joueurs_attendus)),
            tuple(sorted(contrainte.positions)),
        )
    return "contrainte_non_regroupable", id(contrainte)


def dedupliquer_contraintes(contraintes):
    """Conserve une seule évaluation de chaque contrainte sémantiquement identique."""
    resultat = []
    signatures = set()
    cache_participants = {}
    for contrainte in contraintes:
        signature = signature_contrainte(contrainte, cache_participants)
        if signature in signatures:
            continue
        signatures.add(signature)
        resultat.append(contrainte)
    return tuple(resultat)


def _figer(valeur):
    if isinstance(valeur, list):
        return tuple(_figer(element) for element in valeur)
    return valeur


class PlanContraintes:
    """Forme compilée, indépendante des joueurs, des contraintes du tableau."""

    VERSION = 1

    def __init__(
        self,
        unaires,
        binaires,
        contraintes_residuelles=(),
        nombre_contraintes=0,
        contraintes_effectives=0,
    ):
        self.unaires = tuple(tuple(regles) for regles in unaires)
        self.binaires = tuple(
            {
                int(position): tuple(regles)
                for position, regles in voisins.items()
            }
            for voisins in binaires
        )
        self.contraintes_residuelles = tuple(contraintes_residuelles)
        self.nombre_contraintes = int(nombre_contraintes)
        self.contraintes_effectives = int(contraintes_effectives)

    @property
    def nombre_positions(self):
        return len(self.unaires)

    @property
    def contraintes_regroupees(self):
        return self.nombre_contraintes - self.contraintes_effectives

    @property
    def est_entierement_serialisable(self):
        return not self.contraintes_residuelles

    def vers_donnees(self):
        if not self.est_entierement_serialisable:
            raise ValueError(
                "Le plan contient des contraintes inconnues non sérialisables."
            )
        return {
            "version": self.VERSION,
            "nombre_positions": self.nombre_positions,
            "nombre_contraintes": self.nombre_contraintes,
            "contraintes_effectives": self.contraintes_effectives,
            "unaires": [list(regles) for regles in self.unaires],
            "binaires": [
                [
                    {"position": position, "regles": list(regles)}
                    for position, regles in sorted(voisins.items())
                ]
                for voisins in self.binaires
            ],
        }

    @classmethod
    def depuis_donnees(cls, donnees):
        if int(donnees.get("version", 0)) != cls.VERSION:
            raise ValueError("Version du plan de contraintes incompatible.")
        unaires = [
            tuple(_figer(regle) for regle in regles)
            for regles in donnees["unaires"]
        ]
        binaires = []
        for voisins in donnees["binaires"]:
            binaires.append(
                {
                    int(entree["position"]): tuple(
                        _figer(regle) for regle in entree["regles"]
                    )
                    for entree in voisins
                }
            )
        plan = cls(
            unaires,
            binaires,
            nombre_contraintes=donnees.get("nombre_contraintes", 0),
            contraintes_effectives=donnees.get("contraintes_effectives", 0),
        )
        if plan.nombre_positions != int(donnees["nombre_positions"]):
            raise ValueError("Nombre de positions incohérent dans le plan.")
        return plan

    def creer_evaluateur(self, joueurs):
        return EvaluateurPlanContraintes(self, joueurs)


class EvaluateurPlanContraintes:
    """Applique un plan compilé aux caractéristiques d'une liste de joueurs."""

    def __init__(self, plan, joueurs):
        self.plan = plan
        self.caracteristiques = {
            id(joueur): self._extraire_caracteristiques(joueur)
            for joueur in joueurs
        }
        self.residuelles_par_position = indexer_contraintes_par_position(
            plan.contraintes_residuelles, plan.nombre_positions
        )

    @staticmethod
    def _extraire_caracteristiques(joueur):
        poule_brute = joueur.get("poule")
        rang_brut = joueur.get("rang_poule")
        poule = int(poule_brute) if poule_brute is not None else None
        rang = int(rang_brut) if rang_brut is not None else None
        return poule, rang, normaliser_club(joueur.get("club")), (poule, rang)

    def _caracteristiques(self, joueur):
        cle = id(joueur)
        if cle not in self.caracteristiques:
            self.caracteristiques[cle] = self._extraire_caracteristiques(joueur)
        return self.caracteristiques[cle]

    @staticmethod
    def _unaire_valide(regle, caracteristiques):
        type_regle = regle[0]
        poule, rang, _club, identite = caracteristiques
        if type_regle == "rangs_poules":
            rangs, poules = regle[1], regle[2]
            return rang in rangs and (not poules or poule in poules)
        if type_regle == "rangs":
            return rang in regle[1]
        if type_regle == "identite_egale":
            return identite == regle[1]
        if type_regle == "identites_interdites":
            return identite not in regle[1]
        raise ValueError("Règle unaire inconnue : {}".format(type_regle))

    @staticmethod
    def _binaire_valide(regle, caracteristiques_1, caracteristiques_2):
        type_regle = regle[0]
        poule_1, rang_1, club_1, _identite_1 = caracteristiques_1
        poule_2, rang_2, club_2, _identite_2 = caracteristiques_2
        if type_regle == "clubs_differents":
            return not club_1 or not club_2 or club_1 != club_2
        if type_regle == "poules_differentes":
            return poule_1 != poule_2
        if type_regle == "rangs_meme_poule_interdits":
            return not (
                poule_1 == poule_2
                and tuple(sorted((rang_1, rang_2))) == regle[1]
            )
        if type_regle == "rangs_match":
            return tuple(sorted((rang_1, rang_2))) == regle[1]
        raise ValueError("Règle binaire inconnue : {}".format(type_regle))

    def est_compatible(self, position, placement):
        joueur = placement[position]
        if joueur is None:
            return True
        caracteristiques = self._caracteristiques(joueur)
        if not all(
            self._unaire_valide(regle, caracteristiques)
            for regle in self.plan.unaires[position]
        ):
            return False
        for autre_position, regles in self.plan.binaires[position].items():
            autre_joueur = placement[autre_position]
            if autre_joueur is None:
                continue
            autres_caracteristiques = self._caracteristiques(autre_joueur)
            if not all(
                self._binaire_valide(
                    regle, caracteristiques, autres_caracteristiques
                )
                for regle in regles
            ):
                return False
        return all(
            contrainte.est_compatible(placement)
            for contrainte in self.residuelles_par_position[position]
        )

    def placement_compatible(self, placement):
        for position, joueur in enumerate(placement):
            if joueur is None:
                continue
            caracteristiques = self._caracteristiques(joueur)
            if not all(
                self._unaire_valide(regle, caracteristiques)
                for regle in self.plan.unaires[position]
            ):
                return False
            for autre_position, regles in self.plan.binaires[position].items():
                if autre_position <= position:
                    continue
                autre_joueur = placement[autre_position]
                if autre_joueur is None:
                    continue
                autres_caracteristiques = self._caracteristiques(autre_joueur)
                if not all(
                    self._binaire_valide(
                        regle, caracteristiques, autres_caracteristiques
                    )
                    for regle in regles
                ):
                    return False
        return all(
            contrainte.est_compatible(placement)
            for contrainte in self.plan.contraintes_residuelles
        )


def compiler_plan_contraintes(contraintes, nombre_positions):
    """Compile les contraintes en règles unaires et binaires réutilisables."""
    nombre_contraintes = len(contraintes)
    contraintes = dedupliquer_contraintes(contraintes)
    unaires = [set() for _ in range(nombre_positions)]
    binaires = [dict() for _ in range(nombre_positions)]
    residuelles = []
    cache_positions = {}
    cache_sources = {}

    def ajouter_unaire(position, regle):
        if 0 <= position < nombre_positions:
            unaires[position].add(regle)

    def ajouter_binaire(position_1, position_2, regle):
        if position_1 == position_2:
            return False
        binaires[position_1].setdefault(position_2, set()).add(regle)
        binaires[position_2].setdefault(position_1, set()).add(regle)
        return True

    def positions_compilables(participant):
        sources = _sources_participant(participant, cache_sources)
        if any(type_source != "position" for type_source, _valeur in sources):
            return None
        return {valeur for _type_source, valeur in sources}

    def ajouter_croisement(participant_1, participant_2, regle):
        positions_1 = positions_compilables(participant_1)
        positions_2 = positions_compilables(participant_2)
        if positions_1 is None or positions_2 is None or positions_1 & positions_2:
            return False
        for position_1 in positions_1:
            for position_2 in positions_2:
                ajouter_binaire(position_1, position_2, regle)
        return True

    for contrainte in contraintes:
        compilee = True
        if isinstance(contrainte, RangsMemePouleInterdits):
            compilee = ajouter_croisement(
                contrainte.match.participant_1,
                contrainte.match.participant_2,
                ("rangs_meme_poule_interdits", tuple(contrainte.rangs_interdits)),
            )
        elif isinstance(contrainte, MemePouleInterdite):
            compilee = ajouter_croisement(
                contrainte.match.participant_1,
                contrainte.match.participant_2,
                ("poules_differentes",),
            )
        elif isinstance(contrainte, ClubsDifferentsParticipants):
            compilee = ajouter_croisement(
                contrainte.participant_1,
                contrainte.participant_2,
                ("clubs_differents",),
            )
        elif isinstance(contrainte, RangsParticipantsImposes):
            for participant, rangs in zip(
                (contrainte.match.participant_1, contrainte.match.participant_2),
                contrainte.rangs,
            ):
                positions = positions_compilables(participant)
                if positions is None:
                    compilee = False
                    break
                for position in positions:
                    ajouter_unaire(position, ("rangs", tuple(sorted(rangs))))
        elif isinstance(contrainte, RangsMatchImposes):
            participants = (
                contrainte.match.participant_1,
                contrainte.match.participant_2,
            )
            positions_participants = [
                positions_compilables(participant) for participant in participants
            ]
            if any(positions is None for positions in positions_participants):
                compilee = False
            else:
                rangs = tuple(contrainte.rangs_attendus)
                for positions in positions_participants:
                    for position in positions:
                        ajouter_unaire(position, ("rangs", rangs))
                compilee = ajouter_croisement(
                    participants[0], participants[1], ("rangs_match", rangs)
                )
        elif isinstance(contrainte, RangsPositionImposes):
            ajouter_unaire(
                contrainte.position - 1,
                (
                    "rangs_poules",
                    tuple(sorted(contrainte.rangs)),
                    tuple(sorted(contrainte.poules)),
                ),
            )
        elif isinstance(contrainte, ClubsDifferents):
            compilee = ajouter_binaire(
                contrainte.position_1 - 1,
                contrainte.position_2 - 1,
                ("clubs_differents",),
            )
        elif isinstance(contrainte, PositionImposee):
            identite = tuple(contrainte.joueur_attendu)
            for position in range(nombre_positions):
                if position == contrainte.position - 1:
                    ajouter_unaire(position, ("identite_egale", identite))
                else:
                    ajouter_unaire(
                        position, ("identites_interdites", (identite,))
                    )
        elif isinstance(contrainte, JoueursDansPositions):
            identites = tuple(sorted(contrainte.joueurs_attendus))
            positions_autorisees = {
                int(position) - 1 for position in contrainte.positions
            }
            for position in range(nombre_positions):
                if position not in positions_autorisees:
                    ajouter_unaire(
                        position, ("identites_interdites", identites)
                    )
        else:
            compilee = False

        if not compilee:
            residuelles.append(contrainte)

    return PlanContraintes(
        [tuple(sorted(regles)) for regles in unaires],
        [
            {
                position: tuple(sorted(regles))
                for position, regles in voisins.items()
            }
            for voisins in binaires
        ],
        contraintes_residuelles=residuelles,
        nombre_contraintes=nombre_contraintes,
        contraintes_effectives=len(contraintes),
    )


def chemin_plan_contraintes(chemin_configuration):
    """Place le plan à côté du JSON sans le confondre avec une configuration."""
    chemin = Path(chemin_configuration)
    return chemin.with_suffix(".ptjaplan")


def empreinte_configuration(chemin_configuration):
    """Identifie le contenu du JSON et la version du compilateur de contraintes."""
    condensat = hashlib.sha256()
    condensat.update(
        "ping-table-ja-plan-v{}\0".format(PlanContraintes.VERSION).encode("ascii")
    )
    with Path(chemin_configuration).open("rb") as fichier:
        for bloc in iter(lambda: fichier.read(1024 * 1024), b""):
            condensat.update(bloc)
    return condensat.hexdigest()


def enregistrer_plan_contraintes(chemin_configuration, plan):
    """Enregistre atomiquement un plan réutilisable avec d'autres joueurs."""
    chemin = chemin_plan_contraintes(chemin_configuration)
    donnees = {
        "format": "ping-table-ja-plan",
        "empreinte_configuration": empreinte_configuration(chemin_configuration),
        "plan": plan.vers_donnees(),
    }
    temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    temporaire.write_text(
        json.dumps(donnees, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporaire.replace(chemin)
    return chemin


def charger_plan_contraintes(chemin_configuration, nombre_positions):
    """Charge le plan seulement s'il correspond encore exactement au JSON."""
    chemin = chemin_plan_contraintes(chemin_configuration)
    if not chemin.is_file():
        return None
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
        if donnees.get("format") != "ping-table-ja-plan":
            return None
        if donnees.get("empreinte_configuration") != empreinte_configuration(
            chemin_configuration
        ):
            return None
        plan = PlanContraintes.depuis_donnees(donnees["plan"])
        if plan.nombre_positions != int(nombre_positions):
            return None
        return plan
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def positions_contrainte(contrainte, nombre_positions, cache_participants=None):
    """Détermine prudemment les positions dont dépend une contrainte."""
    toutes = set(range(nombre_positions))
    cache = {} if cache_participants is None else cache_participants

    if isinstance(contrainte, (PositionImposee, JoueursDansPositions)):
        # Ces contraintes recherchent aussi le joueur attendu hors de leur cible.
        return toutes
    if isinstance(contrainte, RangsPositionImposes):
        return {contrainte.position - 1}
    if isinstance(contrainte, ClubsDifferents):
        return {contrainte.position_1 - 1, contrainte.position_2 - 1}
    if isinstance(contrainte, ClubsDifferentsParticipants):
        return positions_participant(
            contrainte.participant_1, cache
        ) | positions_participant(contrainte.participant_2, cache)
    if isinstance(
        contrainte,
        (RangsMatchImposes, RangsParticipantsImposes, MemePouleInterdite),
    ):
        return _positions_match(contrainte.match, cache)

    # Une future famille de contraintes inconnue reste évaluée partout.
    return toutes


def indexer_contraintes_par_position(contraintes, nombre_positions):
    """Prépare les seules contraintes à réévaluer après chaque affectation."""
    index = [[] for _ in range(nombre_positions)]
    cache_participants = {}
    for contrainte in contraintes:
        positions = positions_contrainte(
            contrainte, nombre_positions, cache_participants
        )
        for position in positions:
            if 0 <= position < nombre_positions:
                index[position].append(contrainte)
    return tuple(tuple(groupe) for groupe in index)
