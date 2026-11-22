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


def resoudre_toutes(joueurs, contraintes, nombre_positions=32):
    """Retourne toutes les solutions qui respectent les contraintes."""
    solutions, _ = resoudre_plusieurs(
        joueurs,
        contraintes,
        nombre_positions=nombre_positions,
    )
    return solutions


def resoudre_plusieurs(
    joueurs,
    contraintes,
    nombre_positions=32,
    limite=None,
    notifier=None,
    arreter=None,
):
    """Énumère les solutions, avec limite, progression et arrêt facultatifs.

    Retourne ``(solutions, recherche_terminee)``. Le booléen vaut ``False``
    lorsque la limite a été atteinte ou que l'utilisateur a demandé l'arrêt.
    """
    placement = [None] * nombre_positions
    solutions = []
    recherche_interrompue = False

    def doit_arreter():
        nonlocal recherche_interrompue
        limite_atteinte = limite is not None and len(solutions) >= limite
        arret_demande = arreter is not None and arreter()
        if limite_atteinte or arret_demande:
            recherche_interrompue = True
            return True
        return False

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
        if doit_arreter():
            return
        if not disponibles:
            if all(c.est_respectee(placement) for c in contraintes):
                solutions.append(list(placement))
                if notifier is not None:
                    notifier(len(solutions))
            return

        meilleure_position, meilleurs = None, None
        for position in range(nombre_positions):
            if placement[position] is not None:
                continue
            possibles = candidats(position, disponibles)
            if not possibles:
                return
            if meilleurs is None or len(possibles) < len(meilleurs):
                meilleure_position, meilleurs = position, possibles
            if len(meilleurs) == 1:
                break

        for joueur in meilleurs:
            if doit_arreter():
                return
            placement[meilleure_position] = joueur
            rechercher([autre for autre in disponibles if autre is not joueur])
            placement[meilleure_position] = None

    rechercher(list(joueurs))
    return solutions, not recherche_interrompue
