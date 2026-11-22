"""Lecture des poules et écriture de la solution au format Excel."""

import re
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import FormulaRule
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


def creer_liste_joueurs(classements):
    return [
        {
            "nom": joueur["nom"], "club": joueur["club"],
            "poule": int(numero_poule), "rang_poule": int(joueur["rang"]),
        }
        for numero_poule, classement in classements.items()
        for joueur in classement
    ]


COULEUR_ENTETE = "4472C4"
COULEUR_SELECTION = "FFF2CC"


def _styliser_entetes(feuille, ligne, entetes):
    for colonne, entete in enumerate(entetes, start=1):
        cellule = feuille.cell(row=ligne, column=colonne, value=entete)
        cellule.font = Font(bold=True, color="FFFFFF")
        cellule.fill = PatternFill(fill_type="solid", fgColor=COULEUR_ENTETE)
        cellule.alignment = Alignment(horizontal="center", vertical="center")


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
    if len(solutions) * nombre_positions > 1_048_575:
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
    validation = DataValidation(
        type="whole",
        operator="between",
        formula1="1",
        formula2=str(len(solutions)),
        allow_blank=False,
    )
    validation.error = "Choisissez un numéro entre 1 et {}.".format(len(solutions))
    validation.errorTitle = "Numéro de tirage invalide"
    validation.prompt = "Saisissez le numéro du tirage à afficher."
    validation.promptTitle = "Choisir un tirage"
    validation.showErrorMessage = True
    validation.showInputMessage = True
    feuille_tirage.add_data_validation(validation)
    validation.add(feuille_tirage["B3"])

    entetes = ["Place (n° de match)", "Nom", "Club", "Poule", "Rang dans la poule"]
    _styliser_entetes(feuille_tirage, 6, entetes)
    derniere_ligne_donnees = 1 + len(solutions) * nombre_positions
    colonnes_sources = ("C", "D", "E", "F")
    for position in range(1, nombre_positions + 1):
        ligne = position + 6
        feuille_tirage.cell(ligne, 1, position)
        for colonne_destination, colonne_source in enumerate(colonnes_sources, start=2):
            feuille_tirage.cell(
                ligne,
                colonne_destination,
                "=IFERROR(INDEX('Tous les tirages'!${0}$2:${0}${1},(($B$3-1)*{2})+$A{3}),\"\")".format(
                    colonne_source,
                    derniere_ligne_donnees,
                    nombre_positions,
                    ligne,
                ),
            )
    for colonne, largeur in zip("ABCDE", (22, 30, 25, 12, 22)):
        feuille_tirage.column_dimensions[colonne].width = largeur
    feuille_tirage.freeze_panes = "A7"
    feuille_tirage.auto_filter.ref = "A6:E{}".format(nombre_positions + 6)

    feuille_tous = classeur.create_sheet("Tous les tirages")
    feuille_tous.sheet_view.showGridLines = False
    _styliser_entetes(
        feuille_tous,
        1,
        ["N° tirage", "Place (n° de match)", "Nom", "Club", "Poule", "Rang dans la poule"],
    )
    ligne = 2
    for numero_tirage, tirage in enumerate(solutions, start=1):
        for position, joueur in enumerate(tirage, start=1):
            feuille_tous.cell(ligne, 1, numero_tirage)
            feuille_tous.cell(ligne, 2, position)
            if joueur is not None:
                feuille_tous.cell(ligne, 3, joueur.get("nom", ""))
                feuille_tous.cell(ligne, 4, joueur.get("club", ""))
                feuille_tous.cell(ligne, 5, joueur.get("poule", ""))
                feuille_tous.cell(ligne, 6, joueur.get("rang_poule", ""))
            ligne += 1
    for colonne, largeur in zip("ABCDEF", (12, 22, 30, 25, 12, 22)):
        feuille_tous.column_dimensions[colonne].width = largeur
    feuille_tous.freeze_panes = "A2"
    feuille_tous.auto_filter.ref = "A1:F{}".format(ligne - 1)
    feuille_tous.conditional_formatting.add(
        "A2:F{}".format(ligne - 1),
        FormulaRule(
            formula=["$A2='Tirage choisi'!$B$3"],
            fill=PatternFill(fill_type="solid", fgColor="E2F0D9"),
        ),
    )

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
        feuille["B3"] = int(numero_tirage)
        try:
            classeur.calculation.fullCalcOnLoad = True
            classeur.calculation.forceFullCalc = True
            classeur.calculation.calcMode = "auto"
        except AttributeError:
            pass
        classeur.save(fichier_excel)
    finally:
        classeur.close()
