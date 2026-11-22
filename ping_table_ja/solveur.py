"""Algorithme de résolution par retour arrière."""


def resoudre(joueurs, contraintes, nombre_positions=32):
    placement = [None] * nombre_positions

    def compatibles():
        return all(c.est_compatible(placement) for c in contraintes)

    def candidats(position, disponibles):
        resultat = []
        for joueur in disponibles:
            placement[position] = joueur
            if compatibles():
                resultat.append(joueur)
            placement[position] = None
        return resultat

    def rechercher(disponibles):
        if not disponibles:
            return list(placement) if all(c.est_respectee(placement) for c in contraintes) else None

        meilleure_position, meilleurs = None, None
        for position in range(nombre_positions):
            if placement[position] is not None:
                continue
            possibles = candidats(position, disponibles)
            if not possibles:
                return None
            if meilleurs is None or len(possibles) < len(meilleurs):
                meilleure_position, meilleurs = position, possibles
            if len(meilleurs) == 1:
                break

        for joueur in meilleurs:
            placement[meilleure_position] = joueur
            solution = rechercher([j for j in disponibles if j is not joueur])
            if solution is not None:
                return solution
            placement[meilleure_position] = None
        return None

    return rechercher(list(joueurs))
