"""Contraintes portant directement sur les positions du tableau."""

from .base import Contrainte
from ..modele import identite_joueur
from ..utilitaires import normaliser_club


class PositionImposee(Contrainte):
    def __init__(self, numero_poule, rang_poule, position):
        self.joueur_attendu = (numero_poule, rang_poule)
        self.position = position

    def est_compatible(self, placement):
        index_impose = self.position - 1
        joueur = placement[index_impose]
        if joueur is None:
            return not any(
                index != index_impose and identite_joueur(autre) == self.joueur_attendu
                for index, autre in enumerate(placement)
            )
        return identite_joueur(joueur) == self.joueur_attendu

    def est_respectee(self, placement):
        return identite_joueur(placement[self.position - 1]) == self.joueur_attendu

    def description(self):
        return "Le joueur {} doit être en position {}".format(
            self.joueur_attendu, self.position
        )


class ClubsDifferents(Contrainte):
    def __init__(self, position_1, position_2):
        self.position_1, self.position_2 = position_1, position_2

    def _clubs(self, placement):
        joueurs = placement[self.position_1 - 1], placement[self.position_2 - 1]
        if any(joueur is None for joueur in joueurs):
            return None
        return tuple(normaliser_club(joueur.get("club")) for joueur in joueurs)

    def est_compatible(self, placement):
        clubs = self._clubs(placement)
        return clubs is None or not all(clubs) or clubs[0] != clubs[1]

    def est_respectee(self, placement):
        clubs = self._clubs(placement)
        return clubs is not None and all(clubs) and clubs[0] != clubs[1]

    def description(self):
        return "Les positions {} et {} doivent avoir des clubs différents".format(
            self.position_1, self.position_2
        )


class JoueursDansPositions(Contrainte):
    def __init__(self, joueurs_attendus, positions):
        self.joueurs_attendus = set(joueurs_attendus)
        self.positions = set(positions)

    def est_compatible(self, placement):
        joueurs_presents = {
            identite_joueur(placement[p - 1]) for p in self.positions
            if placement[p - 1] is not None
        }
        for position, joueur in enumerate(placement, start=1):
            if (joueur is not None and identite_joueur(joueur) in self.joueurs_attendus
                    and position not in self.positions):
                return False
        positions_libres = sum(placement[p - 1] is None for p in self.positions)
        return len(self.joueurs_attendus - joueurs_presents) <= positions_libres

    def est_respectee(self, placement):
        presents = {
            identite_joueur(placement[p - 1]) for p in self.positions
            if placement[p - 1] is not None
        }
        return self.joueurs_attendus.issubset(presents)

    def description(self):
        return "{} doivent occuper les positions {}".format(
            sorted(self.joueurs_attendus), sorted(self.positions)
        )
