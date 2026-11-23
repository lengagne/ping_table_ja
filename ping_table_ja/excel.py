"""Lecture des poules et écriture de la solution au format Excel."""

import re
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .disposition_tableau import (
    bloc_match_visualisation,
    calculer_disposition_non_compacte,
    definitions_matchs_visualisation,
    sorties_classement,
)
from .utilitaires import nettoyer

REGEX_TITRE = re.compile(r"^\s*CLASSEMENT\s+POULE\s*(\d+)\s*$", re.IGNORECASE)


def lire_classement(fichier_excel, nom_onglet="classement poules"):
    classeur = load_workbook(filename=fichier_excel, data_only=True)
    try:
        if nom_onglet not in classeur.sheetnames:
            raise ValueError(
                "L'onglet {!r} est introuvable. Onglets disponibles : {}".format(
                    nom_onglet, ", ".join(classeur.sheetnames)
                )
            )
        feuille = classeur[nom_onglet]
        titres = []
        for ligne in feuille.iter_rows():
            for cellule in ligne:
                correspondance = REGEX_TITRE.match(nettoyer(cellule.value))
                if correspondance:
                    titres.append({
                        "poule": int(correspondance.group(1)),
                        "ligne": cellule.row,
                        "colonne": cellule.column,
                    })

        classements = {}
        for titre in titres:
            suivants = [
                autre["ligne"] for autre in titres
                if autre["colonne"] == titre["colonne"] and autre["ligne"] > titre["ligne"]
            ]
            derniere_ligne = min(suivants) - 1 if suivants else feuille.max_row
            participants = []
            for numero_ligne in range(titre["ligne"] + 1, derniere_ligne + 1):
                nom = nettoyer(feuille.cell(numero_ligne, titre["colonne"]).value)
                club = nettoyer(feuille.cell(numero_ligne, titre["colonne"] + 1).value)
                if not nom:
                    continue
                if REGEX_TITRE.match(nom):
                    break
                participants.append({
                    "rang": len(participants) + 1,
                    "nom": nom,
                    "club": club,
                    "ligne_excel": numero_ligne,
                })
                if len(participants) == 4:
                    break
            classements[titre["poule"]] = participants
        return dict(sorted(classements.items()))
    finally:
        classeur.close()


def creer_liste_joueurs(classements, nombre_positions=None):
    """Crée les joueurs et complète les poules de trois par un 4e vide.

    Quand ``nombre_positions`` est fourni, chaque poule doit représenter quatre
    places de tableau. Une poule de trois reçoit donc un joueur absent de rang 4.
    """
    joueurs = []
    for numero_poule, classement in classements.items():
        if nombre_positions is not None and len(classement) not in (3, 4):
            raise ValueError(
                "La poule {} contient {} joueur(s) ; 3 ou 4 sont attendus.".format(
                    numero_poule, len(classement)
                )
            )
        joueurs.extend({
            "nom": joueur["nom"],
            "club": joueur["club"],
            "poule": int(numero_poule),
            "rang_poule": int(joueur["rang"]),
        } for joueur in classement)
        if nombre_positions is not None and len(classement) == 3:
            joueurs.append({
                "nom": "",
                "club": "",
                "poule": int(numero_poule),
                "rang_poule": 4,
                "absent": True,
            })
    if nombre_positions is not None and len(joueurs) != int(nombre_positions):
        raise ValueError(
            "Les {} poules représentent {} places ; la configuration en attend {}.".format(
                len(classements), len(joueurs), nombre_positions
            )
        )
    return joueurs


COULEUR_ENTETE = "4472C4"
COULEUR_SELECTION = "FFF2CC"


def _styliser_entetes(feuille, ligne, entetes):
    for colonne, entete in enumerate(entetes, start=1):
        cellule = feuille.cell(row=ligne, column=colonne, value=entete)
        cellule.font = Font(bold=True, color="FFFFFF")
        cellule.fill = PatternFill(fill_type="solid", fgColor=COULEUR_ENTETE)
        cellule.alignment = Alignment(horizontal="center", vertical="center")


def _nom_colonne_poule(index):
    """Retourne A, B, ..., Z, AA... pour identifier visuellement une poule."""
    resultat = ""
    while index:
        index, reste = divmod(index - 1, 26)
        resultat = chr(65 + reste) + resultat
    return resultat


def _libelle_rang(rang):
    return {1: "1ER", 2: "2EME", 3: "3EME", 4: "4EME"}.get(rang, "{}EME".format(rang))


def _positions_par_poule(tirage):
    """Associe chaque couple (poule, rang) à sa place dans le tirage."""
    return {
        (int(joueur["poule"]), int(joueur["rang_poule"])): position
        for position, joueur in enumerate(tirage, start=1)
        if joueur is not None and joueur.get("poule") and joueur.get("rang_poule")
    }


def _creer_onglet_tableau_compact(classeur, solution, matchs):
    """Crée le tableau interactif et propage vainqueurs et perdants par formules."""
    feuille = classeur.create_sheet("Tableau")
    feuille.sheet_view.showGridLines = False
    feuille["A1"] = "Tableau des matchs"
    feuille["A1"].font = Font(size=15, bold=True)
    feuille["A2"] = (
        '=IF(\'Tirage choisi\'!$B$4="VERROUILLÉ",'
        '"Choisissez le vainqueur de chaque match.",'
        '"Verrouillez d’abord le tirage dans l’onglet Tirage choisi.")'
    )
    feuille["A2"].font = Font(italic=True, color="666666")

    profondeurs = {}

    def profondeur(match):
        if match.numero in profondeurs:
            return profondeurs[match.numero]
        precedents = []
        for participant in (match.participant_1, match.participant_2):
            precedent = getattr(participant, "match", None)
            if precedent is not None:
                precedents.append(profondeur(precedent))
        profondeurs[match.numero] = 1 + max(precedents, default=0)
        return profondeurs[match.numero]

    ordre = sorted(matchs.values(), key=lambda match: (profondeur(match), match.numero))
    principaux = [match for match in ordre if min(match.places or (1,)) == 1]
    classements = [match for match in ordre if match not in principaux]
    principal_par_niveau = {}
    classement_par_niveau = {}
    for match in principaux:
        principal_par_niveau.setdefault(profondeurs[match.numero], []).append(match)
    for match in classements:
        classement_par_niveau.setdefault(profondeurs[match.numero], []).append(match)
    maximum_principal = max(
        (len(liste) for liste in principal_par_niveau.values()), default=1
    )
    debut_classements = 7 + maximum_principal * 6 + 3
    lignes_matchs = {}
    for niveau, liste in principal_par_niveau.items():
        for index, match in enumerate(liste):
            lignes_matchs[match.numero] = 5 + index * 6
    for niveau, liste in classement_par_niveau.items():
        for index, match in enumerate(liste):
            lignes_matchs[match.numero] = debut_classements + index * 6

    cellules_resultats = {}

    def texte_position(position):
        joueur = solution[position - 1]
        if joueur is None or joueur.get("absent"):
            return "Position {} — absent".format(position)
        return "{} — Poule {}, rang {}".format(
            joueur.get("nom", ""), joueur.get("poule", ""), joueur.get("rang_poule", "")
        )

    def valeur_participant(participant):
        if hasattr(participant, "position"):
            return texte_position(int(participant.position))
        precedent = getattr(participant, "match", None)
        resultat = getattr(participant, "resultat", "")
        cellule = cellules_resultats[(int(precedent.numero), resultat)]
        return "='Tableau'!{}".format(cellule)

    feuille_listes = classeur.create_sheet("_Listes")
    feuille_listes["A1"], feuille_listes["A2"] = "☐", "☑"
    feuille_listes["B1"] = ""
    feuille_listes.sheet_state = "hidden"
    validation = DataValidation(
        type="list",
        formula1='=IF(\'Tirage choisi\'!$B$4="VERROUILLÉ",\'_Listes\'!$A$1:$A$2,\'_Listes\'!$B$1)',
        allow_blank=True,
    )
    validation.promptTitle = "Choisir le vainqueur"
    validation.prompt = "Après verrouillage du tirage, sélectionnez ☑ pour le vainqueur."
    validation.errorTitle = "Valeur invalide"
    validation.error = "Choisissez uniquement ☐ ou ☑."
    validation.showInputMessage = True
    validation.showErrorMessage = True
    feuille.add_data_validation(validation)

    feuille.cell(debut_classements - 3, 1, "TABLEAUX DE CLASSEMENT").font = Font(
        size=13, bold=True, color="9A3412"
    )
    for niveau in sorted(set(profondeurs.values())):
        colonne = 2 + (niveau - 1) * 6
        for ligne_entete, liste in (
            (3, principal_par_niveau.get(niveau, [])),
            (debut_classements - 1, classement_par_niveau.get(niveau, [])),
        ):
            if not liste:
                continue
            cellule_entete = feuille.cell(
                ligne_entete, colonne, "NIVEAU {}".format(niveau)
            )
            cellule_entete.font = Font(bold=True, color="FFFFFF")
            cellule_entete.fill = PatternFill(fill_type="solid", fgColor=COULEUR_ENTETE)
            feuille.merge_cells(
                start_row=ligne_entete, start_column=colonne,
                end_row=ligne_entete, end_column=colonne + 3,
            )
        for match in [m for m in ordre if profondeurs[m.numero] == niveau]:
            ligne = lignes_matchs[match.numero]
            entete = feuille.cell(
                ligne, colonne, "MATCH {} — {}".format(match.numero, match.niveau or "")
            )
            entete.font = Font(bold=True, color="FFFFFF")
            entete.fill = PatternFill(fill_type="solid", fgColor=COULEUR_ENTETE)
            feuille.merge_cells(
                start_row=ligne, start_column=colonne,
                end_row=ligne, end_column=colonne + 3,
            )
            cellule_p1 = feuille.cell(ligne + 1, colonne, valeur_participant(match.participant_1))
            cellule_p2 = feuille.cell(ligne + 2, colonne, valeur_participant(match.participant_2))
            feuille.merge_cells(
                start_row=ligne + 1, start_column=colonne,
                end_row=ligne + 1, end_column=colonne + 2,
            )
            feuille.merge_cells(
                start_row=ligne + 2, start_column=colonne,
                end_row=ligne + 2, end_column=colonne + 2,
            )
            case_1 = feuille.cell(ligne + 1, colonne + 3, "")
            case_2 = feuille.cell(ligne + 2, colonne + 3, "")
            for case in (case_1, case_2):
                case.fill = PatternFill(fill_type="solid", fgColor=COULEUR_SELECTION)
                case.alignment = Alignment(horizontal="center")
                case.font = Font(size=14, bold=True)
                validation.add(case)
            adresse_p1, adresse_p2 = cellule_p1.coordinate, cellule_p2.coordinate
            adresse_c1, adresse_c2 = case_1.coordinate, case_2.coordinate
            gagnant = feuille.cell(
                ligne + 3,
                colonne + 1,
                '=IF(\'Tirage choisi\'!$B$4<>"VERROUILLÉ","",IF(COUNTIF({0}:{1},"☑")<>1,"",IF({0}="☑",{2},{3})))'.format(
                    adresse_c1, adresse_c2, adresse_p1, adresse_p2
                ),
            )
            perdant = feuille.cell(
                ligne + 4,
                colonne + 1,
                '=IF(\'Tirage choisi\'!$B$4<>"VERROUILLÉ","",IF(COUNTIF({0}:{1},"☑")<>1,"",IF({0}="☑",{3},{2})))'.format(
                    adresse_c1, adresse_c2, adresse_p1, adresse_p2
                ),
            )
            feuille.cell(ligne + 3, colonne, "Vainqueur").font = Font(bold=True)
            feuille.cell(ligne + 4, colonne, "Perdant").font = Font(bold=True)
            cellules_resultats[(match.numero, "vainqueur")] = gagnant.coordinate
            cellules_resultats[(match.numero, "perdant")] = perdant.coordinate
        for decalage in range(4):
            feuille.column_dimensions[get_column_letter(colonne + decalage)].width = (
                19 if decalage < 3 else 7
            )
    feuille.freeze_panes = "B4"
    return feuille


def _creer_onglet_tableau(classeur, solution, matchs):
    """Crée le tableau interactif avec la disposition développée des interfaces."""
    feuille = classeur.create_sheet("Tableau")
    feuille.sheet_view.showGridLines = False
    feuille["A1"] = "Tableau des matchs"
    feuille["A1"].font = Font(size=15, bold=True)
    feuille["A2"] = (
        '=IF(\'Tirage choisi\'!$B$4="VERROUILLÉ",'
        '"Choisissez le vainqueur de chaque match.",'
        '"Verrouillez d’abord le tirage dans l’onglet Tirage choisi.")'
    )
    feuille["A2"].font = Font(italic=True, color="666666")

    definitions = definitions_matchs_visualisation(matchs)
    definitions_par_numero = {match["numero"]: match for match in definitions}
    taille = len(solution)
    profondeurs = {}

    def profondeur(match):
        if match.numero in profondeurs:
            return profondeurs[match.numero]
        precedents = [
            profondeur(participant.match)
            for participant in (match.participant_1, match.participant_2)
            if getattr(participant, "match", None) is not None
        ]
        profondeurs[match.numero] = 1 + max(precedents, default=0)
        return profondeurs[match.numero]

    for match in matchs.values():
        profondeur(match)
    profondeur_max = max(profondeurs.values(), default=1)
    largeur_match, pas_colonne = 4, 7
    origine = 8 + profondeur_max * pas_colonne
    coordonnees, bandes, fin_y = calculer_disposition_non_compacte(
        definitions, taille, origine, pas_colonne, largeur_match,
        8, 7, 8, hauteur_minimale=7,
    )
    coordonnees = {
        numero: (int(round(x)), int(round(y)))
        for numero, (x, y) in coordonnees.items()
    }
    min_colonne = max(1, min(x for x, _y in coordonnees.values()) - 5)
    max_colonne = max(x for x, _y in coordonnees.values()) + largeur_match + 5

    bord_fin = Side(style="thin", color="64748B")
    bord_match = Border(left=bord_fin, right=bord_fin, top=bord_fin, bottom=bord_fin)
    couleur_bande = PatternFill(fill_type="solid", fgColor="EAF3F8")
    for bande in bandes:
        haut, bas = int(round(bande["haut"])), int(round(bande["bas"]))
        for cote, plage in bande["plages"].items():
            colonne = origine + pas_colonne if cote == "droite" else min_colonne
            texte = (
                "TABLEAU PLACES {} À {}".format(*plage)
                if plage[1] - plage[0] > 1
                else "PLACES {}e / {}e".format(*plage)
            )
            feuille.cell(haut - 1, colonne, texte).font = Font(
                bold=True, color="1F4E78"
            )
            feuille.cell(haut - 1, colonne).fill = couleur_bande
            feuille.merge_cells(
                start_row=haut - 1, start_column=colonne,
                end_row=haut - 1, end_column=colonne + 3,
            )
        ligne_separation = bas + 4
        for colonne in range(min_colonne, max_colonne + 1):
            feuille.cell(ligne_separation, colonne).fill = PatternFill(
                fill_type="solid", fgColor="E7EBEF"
            )

    def texte_position(position):
        joueur = solution[position - 1]
        if joueur is None or joueur.get("absent"):
            return "Position {} — absent".format(position)
        return "{} — Poule {}, rang {}".format(
            joueur.get("nom", ""), joueur.get("poule", ""), joueur.get("rang_poule", "")
        )

    feuille_listes = classeur.create_sheet("_Listes")
    feuille_listes["A1"], feuille_listes["A2"] = "☐", "☑"
    feuille_listes["B1"] = ""
    feuille_listes.sheet_state = "hidden"
    validation = DataValidation(
        type="list",
        formula1='=IF(\'Tirage choisi\'!$B$4="VERROUILLÉ",\'_Listes\'!$A$1:$A$2,\'_Listes\'!$B$1)',
        allow_blank=True,
    )
    validation.promptTitle = "Choisir le vainqueur"
    validation.prompt = "Après verrouillage du tirage, sélectionnez ☑ pour le vainqueur."
    validation.errorTitle = "Valeur invalide"
    validation.error = "Choisissez uniquement ☐ ou ☑."
    validation.showInputMessage = True
    validation.showErrorMessage = True
    feuille.add_data_validation(validation)
    cellules_resultats = {}

    def valeur_participant(participant):
        if hasattr(participant, "position"):
            return texte_position(int(participant.position))
        precedent = participant.match
        return "='Tableau'!{}".format(
            cellules_resultats[(int(precedent.numero), participant.resultat)]
        )

    ordre = sorted(matchs.values(), key=lambda match: (profondeurs[match.numero], match.numero))
    for match in ordre:
        colonne, centre = coordonnees[match.numero]
        ligne = centre - 2
        entete = feuille.cell(
            ligne, colonne, "MATCH {} — {}".format(match.numero, match.niveau or "")
        )
        entete.font = Font(bold=True, color="FFFFFF")
        entete.fill = PatternFill(fill_type="solid", fgColor=COULEUR_ENTETE)
        feuille.merge_cells(
            start_row=ligne, start_column=colonne,
            end_row=ligne, end_column=colonne + 3,
        )
        cellule_p1 = feuille.cell(ligne + 1, colonne, valeur_participant(match.participant_1))
        cellule_p2 = feuille.cell(ligne + 2, colonne, valeur_participant(match.participant_2))
        feuille.merge_cells(
            start_row=ligne + 1, start_column=colonne,
            end_row=ligne + 1, end_column=colonne + 2,
        )
        feuille.merge_cells(
            start_row=ligne + 2, start_column=colonne,
            end_row=ligne + 2, end_column=colonne + 2,
        )
        case_1 = feuille.cell(ligne + 1, colonne + 3, "")
        case_2 = feuille.cell(ligne + 2, colonne + 3, "")
        for case in (case_1, case_2):
            case.fill = PatternFill(fill_type="solid", fgColor=COULEUR_SELECTION)
            case.alignment = Alignment(horizontal="center")
            case.font = Font(size=14, bold=True)
            validation.add(case)
        adresse_p1, adresse_p2 = cellule_p1.coordinate, cellule_p2.coordinate
        adresse_c1, adresse_c2 = case_1.coordinate, case_2.coordinate
        gagnant = feuille.cell(
            ligne + 3, colonne + 1,
            '=IF(\'Tirage choisi\'!$B$4<>"VERROUILLÉ","",IF(COUNTIF({0}:{1},"☑")<>1,"",IF({0}="☑",{2},{3})))'.format(
                adresse_c1, adresse_c2, adresse_p1, adresse_p2
            ),
        )
        perdant = feuille.cell(
            ligne + 4, colonne + 1,
            '=IF(\'Tirage choisi\'!$B$4<>"VERROUILLÉ","",IF(COUNTIF({0}:{1},"☑")<>1,"",IF({0}="☑",{3},{2})))'.format(
                adresse_c1, adresse_c2, adresse_p1, adresse_p2
            ),
        )
        feuille.cell(ligne + 3, colonne, "Vainqueur").font = Font(bold=True)
        feuille.cell(ligne + 4, colonne, "Perdant").font = Font(bold=True)
        cellules_resultats[(match.numero, "vainqueur")] = gagnant.coordinate
        cellules_resultats[(match.numero, "perdant")] = perdant.coordinate
        for row in range(ligne, ligne + 5):
            for col in range(colonne, colonne + 4):
                feuille.cell(row, col).border = bord_match

        definition = definitions_par_numero[match.numero]
        classement = sorties_classement(definition)
        if classement:
            cote, _ordre, _plage = bloc_match_visualisation(definition, taille)
            if cote == "gauche":
                colonne_nom, colonne_rang = colonne - 4, colonne - 1
            else:
                colonne_rang, colonne_nom = colonne + 4, colonne + 5
            for rang, adresse, row in (
                (classement[0], gagnant.coordinate, ligne + 1),
                (classement[1], perdant.coordinate, ligne + 2),
            ):
                feuille.cell(row, colonne_rang, "{}{}".format(rang, "er" if rang == 1 else "e")).font = Font(bold=True)
                feuille.cell(row, colonne_nom, "='Tableau'!{}".format(adresse))

    for colonne in range(min_colonne, max_colonne + 1):
        feuille.column_dimensions[get_column_letter(colonne)].width = 13
    feuille.freeze_panes = "A4"
    feuille.sheet_properties.pageSetUpPr.fitToPage = True
    feuille.page_setup.fitToWidth = 1
    feuille.page_setup.fitToHeight = 0
    feuille.print_area = "{}1:{}{}".format(
        get_column_letter(min_colonne), get_column_letter(max_colonne), int(fin_y) + 2
    )
    return feuille


def creer_fichier_solution(
    fichier_sortie,
    solution,
    nom_onglet="Tirage choisi",
    solutions=None,
    recap=None,
    numero_tirage_choisi=1,
    matchs=None,
):
    """Crée un classeur autonome contenant récapitulatif et tirages.

    ``nom_onglet`` est conservé pour compatibilité avec les anciens appels ;
    la feuille de sortie porte désormais toujours le nom ``Tirage choisi``.
    """
    fichier_sortie = Path(fichier_sortie)
    solutions = list(solutions) if solutions is not None else [solution]
    if not solutions:
        raise ValueError("Au moins une solution est nécessaire pour créer le fichier Excel")
    if not 1 <= numero_tirage_choisi <= len(solutions):
        raise ValueError("Le numéro du tirage choisi est hors limites")

    nombre_positions = len(solutions[0])
    if any(len(tirage) != nombre_positions for tirage in solutions):
        raise ValueError("Tous les tirages doivent avoir le même nombre de positions")
    joueurs = [joueur for tirage in solutions for joueur in tirage if joueur is not None]
    poules = sorted({int(joueur["poule"]) for joueur in joueurs if joueur.get("poule")})
    nombre_rangs = max(
        (int(joueur["rang_poule"]) for joueur in joueurs if joueur.get("rang_poule")),
        default=0,
    )
    if not poules or not nombre_rangs:
        raise ValueError("Les joueurs doivent posséder un numéro de poule et un rang")
    hauteur_bloc = nombre_rangs + 4
    if len(solutions) * hauteur_bloc > 1_048_576:
        raise ValueError("Le nombre de tirages dépasse la capacité d'un onglet Excel")

    classeur = Workbook()
    recap = recap or {}

    feuille_recap = classeur.active
    feuille_recap.title = "Récap"
    feuille_recap.sheet_view.showGridLines = False
    feuille_recap["A2"] = "Récapitulatif du calcul"
    feuille_recap["A2"].font = Font(size=15, bold=True, color="1F1F1F")
    informations = [
        ("Fichier de configuration", recap.get("configuration", "")),
        ("Fichier Excel d'entrée", recap.get("excel", "")),
        ("Mode de calcul", recap.get("mode", "")),
        ("Recherche terminée", "Oui" if recap.get("recherche_terminee", True) else "Non"),
        ("Nombre de tirages trouvés", len(solutions)),
        ("Numéro du tirage choisi", "='Tirage choisi'!B3"),
    ]
    for ligne, (libelle, valeur) in enumerate(informations, start=4):
        feuille_recap.cell(ligne, 1, libelle).font = Font(bold=True)
        if isinstance(valeur, str) and valeur.startswith("="):
            feuille_recap.cell(ligne, 2, valeur)
        else:
            feuille_recap.cell(ligne, 2, valeur)
    feuille_recap["A11"] = "Utilisation"
    feuille_recap["A11"].font = Font(bold=True, color="FFFFFF")
    feuille_recap["A11"].fill = PatternFill(fill_type="solid", fgColor=COULEUR_ENTETE)
    feuille_recap["B11"] = (
        "Dans l'onglet Tirage choisi, modifiez la cellule jaune B3 pour afficher un autre tirage."
    )
    feuille_recap.column_dimensions["A"].width = 30
    feuille_recap.column_dimensions["B"].width = 95

    feuille_poules = classeur.create_sheet("Poules")
    feuille_poules.sheet_view.showGridLines = False
    feuille_poules["A1"] = "Joueurs par poule et par rang"
    feuille_poules["A1"].font = Font(size=15, bold=True, color="1F1F1F")
    _styliser_entetes(
        feuille_poules,
        3,
        ["Rang"] + ["Poule {}".format(numero_poule) for numero_poule in poules],
    )
    joueurs_par_poule_et_rang = {
        (int(joueur["poule"]), int(joueur["rang_poule"])): joueur
        for joueur in solutions[0]
        if joueur is not None
    }
    for rang in range(1, nombre_rangs + 1):
        ligne = rang + 3
        cellule_rang = feuille_poules.cell(ligne, 1, _libelle_rang(rang))
        cellule_rang.font = Font(bold=True)
        cellule_rang.alignment = Alignment(horizontal="center")
        for index_poule, numero_poule in enumerate(poules, start=2):
            joueur = joueurs_par_poule_et_rang.get((numero_poule, rang))
            if joueur is None:
                valeur = ""
            else:
                nom = joueur.get("nom", "")
                club = joueur.get("club", "")
                valeur = "{} — {}".format(nom, club) if club else nom
            feuille_poules.cell(ligne, index_poule, valeur)
    feuille_poules.column_dimensions["A"].width = 12
    for colonne in range(2, len(poules) + 2):
        feuille_poules.column_dimensions[
            feuille_poules.cell(1, colonne).column_letter
        ].width = 28
    feuille_poules.freeze_panes = "B4"

    feuille_tirage = classeur.create_sheet("Tirage choisi")
    feuille_tirage.sheet_view.showGridLines = False
    feuille_tirage["A1"] = "Tirage choisi"
    feuille_tirage["A1"].font = Font(size=15, bold=True, color="1F1F1F")
    feuille_tirage["A3"] = "Numéro du tirage"
    feuille_tirage["A3"].font = Font(bold=True)
    feuille_tirage["B3"] = numero_tirage_choisi
    feuille_tirage["B3"].fill = PatternFill(fill_type="solid", fgColor=COULEUR_SELECTION)
    feuille_tirage["B3"].font = Font(bold=True)
    feuille_tirage["B3"].alignment = Alignment(horizontal="center")
    feuille_tirage["C3"] = "sur {} tirage{} disponible{}".format(
        len(solutions),
        "s" if len(solutions) > 1 else "",
        "s" if len(solutions) > 1 else "",
    )
    feuille_tirage["C3"].font = Font(italic=True, color="666666")
    validation = DataValidation(
        type="whole",
        operator="between",
        formula1="1",
        formula2=str(len(solutions)),
        allow_blank=False,
    )
    validation.error = (
        "Le numéro du tirage doit être un nombre entier compris entre 1 et {}."
    ).format(len(solutions))
    validation.errorTitle = "Numéro de tirage invalide"
    validation.prompt = "Saisissez le numéro du tirage à afficher."
    validation.promptTitle = "Choisir un tirage"
    validation.showErrorMessage = True
    validation.showInputMessage = True
    feuille_tirage.add_data_validation(validation)
    validation.add(feuille_tirage["B3"])

    feuille_tirage["A4"] = "Verrouiller le tirage"
    feuille_tirage["A4"].font = Font(bold=True)
    feuille_tirage["B4"] = "NON VERROUILLÉ"
    feuille_tirage["B4"].fill = PatternFill(fill_type="solid", fgColor="F4B183")
    feuille_tirage["B4"].font = Font(bold=True)
    feuille_tirage["B4"].alignment = Alignment(horizontal="center")
    verrouillage = DataValidation(
        type="list",
        formula1='"NON VERROUILLÉ,VERROUILLÉ"',
        allow_blank=False,
    )
    verrouillage.promptTitle = "Verrouiller le tirage"
    verrouillage.prompt = (
        "Choisissez VERROUILLÉ avant de saisir les vainqueurs dans l’onglet Tableau."
    )
    verrouillage.errorTitle = "Choix invalide"
    verrouillage.error = "Choisissez NON VERROUILLÉ ou VERROUILLÉ."
    verrouillage.showInputMessage = True
    verrouillage.showErrorMessage = True
    feuille_tirage.add_data_validation(verrouillage)
    verrouillage.add(feuille_tirage["B4"])

    feuille_tirage["A5"] = '="TIRAGE "&$B$3'
    feuille_tirage["A5"].font = Font(size=14, bold=True)
    feuille_tirage["A6"] = "POULES"
    feuille_tirage["A6"].font = Font(bold=True, color="FFFFFF")
    feuille_tirage["A6"].fill = PatternFill(fill_type="solid", fgColor=COULEUR_ENTETE)
    for index_poule, numero_poule in enumerate(poules, start=1):
        colonne = index_poule + 1
        for ligne, valeur in ((6, numero_poule), (7, _nom_colonne_poule(index_poule))):
            cellule = feuille_tirage.cell(ligne, colonne, valeur)
            cellule.font = Font(bold=True, color="FFFFFF")
            cellule.fill = PatternFill(fill_type="solid", fgColor=COULEUR_ENTETE)
            cellule.alignment = Alignment(horizontal="center")
    feuille_tirage["A7"].fill = PatternFill(fill_type="solid", fgColor=COULEUR_ENTETE)
    derniere_ligne_tous = len(solutions) * hauteur_bloc
    for rang in range(1, nombre_rangs + 1):
        ligne = rang + 7
        cellule_rang = feuille_tirage.cell(ligne, 1, _libelle_rang(rang))
        cellule_rang.font = Font(bold=True)
        for index_poule in range(1, len(poules) + 1):
            cellule = feuille_tirage.cell(
                ligne,
                index_poule + 1,
                "=IFERROR(INDEX('Tous les tirages'!$B$4:${0}${1},(($B$3-1)*{2})+{3},{4}),\"\")".format(
                    feuille_tirage.cell(1, len(poules) + 1).column_letter,
                    derniere_ligne_tous,
                    hauteur_bloc,
                    rang,
                    index_poule,
                ),
            )
            cellule.alignment = Alignment(horizontal="center")
    feuille_tirage.column_dimensions["A"].width = 18
    feuille_tirage.column_dimensions["C"].width = max(
        feuille_tirage.column_dimensions["C"].width or 0,
        24,
    )
    for colonne in range(2, len(poules) + 2):
        lettre_colonne = feuille_tirage.cell(1, colonne).column_letter
        feuille_tirage.column_dimensions[lettre_colonne].width = max(
            feuille_tirage.column_dimensions[lettre_colonne].width or 0,
            11,
        )
    feuille_tirage.freeze_panes = "B8"

    feuille_tous = classeur.create_sheet("Tous les tirages")
    feuille_tous.sheet_view.showGridLines = False
    ligne = 1
    for numero_tirage, tirage in enumerate(solutions, start=1):
        positions = _positions_par_poule(tirage)
        feuille_tous.cell(ligne, 1, "TIRAGE {}".format(numero_tirage)).font = Font(
            size=14, bold=True
        )
        feuille_tous.cell(ligne + 1, 1, "POULES")
        feuille_tous.cell(ligne + 2, 1, "")
        for index_poule, numero_poule in enumerate(poules, start=1):
            colonne = index_poule + 1
            feuille_tous.cell(ligne + 1, colonne, numero_poule)
            feuille_tous.cell(ligne + 2, colonne, _nom_colonne_poule(index_poule))
        for colonne in range(1, len(poules) + 2):
            for ligne_entete in (ligne + 1, ligne + 2):
                cellule = feuille_tous.cell(ligne_entete, colonne)
                cellule.font = Font(bold=True, color="FFFFFF")
                cellule.fill = PatternFill(fill_type="solid", fgColor=COULEUR_ENTETE)
                cellule.alignment = Alignment(horizontal="center")
        for rang in range(1, nombre_rangs + 1):
            feuille_tous.cell(ligne + 2 + rang, 1, _libelle_rang(rang)).font = Font(bold=True)
            for index_poule, numero_poule in enumerate(poules, start=1):
                cellule = feuille_tous.cell(
                    ligne + 2 + rang,
                    index_poule + 1,
                    positions.get((numero_poule, rang), ""),
                )
                cellule.alignment = Alignment(horizontal="center")
        ligne += hauteur_bloc
    feuille_tous.column_dimensions["A"].width = 18
    for colonne in range(2, len(poules) + 2):
        feuille_tous.column_dimensions[feuille_tous.cell(1, colonne).column_letter].width = 11
    feuille_tous.freeze_panes = "B4"

    if matchs:
        _creer_onglet_tableau(classeur, solutions[numero_tirage_choisi - 1], matchs)

    try:
        classeur.calculation.fullCalcOnLoad = True
        classeur.calculation.forceFullCalc = True
        classeur.calculation.calcMode = "auto"
    except AttributeError:
        pass
    fichier_sortie.parent.mkdir(parents=True, exist_ok=True)
    classeur.save(fichier_sortie)
    classeur.close()


def mettre_a_jour_tirage_choisi(fichier_excel, numero_tirage):
    """Met à jour la cellule de sélection dans un classeur de résultats."""
    fichier_excel = Path(fichier_excel)
    classeur = load_workbook(fichier_excel)
    try:
        if "Tirage choisi" not in classeur.sheetnames:
            raise ValueError("L'onglet 'Tirage choisi' est introuvable")
        feuille = classeur["Tirage choisi"]
        numero_tirage = int(numero_tirage)
        validation = next(iter(feuille.data_validations.dataValidation), None)
        nombre_tirages = int(validation.formula2) if validation is not None else 0
        if not 1 <= numero_tirage <= nombre_tirages:
            raise ValueError(
                "Le numéro du tirage doit être compris entre 1 et {}.".format(nombre_tirages)
            )
        feuille["B3"] = numero_tirage
        feuille["B4"] = "NON VERROUILLÉ"
        try:
            classeur.calculation.fullCalcOnLoad = True
            classeur.calculation.forceFullCalc = True
            classeur.calculation.calcMode = "auto"
        except AttributeError:
            pass
        classeur.save(fichier_excel)
    finally:
        classeur.close()
