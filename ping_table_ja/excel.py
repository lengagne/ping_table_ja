"""Lecture des poules et écriture de la solution au format Excel."""

import re
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

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


def creer_fichier_solution(fichier_sortie, solution, nom_onglet="TropFortSeb"):
    fichier_sortie = Path(fichier_sortie)
    classeur = Workbook()
    feuille = classeur.active
    feuille.title = nom_onglet
    entetes = ["Position", "Nom", "Club", "Poule", "Rang dans la poule"]
    for colonne, entete in enumerate(entetes, start=1):
        cellule = feuille.cell(row=1, column=colonne, value=entete)
        cellule.font = Font(bold=True, color="FFFFFF")
        cellule.fill = PatternFill(fill_type="solid", fgColor="4472C4")
    for position, joueur in enumerate(solution, start=1):
        feuille.cell(position + 1, 1, position)
        if joueur is None:
            feuille.cell(position + 1, 2, "je sais pas")
        else:
            for colonne, cle in enumerate(("nom", "club", "poule", "rang_poule"), start=2):
                feuille.cell(position + 1, colonne, joueur[cle])
    for colonne, largeur in zip("ABCDE", (12, 30, 25, 12, 22)):
        feuille.column_dimensions[colonne].width = largeur
    feuille.freeze_panes = "A2"
    feuille.auto_filter.ref = "A1:E{}".format(len(solution) + 1)
    fichier_sortie.parent.mkdir(parents=True, exist_ok=True)
    classeur.save(fichier_sortie)
    classeur.close()
