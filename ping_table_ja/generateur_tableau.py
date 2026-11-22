"""Génération de graphes de matchs standards et personnalisables."""

import math


TAILLES_STANDARDS = (8, 16, 32, 64, 128, 256)


def _est_puissance_de_deux(nombre):
    return nombre >= 2 and nombre & (nombre - 1) == 0


def nom_niveau(nombre_participants):
    """Retourne le nom du tour principal joué par ce nombre de participants."""
    if nombre_participants == 2:
        return "finale"
    if nombre_participants == 4:
        return "1/2"
    return "1/{}".format(nombre_participants // 2)


def generer_configuration_standard(
    taille_tableau,
    classement_integral=True,
    barrages_1_contre_4=False,
    nom=None,
):
    """Génère un JSON v2 dont tous les matchs restent ensuite modifiables.

    En classement intégral, les vainqueurs et les perdants de chaque groupe
    continuent à jouer jusqu'à obtenir une place précise pour chaque joueur.
    Sans classement intégral, seul le chemin menant à la finale est généré.
    """
    taille_tableau = int(taille_tableau)
    if not _est_puissance_de_deux(taille_tableau):
        raise ValueError("La taille d'un tableau standard doit être une puissance de deux")

    matchs = []
    prochain_numero = [1]

    def ajouter_match(participant_1, participant_2, niveau, places):
        numero = prochain_numero[0]
        prochain_numero[0] += 1
        matchs.append({
            "numero": numero,
            "niveau": niveau,
            "places": list(places),
            "participant_1": participant_1,
            "participant_2": participant_2,
        })
        return numero

    def classer(participants, premiere_place, integral):
        nombre = len(participants)
        if nombre == 1:
            return
        derniere_place = premiere_place + nombre - 1
        niveau = (
            nom_niveau(nombre)
            if premiere_place == 1
            else "places_{}_{}".format(premiere_place, derniere_place)
        )
        numeros = []
        for index in range(0, nombre, 2):
            numeros.append(ajouter_match(
                participants[index],
                participants[index + 1],
                niveau,
                (premiere_place, derniere_place),
            ))
        vainqueurs = [{"type": "vainqueur", "match": numero} for numero in numeros]
        classer(vainqueurs, premiere_place, integral)
        if integral:
            perdants = [{"type": "perdant", "match": numero} for numero in numeros]
            classer(perdants, premiere_place + nombre // 2, True)

    positions = [
        {"type": "position", "numero": position}
        for position in range(1, taille_tableau + 1)
    ]
    classer(positions, 1, bool(classement_integral))
    return {
        "version": 2,
        "nom": nom or "Tableau standard {} joueurs".format(taille_tableau),
        "format": "standard",
        "taille_tableau": taille_tableau,
        "classement_integral": bool(classement_integral),
        "barrages_1_contre_4": bool(barrages_1_contre_4),
        "onglet_excel": "classement poules",
        "matchs": matchs,
        "contraintes": [],
    }


def niveaux_principaux(taille_tableau):
    """Liste ordonnée des niveaux utilisables par l'interface de contraintes."""
    taille_tableau = int(taille_tableau)
    if not _est_puissance_de_deux(taille_tableau):
        return []
    return [
        nom_niveau(2 ** exposant)
        for exposant in range(int(math.log2(taille_tableau)), 0, -1)
    ]
