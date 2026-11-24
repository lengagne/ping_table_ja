"""Algorithme de résolution par retour arrière."""

import random

from .evaluation_contraintes import (
    compiler_plan_contraintes,
    dedupliquer_contraintes,
)
from .modele import Placement


def resoudre(joueurs, contraintes, nombre_positions=32, plan_contraintes=None):
    contraintes = dedupliquer_contraintes(contraintes)
    plan = plan_contraintes or compiler_plan_contraintes(
        contraintes, nombre_positions
    )
    if plan.nombre_positions != nombre_positions:
        raise ValueError("Le plan compilé ne correspond pas au nombre de positions.")
    evaluateur = plan.creer_evaluateur(joueurs)
    placement = Placement([None] * nombre_positions)

    def compatibles(position):
        return evaluateur.est_compatible(position, placement)

    def candidats(position, disponibles):
        resultat = []
        for joueur in disponibles:
            placement[position] = joueur
            if compatibles(position):
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
    melanger_candidats=False,
    graine=None,
    notifier_statistiques=None,
    plan_contraintes=None,
):
    """Énumère les solutions, avec limite, progression et arrêt facultatifs.

    Retourne ``(solutions, recherche_terminee)``. Le booléen vaut ``False``
    lorsque la limite a été atteinte ou que l'utilisateur a demandé l'arrêt.
    ``melanger_candidats`` fait varier la partie de l'arbre visitée en premier,
    ce qui convient à un aperçu rapide limité. ``notifier_statistiques`` reçoit
    périodiquement les compteurs de recherche sans modifier le résultat.
    """
    contraintes = dedupliquer_contraintes(contraintes)
    plan = plan_contraintes or compiler_plan_contraintes(
        contraintes, nombre_positions
    )
    if plan.nombre_positions != nombre_positions:
        raise ValueError("Le plan compilé ne correspond pas au nombre de positions.")
    evaluateur = plan.creer_evaluateur(joueurs)
    placement = Placement([None] * nombre_positions)
    solutions = []
    recherche_interrompue = False
    generateur_aleatoire = random.Random(graine) if melanger_candidats else None
    statistiques = {
        "noeuds_explores": 0,
        "candidats_testes": 0,
        "retours_arriere": 0,
        "profondeur": 0,
        "profondeur_max": 0,
        "solutions": 0,
        "contraintes_effectives": plan.contraintes_effectives,
        "contraintes_regroupees": plan.contraintes_regroupees,
    }

    def publier_statistiques(force=False):
        if notifier_statistiques is None:
            return
        if force or statistiques["noeuds_explores"] % 250 == 0:
            notifier_statistiques(dict(statistiques))

    def doit_arreter():
        nonlocal recherche_interrompue
        limite_atteinte = limite is not None and len(solutions) >= limite
        arret_demande = arreter is not None and arreter()
        if limite_atteinte or arret_demande:
            recherche_interrompue = True
            return True
        return False

    def compatibles(position):
        return evaluateur.est_compatible(position, placement)

    def candidats(position, disponibles):
        resultat = []
        for joueur in disponibles:
            statistiques["candidats_testes"] += 1
            placement[position] = joueur
            if compatibles(position):
                resultat.append(joueur)
            placement[position] = None
        return resultat

    def rechercher(disponibles):
        statistiques["noeuds_explores"] += 1
        statistiques["profondeur"] = nombre_positions - len(disponibles)
        statistiques["profondeur_max"] = max(
            statistiques["profondeur_max"], statistiques["profondeur"]
        )
        publier_statistiques()
        if doit_arreter():
            return
        if not disponibles:
            if all(c.est_respectee(placement) for c in contraintes):
                solutions.append(list(placement))
                statistiques["solutions"] = len(solutions)
                if notifier is not None:
                    notifier(len(solutions))
                publier_statistiques(force=True)
            return

        meilleure_position, meilleurs = None, None
        for position in range(nombre_positions):
            if placement[position] is not None:
                continue
            possibles = candidats(position, disponibles)
            if not possibles:
                statistiques["retours_arriere"] += 1
                return
            if meilleurs is None or len(possibles) < len(meilleurs):
                meilleure_position, meilleurs = position, possibles
            if len(meilleurs) == 1:
                break

        if generateur_aleatoire is not None and len(meilleurs) > 1:
            generateur_aleatoire.shuffle(meilleurs)
        for joueur in meilleurs:
            if doit_arreter():
                return
            placement[meilleure_position] = joueur
            rechercher([autre for autre in disponibles if autre is not joueur])
            placement[meilleure_position] = None
            statistiques["retours_arriere"] += 1

    rechercher(list(joueurs))
    statistiques["profondeur"] = 0
    statistiques["solutions"] = len(solutions)
    publier_statistiques(force=True)
    return solutions, not recherche_interrompue
