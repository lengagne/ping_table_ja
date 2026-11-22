"""Lecture des poules et écriture de la solution au format Excel."""

import re
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

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


def creer_fichier_solution(
    fichier_sortie,
    solution,
    nom_onglet="Tirage choisi",
    solutions=None,
    recap=None,
    numero_tirage_choisi=1,
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
        try:
            classeur.calculation.fullCalcOnLoad = True
            classeur.calculation.forceFullCalc = True
            classeur.calculation.calcMode = "auto"
        except AttributeError:
            pass
        classeur.save(fichier_excel)
    finally:
        classeur.close()
