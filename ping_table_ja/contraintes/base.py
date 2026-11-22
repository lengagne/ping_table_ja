"""Classe abstraite et fonctions communes aux contraintes."""

from abc import ABC, abstractmethod


class Contrainte(ABC):
    @abstractmethod
    def est_compatible(self, placement):
        """Vérifie une solution partiellement remplie."""

    @abstractmethod
    def est_respectee(self, placement):
        """Vérifie une solution finale."""

    @abstractmethod
    def description(self):
        """Explique la contrainte."""


def verifier_contraintes(placement, contraintes):
    resultat_global = True
    for contrainte in contraintes:
        valide = contrainte.est_respectee(placement)
        print("{} : {}".format(
            contrainte.description(), "OK" if valide else "NON RESPECTÉE"
        ))
        resultat_global = resultat_global and valide
    return resultat_global
