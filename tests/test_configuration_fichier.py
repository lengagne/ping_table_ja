import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from ping_table_ja.configuration_fichier import charger_configuration, configuration_par_defaut
from ping_table_ja.excel import creer_fichier_solution, mettre_a_jour_tirage_choisi
from ping_table_ja.gui import construire_matrice_classements
from ping_table_ja.solveur import resoudre_plusieurs, resoudre_toutes


class TestConfigurationFichier(unittest.TestCase):
    def test_configuration_par_defaut_est_chargeable(self):
        configuration = charger_configuration(configuration_par_defaut())
        self.assertEqual(configuration.nombre_positions, 32)
        self.assertEqual(len(configuration.matchs), 36)
        self.assertEqual(len(configuration.contraintes), 77)

    def test_generateur_inconnu_est_refuse(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "invalide.json"
            chemin.write_text(
                json.dumps({"version": 1, "generateur": "inconnu"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Générateur inconnu"):
                charger_configuration(chemin)

    def test_classements_presentes_par_poule_et_par_rang(self):
        classements = {
            2: [{"rang": 1, "nom": "Béatrice", "club": "Club B"}],
            1: [
                {"rang": 1, "nom": "Alice", "club": "Club A"},
                {"rang": 2, "nom": "Arthur", "club": "Club C"},
            ],
        }
        poules, lignes = construire_matrice_classements(classements)
        self.assertEqual(poules, [1, 2])
        self.assertEqual(lignes, [
            [1, "Alice — Club A", "Béatrice — Club B"],
            [2, "Arthur — Club C", ""],
        ])

    def test_resolution_exhaustive(self):
        joueurs = [{"nom": "A"}, {"nom": "B"}]
        solutions = resoudre_toutes(joueurs, [], nombre_positions=2)
        self.assertEqual(len(solutions), 2)
        self.assertEqual(
            {tuple(joueur["nom"] for joueur in solution) for solution in solutions},
            {("A", "B"), ("B", "A")},
        )

    def test_resolution_limitee_et_progression(self):
        joueurs = [{"nom": "A"}, {"nom": "B"}, {"nom": "C"}]
        progression = []
        solutions, recherche_terminee = resoudre_plusieurs(
            joueurs,
            [],
            nombre_positions=3,
            limite=2,
            notifier=progression.append,
        )
        self.assertEqual(len(solutions), 2)
        self.assertEqual(progression, [1, 2])
        self.assertFalse(recherche_terminee)

    def test_resolution_interruptible(self):
        joueurs = [{"nom": "A"}, {"nom": "B"}]
        solutions, recherche_terminee = resoudre_plusieurs(
            joueurs,
            [],
            nombre_positions=2,
            arreter=lambda: True,
        )
        self.assertEqual(solutions, [])
        self.assertFalse(recherche_terminee)

    def test_classeur_resultats_contient_recap_et_tirages_dynamiques(self):
        solution_1 = [
            {"nom": "Alice", "club": "A", "poule": 1, "rang_poule": 1},
            {"nom": "Benoît", "club": "B", "poule": 2, "rang_poule": 2},
        ]
        solution_2 = list(reversed(solution_1))
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "resultats.xlsx"
            creer_fichier_solution(
                chemin,
                solution_1,
                solutions=[solution_1, solution_2],
                recap={
                    "configuration": "configuration.json",
                    "excel": "poules.xlsx",
                    "mode": "Deux solutions",
                    "recherche_terminee": False,
                },
            )
            classeur = load_workbook(chemin, data_only=False)
            self.assertEqual(
                classeur.sheetnames,
                ["Récap", "Tirage choisi", "Tous les tirages"],
            )
            self.assertEqual(classeur["Tirage choisi"]["B3"].value, 1)
            self.assertTrue(classeur["Tirage choisi"]["B7"].value.startswith("=IFERROR(INDEX"))
            self.assertEqual(classeur["Tous les tirages"].max_row, 5)
            classeur.close()

            mettre_a_jour_tirage_choisi(chemin, 2)
            classeur = load_workbook(chemin, data_only=False)
            self.assertEqual(classeur["Tirage choisi"]["B3"].value, 2)
            classeur.close()


if __name__ == "__main__":
    unittest.main()
