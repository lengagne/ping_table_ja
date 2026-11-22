"""Définition du tableau à 32 joueurs et de ses contraintes."""

from .contraintes import (
    ClubsDifferentsParticipants, JoueursDansPositions, MemePouleInterdite,
    PositionImposee, RangsMemePouleInterdits,
)
from .modele import Match, PositionTableau


def creer_matchs():
    """Construit le graphe des matchs et les indexe par numéro."""
    matchs = {}

    for numero, positions in zip(range(33, 41), ((3, 4), (5, 6), (11, 12), (13, 14),
                                                   (19, 20), (21, 22), (27, 28), (29, 30))):
        matchs[numero] = Match(numero, PositionTableau(positions[0]), PositionTableau(positions[1]))

    for numero, position, precedent in zip(range(41, 49), (1, 8, 9, 16, 17, 24, 25, 32), range(33, 41)):
        matchs[numero] = Match(numero, PositionTableau(position), matchs[precedent].vainqueur)

    for numero, (a, b) in zip(range(49, 53), ((41, 42), (43, 44), (45, 46), (47, 48))):
        matchs[numero] = Match(numero, matchs[a].vainqueur, matchs[b].vainqueur)
    matchs[53] = Match(53, matchs[49].vainqueur, matchs[50].vainqueur)
    matchs[54] = Match(54, matchs[51].vainqueur, matchs[52].vainqueur)

    for numero, position, precedent in zip(range(55, 63), (2, 7, 10, 15, 18, 23, 26, 31), range(33, 41)):
        matchs[numero] = Match(numero, PositionTableau(position), matchs[precedent].perdant)

    for numero, (a, b) in zip(range(63, 67), ((55, 56), (57, 58), (59, 60), (61, 62))):
        matchs[numero] = Match(numero, matchs[a].vainqueur, matchs[b].vainqueur)
    matchs[67] = Match(67, matchs[63].vainqueur, matchs[64].vainqueur)
    matchs[68] = Match(68, matchs[65].vainqueur, matchs[66].vainqueur)
    return matchs


def creer_contraintes(matchs):
    contraintes = [
        PositionImposee(1, 1, 1),
        PositionImposee(2, 1, 32),
        JoueursDansPositions([(3, 1), (4, 1)], [16, 17]),
        JoueursDansPositions([(p, 1) for p in range(5, 9)], [8, 9, 24, 25]),
        JoueursDansPositions([(1, 2)], [20, 21, 28, 29]),
        JoueursDansPositions([(2, 2)], [4, 5, 12, 13]),
        JoueursDansPositions([(p, 2) for p in range(3, 9)], [4, 5, 12, 13, 20, 21, 28, 29]),
        JoueursDansPositions([(1, 3)], [19, 22, 27, 30]),
        JoueursDansPositions([(2, 3)], [3, 6, 11, 14]),
        JoueursDansPositions([(p, 3) for p in range(3, 9)], [3, 6, 11, 14, 19, 22, 27, 30]),
        JoueursDansPositions([(1, 4)], [2, 7, 10, 15]),
        JoueursDansPositions([(2, 4)], [18, 23, 26, 31]),
        JoueursDansPositions([(p, 4) for p in range(3, 9)], [2, 7, 10, 15, 18, 23, 26, 31]),
    ]

    for numero in list(range(33, 49)) + list(range(55, 63)):
        match = matchs[numero]
        contraintes.extend([
            ClubsDifferentsParticipants(match.participant_1, match.participant_2),
            MemePouleInterdite(match),
        ])
    contraintes.extend(MemePouleInterdite(matchs[n]) for n in list(range(49, 53)) + list(range(63, 67)))
    for numero in (53, 54):
        contraintes.extend([
            RangsMemePouleInterdits(matchs[numero], 1, 2),
            RangsMemePouleInterdits(matchs[numero], 1, 3),
        ])
    for numero in (67, 68):
        contraintes.extend([
            RangsMemePouleInterdits(matchs[numero], 4, 2),
            RangsMemePouleInterdits(matchs[numero], 4, 3),
        ])
    return contraintes
