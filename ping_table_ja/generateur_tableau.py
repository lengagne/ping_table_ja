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
    contraintes = []
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

    def continuer_apres_premier_tour(numeros, premiere_place, integral):
        """Poursuit un tableau dont le premier tour est déjà créé."""
        vainqueurs = [{"type": "vainqueur", "match": numero} for numero in numeros]
        classer(vainqueurs, premiere_place, integral)
        if integral:
            perdants = [{"type": "perdant", "match": numero} for numero in numeros]
            classer(perdants, premiere_place + len(numeros), True)

    def imposer_rangs_match(numero_match, rang_1, rang_2):
        contraintes.append({
            "type": "rangs_match",
            "cible": {"type": "match", "numero": numero_match},
            "rangs": [rang_1, rang_2],
        })

    def imposer_rangs_participants(numero_match, rangs_1, rangs_2):
        contraintes.append({
            "type": "rangs_participants",
            "cible": {"type": "match", "numero": numero_match},
            "participant_1": list(rangs_1),
            "participant_2": list(rangs_2),
        })

    def position(numero):
        return {"type": "position", "numero": numero}

    if barrages_1_contre_4:
        # Chaque bloc de quatre positions reçoit un barrage 1-4 et un barrage 2-3.
        premiers_matchs = []
        niveau = nom_niveau(taille_tableau)
        for debut in range(1, taille_tableau + 1, 4):
            match_1_4 = ajouter_match(
                position(debut), position(debut + 1), niveau, (1, taille_tableau)
            )
            match_2_3 = ajouter_match(
                position(debut + 2), position(debut + 3), niveau, (1, taille_tableau)
            )
            imposer_rangs_match(match_1_4, 1, 4)
            imposer_rangs_match(match_2_3, 2, 3)
            premiers_matchs.extend((match_1_4, match_2_3))
        continuer_apres_premier_tour(
            premiers_matchs, 1, bool(classement_integral)
        )
    else:
        # Les 2es et 3es jouent un barrage. Le gagnant rejoint un 1er dans
        # le tableau supérieur et le perdant rejoint un 4e dans le tableau inférieur.
        nombre_poules = taille_tableau // 4
        taille_sous_tableau = taille_tableau // 2
        matchs_superieurs = []
        matchs_inferieurs = []
        for index_poule in range(nombre_poules):
            debut = index_poule * 4 + 1
            barrage = ajouter_match(
                position(debut + 1),
                position(debut + 2),
                "barrage_2_3",
                (1, taille_tableau),
            )
            imposer_rangs_match(barrage, 2, 3)

            match_superieur = ajouter_match(
                position(debut),
                {"type": "vainqueur", "match": barrage},
                nom_niveau(taille_sous_tableau),
                (1, taille_sous_tableau),
            )
            imposer_rangs_participants(match_superieur, [1], [2, 3])
            matchs_superieurs.append(match_superieur)

            match_inferieur = ajouter_match(
                {"type": "perdant", "match": barrage},
                position(debut + 3),
                "places_{}_{}".format(taille_sous_tableau + 1, taille_tableau),
                (taille_sous_tableau + 1, taille_tableau),
            )
            imposer_rangs_participants(match_inferieur, [2, 3], [4])
            matchs_inferieurs.append(match_inferieur)

        continuer_apres_premier_tour(
            matchs_superieurs, 1, bool(classement_integral)
        )
        continuer_apres_premier_tour(
            matchs_inferieurs,
            taille_sous_tableau + 1,
            bool(classement_integral),
        )
    return {
        "version": 2,
        "nom": nom or "Tableau standard {} joueurs".format(taille_tableau),
        "format": "standard",
        "taille_tableau": taille_tableau,
        "classement_integral": bool(classement_integral),
        "barrages_1_contre_4": bool(barrages_1_contre_4),
        "aucune_contrainte": False,
        "onglet_excel": "classement poules",
        "matchs": matchs,
        "contraintes": contraintes,
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
