"""Disposition commune des tableaux développés dans l'interface et Excel."""

import math


def definitions_matchs_visualisation(matchs):
    """Convertit les objets Match en définitions légères utilisables par le moteur."""
    resultat = []
    valeurs = matchs.values() if hasattr(matchs, "values") else matchs
    for match in valeurs:
        participants = []
        for participant in (match.participant_1, match.participant_2):
            if hasattr(participant, "position"):
                participants.append({"type": "position", "numero": int(participant.position)})
            else:
                participants.append({
                    "type": str(participant.resultat),
                    "match": int(participant.match.numero),
                })
        resultat.append({
            "numero": int(match.numero),
            "niveau": str(match.niveau or ""),
            "places": list(match.places or ()),
            "participant_1": participants[0],
            "participant_2": participants[1],
        })
    return sorted(resultat, key=lambda match: match["numero"])


def bloc_match_visualisation(match, taille_tableau):
    """Retourne la moitié, la bande verticale et sa plage de places."""
    places = [int(place) for place in match.get("places", [])]
    if match.get("niveau") == "barrage_2_3" or not places:
        return "centre", 0, (1, taille_tableau)
    milieu = taille_tableau // 2
    gauche = min(places) > milieu
    minimum_relatif = min(places) - (milieu if gauche else 0)
    if minimum_relatif <= 1:
        ordre = 0
        debut_relatif, fin_relatif = 1, milieu
    else:
        ordre = int(math.floor(math.log2(minimum_relatif - 1)))
        debut_relatif = 2 ** ordre + 1
        fin_relatif = min(2 ** (ordre + 1), milieu)
    decalage = milieu if gauche else 0
    return (
        "gauche" if gauche else "droite",
        ordre,
        (debut_relatif + decalage, fin_relatif + decalage),
    )


def calculer_disposition_non_compacte(
    matchs, taille_tableau, origine_x, pas_colonne, largeur_match,
    debut_y, espace_match, espace_bandes, hauteur_minimale=90
):
    """Dispose deux séries de tableaux en miroir, empilées par classement."""
    par_numero = {int(match["numero"]): match for match in matchs}
    groupes = {}
    barrages = []
    for match in matchs:
        cote, ordre, plage = bloc_match_visualisation(match, taille_tableau)
        if cote == "centre":
            barrages.append(match)
        else:
            groupes.setdefault((cote, ordre, plage), []).append(match)

    ordres = sorted({cle[1] for cle in groupes} | ({0} if barrages else set()))
    coordonnees = {}
    bandes = []
    y_courant = debut_y

    def dependances_internes(match, numeros_groupe):
        resultat = []
        for cle in ("participant_1", "participant_2"):
            reference = match.get(cle, {})
            if reference.get("type") in ("vainqueur", "perdant"):
                numero = int(reference.get("match", 0))
                if numero in numeros_groupe:
                    resultat.append(numero)
        return resultat

    for ordre in ordres:
        groupes_bande = [
            (cle, valeur) for cle, valeur in groupes.items() if cle[1] == ordre
        ]
        informations = []
        maximum_premier_tour = len(barrages) if ordre == 0 else 0
        for cle, matchs_groupe in groupes_bande:
            numeros = {int(match["numero"]) for match in matchs_groupe}
            etapes = {}

            def etape(numero):
                if numero in etapes:
                    return etapes[numero]
                parents = dependances_internes(par_numero[numero], numeros)
                etapes[numero] = 0 if not parents else 1 + max(etape(p) for p in parents)
                return etapes[numero]

            for numero in numeros:
                etape(numero)
            premier_tour = sorted(numero for numero, valeur in etapes.items() if valeur == 0)
            maximum_premier_tour = max(maximum_premier_tour, len(premier_tour))
            informations.append((cle, numeros, etapes, premier_tour))

        nombre_lignes = max(1, maximum_premier_tour)
        hauteur_bande = max(hauteur_minimale, nombre_lignes * espace_match)
        centre_lignes = [
            y_courant + (index + 0.5) * hauteur_bande / nombre_lignes
            for index in range(nombre_lignes)
        ]
        if ordre == 0 and barrages:
            for index, match in enumerate(sorted(barrages, key=lambda m: int(m["numero"]))):
                ligne = int(index * nombre_lignes / max(1, len(barrages)))
                coordonnees[int(match["numero"])] = (
                    origine_x, centre_lignes[min(ligne, nombre_lignes - 1)]
                )

        plages = {}
        for cle, numeros, etapes, premier_tour in informations:
            cote, _ordre, plage = cle
            plages[cote] = plage
            for index, numero in enumerate(premier_tour):
                ligne = int(index * nombre_lignes / max(1, len(premier_tour)))
                direction = -1 if cote == "gauche" else 1
                x = origine_x + direction * pas_colonne
                if direction < 0:
                    x -= largeur_match
                coordonnees[numero] = (x, centre_lignes[min(ligne, nombre_lignes - 1)])
            for valeur in range(1, max(etapes.values(), default=0) + 1):
                candidats = []
                for numero in sorted(n for n, e in etapes.items() if e == valeur):
                    parents = dependances_internes(par_numero[numero], numeros)
                    souhaite_y = sum(coordonnees[parent][1] for parent in parents) / len(parents)
                    candidats.append((souhaite_y, numero))
                candidats.sort()
                ordonnees = []
                for souhaite_y, _numero in candidats:
                    ordonnees.append(
                        max(souhaite_y, ordonnees[-1] + espace_match if ordonnees else souhaite_y)
                    )
                if ordonnees:
                    decalage = (
                        sum(souhaite for souhaite, _numero in candidats) / len(candidats)
                        - sum(ordonnees) / len(ordonnees)
                    )
                    ordonnees = [y + decalage for y in ordonnees]
                for (_souhaite_y, numero), y in zip(candidats, ordonnees):
                    direction = -1 if cote == "gauche" else 1
                    x = origine_x + direction * (valeur + 1) * pas_colonne
                    if direction < 0:
                        x -= largeur_match
                    coordonnees[numero] = (x, y)

        bandes.append({
            "ordre": ordre,
            "haut": y_courant,
            "bas": y_courant + hauteur_bande,
            "plages": plages,
        })
        y_courant += hauteur_bande + espace_bandes
    return coordonnees, bandes, y_courant


def sorties_classement(match):
    """Retourne les places gagnant/perdant d'un dernier match de classement."""
    places = sorted(int(place) for place in match.get("places", []))
    if len(places) == 2 and places[1] == places[0] + 1:
        return places[0], places[1]
    return None
