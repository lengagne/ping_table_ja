"""Modèle métier : joueurs, positions et matchs."""


def identite_joueur(joueur):
    if joueur is None:
        return None
    return joueur["poule"], joueur["rang_poule"]


class PositionTableau:
    """Référence à une position du tableau, numérotée à partir de 1."""

    def __init__(self, position):
        self.position = position

    def joueurs_possibles(self, placement):
        joueur = placement[self.position - 1]
        return [] if joueur is None else [joueur]

    def description(self):
        return "position {}".format(self.position)


class ResultatMatch:
    """Référence au vainqueur ou au perdant d'un match."""

    RESULTATS_VALIDES = ("vainqueur", "perdant")

    def __init__(self, match, resultat):
        if resultat not in self.RESULTATS_VALIDES:
            raise ValueError("Résultat inconnu : {}".format(resultat))
        self.match = match
        self.resultat = resultat

    def joueurs_possibles(self, placement):
        joueur_reel = self.match.resultat_reel(self.resultat)
        if joueur_reel is not None:
            return [joueur_reel]
        return self.match.joueurs_possibles(placement)

    def description(self):
        return "{} du match {}".format(self.resultat, self.match.numero)


class Match:
    """Match entre deux positions ou résultats de matchs précédents."""

    def __init__(self, numero, participant_1, participant_2):
        self.numero = numero
        self.participant_1 = participant_1
        self.participant_2 = participant_2
        self._vainqueur_reel = None
        self._perdant_reel = None
        self.vainqueur = ResultatMatch(self, "vainqueur")
        self.perdant = ResultatMatch(self, "perdant")

    def joueurs_possibles(self, placement):
        joueurs = (self.participant_1.joueurs_possibles(placement)
                   + self.participant_2.joueurs_possibles(placement))
        resultat, identites = [], set()
        for joueur in joueurs:
            identite = identite_joueur(joueur)
            if identite not in identites:
                identites.add(identite)
                resultat.append(joueur)
        return resultat

    def definir_resultat(self, vainqueur, perdant):
        self._vainqueur_reel = vainqueur
        self._perdant_reel = perdant

    def resultat_reel(self, resultat):
        return self._vainqueur_reel if resultat == "vainqueur" else self._perdant_reel
