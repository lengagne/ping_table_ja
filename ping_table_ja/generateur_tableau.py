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


def positions_poules_tableau(taille_tableau):
    """Retourne les positions de poule selon la numérotation du tableau PDF.

    Par bloc de deux poules, les positions sont disposées de haut en bas ainsi :
    1er A, 4e A, 2e/3e A, 2e/3e B, 4e B, 1er B. Cette disposition
    reste identique, que les barrages 1-4 soient joués ou non.
    """
    taille_tableau = int(taille_tableau)
    if taille_tableau < 8 or taille_tableau % 8:
        raise ValueError("La numérotation standard nécessite un multiple de 8")
    poules = []
    for debut in range(1, taille_tableau + 1, 8):
        poules.extend([
            {
                "rang_1": debut,
                "rang_4": debut + 1,
                "rangs_2_3": (debut + 2, debut + 3),
            },
            {
                "rang_1": debut + 7,
                "rang_4": debut + 6,
                "rangs_2_3": (debut + 4, debut + 5),
            },
        ])
    return poules


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

    def imposer_rangs_matchs(numeros_matchs, rang_1, rang_2):
        contraintes.append({
            "type": "rangs_match",
            "cible": {"type": "matchs", "numeros": list(numeros_matchs)},
            "rangs": [rang_1, rang_2],
        })

    def imposer_rangs_participants_niveau(niveau, rangs_1, rangs_2):
        contraintes.append({
            "type": "rangs_participants",
            "cible": {"type": "niveau", "niveau": niveau},
            "participant_1": list(rangs_1),
            "participant_2": list(rangs_2),
        })

    def position(numero):
        return {"type": "position", "numero": numero}

    positions_poules = positions_poules_tableau(taille_tableau)

    if barrages_1_contre_4:
        # Les positions conservent la disposition du PDF. Dans une paire de
        # poules, la seconde est donc dessinée en miroir.
        premiers_matchs = []
        matchs_1_4 = []
        matchs_2_3 = []
        niveau = nom_niveau(taille_tableau)
        for index in range(0, len(positions_poules), 2):
            paire = positions_poules[index:index + 2]
            definitions = [
                ("1_4", paire[0]["rang_1"], paire[0]["rang_4"]),
                ("2_3", *paire[0]["rangs_2_3"]),
                ("2_3", *paire[1]["rangs_2_3"]),
                ("1_4", paire[1]["rang_1"], paire[1]["rang_4"]),
            ]
            for type_barrage, numero_1, numero_2 in definitions:
                numero_match = ajouter_match(
                    position(numero_1), position(numero_2), niveau, (1, taille_tableau)
                )
                premiers_matchs.append(numero_match)
                (matchs_1_4 if type_barrage == "1_4" else matchs_2_3).append(
                    numero_match
                )
        imposer_rangs_matchs(matchs_1_4, 1, 4)
        imposer_rangs_matchs(matchs_2_3, 2, 3)
        continuer_apres_premier_tour(
            premiers_matchs, 1, bool(classement_integral)
        )
    else:
        # Les 2es et 3es jouent un barrage. Le gagnant rejoint un 1er dans
        # le tableau supérieur et le perdant rejoint un 4e dans le tableau inférieur.
        taille_sous_tableau = taille_tableau // 2
        matchs_superieurs = []
        matchs_inferieurs = []
        niveau_superieur = nom_niveau(taille_sous_tableau)
        niveau_inferieur = "places_{}_{}".format(
            taille_sous_tableau + 1, taille_tableau
        )
        for positions_poule in positions_poules:
            numero_2, numero_3 = positions_poule["rangs_2_3"]
            barrage = ajouter_match(
                position(numero_2),
                position(numero_3),
                "barrage_2_3",
                (1, taille_tableau),
            )

            match_superieur = ajouter_match(
                position(positions_poule["rang_1"]),
                {"type": "vainqueur", "match": barrage},
                niveau_superieur,
                (1, taille_sous_tableau),
            )
            matchs_superieurs.append(match_superieur)

            match_inferieur = ajouter_match(
                {"type": "perdant", "match": barrage},
                position(positions_poule["rang_4"]),
                niveau_inferieur,
                (taille_sous_tableau + 1, taille_tableau),
            )
            matchs_inferieurs.append(match_inferieur)

        contraintes.extend([
            {
                "type": "rangs_match",
                "cible": {"type": "niveau", "niveau": "barrage_2_3"},
                "rangs": [2, 3],
            },
        ])
        imposer_rangs_participants_niveau(niveau_superieur, [1], [2, 3])
        imposer_rangs_participants_niveau(niveau_inferieur, [2, 3], [4])

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
