"""Contraintes portant sur les participants possibles d'un match."""

from .base import Contrainte
from ..utilitaires import normaliser_club


class ClubsDifferentsParticipants(Contrainte):
    def __init__(self, participant_1, participant_2):
        self.participant_1, self.participant_2 = participant_1, participant_2

    @staticmethod
    def _clubs(participant, placement):
        return {
            normaliser_club(joueur.get("club"))
            for joueur in participant.joueurs_possibles(placement)
            if normaliser_club(joueur.get("club"))
        }

    def est_compatible(self, placement):
        joueurs_1 = self.participant_1.joueurs_possibles(placement)
        joueurs_2 = self.participant_2.joueurs_possibles(placement)
        if not joueurs_1 or not joueurs_2:
            return True
        return self._clubs(self.participant_1, placement).isdisjoint(
            self._clubs(self.participant_2, placement)
        )

    def est_respectee(self, placement):
        joueurs_1 = self.participant_1.joueurs_possibles(placement)
        joueurs_2 = self.participant_2.joueurs_possibles(placement)
        return bool(joueurs_1 and joueurs_2) and self.est_compatible(placement)

    def description(self):
        return "Clubs différents entre {} et {}".format(
            self.participant_1.description(), self.participant_2.description()
        )


class RangsMatchImposes(Contrainte):
    def __init__(self, match, rang_1, rang_2):
        self.match = match
        self.rangs_attendus = sorted([rang_1, rang_2])

    def _combinaison_valide(self, joueur_1, joueur_2):
        return sorted([int(joueur_1["rang_poule"]), int(joueur_2["rang_poule"])]) == self.rangs_attendus

    def _candidats(self, placement):
        return (self.match.participant_1.joueurs_possibles(placement),
                self.match.participant_2.joueurs_possibles(placement))

    def est_compatible(self, placement):
        candidats_1, candidats_2 = self._candidats(placement)
        if not candidats_1 or not candidats_2:
            return True
        return all(self._combinaison_valide(a, b) for a in candidats_1 for b in candidats_2)

    def est_respectee(self, placement):
        candidats_1, candidats_2 = self._candidats(placement)
        return bool(candidats_1 and candidats_2) and self.est_compatible(placement)

    def description(self):
        return "Le match {} doit opposer les rangs {} et {}".format(
            self.match.numero, *self.rangs_attendus
        )


class RangsParticipantsImposes(Contrainte):
    """Impose séparément les rangs possibles de chaque participant d'un match."""

    def __init__(self, match, rangs_participant_1, rangs_participant_2):
        self.match = match
        self.rangs = (
            {int(rang) for rang in rangs_participant_1},
            {int(rang) for rang in rangs_participant_2},
        )

    def _candidats_valides(self, participant, rangs, placement):
        candidats = participant.joueurs_possibles(placement)
        return not candidats or all(int(joueur["rang_poule"]) in rangs for joueur in candidats)

    def est_compatible(self, placement):
        return self._candidats_valides(self.match.participant_1, self.rangs[0], placement) and (
            self._candidats_valides(self.match.participant_2, self.rangs[1], placement)
        )

    def est_respectee(self, placement):
        candidats = (
            self.match.participant_1.joueurs_possibles(placement),
            self.match.participant_2.joueurs_possibles(placement),
        )
        return all(candidats) and self.est_compatible(placement)

    def description(self):
        return "Le match {} impose les rangs {} puis {}".format(
            self.match.numero, sorted(self.rangs[0]), sorted(self.rangs[1])
        )


class MemePouleInterdite(Contrainte):
    def __init__(self, match):
        self.match = match

    def _candidats(self, placement):
        return (self.match.participant_1.joueurs_possibles(placement),
                self.match.participant_2.joueurs_possibles(placement))

    @staticmethod
    def _rencontre_interdite(joueur_1, joueur_2):
        return int(joueur_1["poule"]) == int(joueur_2["poule"])

    def est_compatible(self, placement):
        candidats_1, candidats_2 = self._candidats(placement)
        if not candidats_1 or not candidats_2:
            return True
        return not any(self._rencontre_interdite(a, b) for a in candidats_1 for b in candidats_2)

    def est_respectee(self, placement):
        candidats_1, candidats_2 = self._candidats(placement)
        return bool(candidats_1 and candidats_2) and self.est_compatible(placement)

    def description(self):
        return "Deux joueurs de la même poule ne doivent pas se rencontrer au match {}".format(
            self.match.numero
        )


class RangsMemePouleInterdits(MemePouleInterdite):
    def __init__(self, match, rang_a, rang_b):
        super().__init__(match)
        self.rangs_interdits = sorted([int(rang_a), int(rang_b)])

    def _rencontre_interdite(self, joueur_1, joueur_2):
        meme_poule = int(joueur_1["poule"]) == int(joueur_2["poule"])
        rangs = sorted([int(joueur_1["rang_poule"]), int(joueur_2["rang_poule"])])
        return meme_poule and rangs == self.rangs_interdits

    def description(self):
        return "Les rangs {} et {} d'une même poule ne doivent pas se rencontrer au match {}".format(
            self.rangs_interdits[0], self.rangs_interdits[1], self.match.numero
        )
