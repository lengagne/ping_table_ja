"""Interface en ligne de commande de l'application."""

import argparse
import sys
from pathlib import Path

from .configuration import creer_contraintes, creer_matchs
from .contraintes import verifier_contraintes
from .excel import creer_fichier_solution, creer_liste_joueurs, lire_classement
from .solveur import resoudre


def construire_parser():
    parser = argparse.ArgumentParser(description="Génère un tableau double KO de 32 joueurs")
    parser.add_argument("fichier", type=Path, help="Fichier Excel .xlsx contenant les poules")
    parser.add_argument("--onglet", default="classement poules", help="Nom de l'onglet source")
    parser.add_argument("--sortie", type=Path, default=Path("solution.xlsx"), help="Fichier Excel produit")
    return parser


def main(argv=None):
    parser = construire_parser()
    arguments = parser.parse_args(argv)
    if not arguments.fichier.is_file():
        parser.error("Fichier introuvable : {}".format(arguments.fichier))
    if arguments.fichier.suffix.lower() != ".xlsx":
        parser.error("Le fichier doit avoir l'extension .xlsx")

    joueurs = creer_liste_joueurs(lire_classement(arguments.fichier, arguments.onglet))
    print("{} joueurs trouvés.".format(len(joueurs)))
    if len(joueurs) != 32:
        print("Erreur : 32 joueurs sont attendus, mais {} ont été trouvés.".format(len(joueurs)))
        return 1

    matchs = creer_matchs()
    contraintes = creer_contraintes(matchs)
    print("Résolution en cours…")
    solution = resoudre(joueurs, contraintes)
    if solution is None:
        print("Aucune solution ne respecte toutes les contraintes.")
        return 1

    verifier_contraintes(solution, contraintes)
    print("\nLISTE DES 32 JOUEURS")
    print("-" * 70)
    for position, joueur in enumerate(solution, start=1):
        print("{:2d}. {} | {} | Poule {} | Rang {}".format(
            position, joueur["nom"], joueur["club"], joueur["poule"], joueur["rang_poule"]
        ))
    creer_fichier_solution(arguments.sortie, solution)
    print("Fichier créé : {}".format(arguments.sortie))
    return 0


if __name__ == "__main__":
    sys.exit(main())
