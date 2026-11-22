import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from ping_table_ja.configuration_fichier import (
    charger_configuration,
    configuration_par_defaut,
    enregistrer_configuration,
)
from ping_table_ja.excel import (
    creer_fichier_solution,
    creer_liste_joueurs,
    mettre_a_jour_tirage_choisi,
)
from ping_table_ja.editeur_configuration import (
    calculer_profondeurs_matchs,
    formater_reference,
    parser_reference,
)
from ping_table_ja.generateur_tableau import generer_configuration_standard, niveaux_principaux
from ping_table_ja.gui import construire_matrice_classements, construire_matrice_tirage
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

    def test_generation_tableau_standard_integral(self):
        donnees = generer_configuration_standard(8, classement_integral=True)
        self.assertEqual(len(donnees["matchs"]), 10)
        self.assertEqual([match["numero"] for match in donnees["matchs"]], list(range(1, 11)))
        self.assertEqual(niveaux_principaux(8), ["1/4", "1/2", "finale"])
        self.assertEqual(donnees["matchs"][0]["niveau"], "barrage_2_3")
        self.assertEqual(donnees["matchs"][0]["participant_1"]["numero"], 2)
        self.assertEqual(donnees["matchs"][0]["participant_2"]["numero"], 3)
        self.assertEqual(donnees["matchs"][1]["participant_1"]["numero"], 1)
        self.assertEqual(donnees["matchs"][1]["participant_2"], {"type": "vainqueur", "match": 1})
        self.assertEqual(donnees["matchs"][2]["participant_1"], {"type": "perdant", "match": 1})
        self.assertEqual(donnees["matchs"][2]["participant_2"]["numero"], 4)
        self.assertEqual(len(donnees["contraintes"]), 6)

    def test_generation_avec_barrages_1_4_et_2_3(self):
        donnees = generer_configuration_standard(
            8, classement_integral=True, barrages_1_contre_4=True
        )
        self.assertEqual(len(donnees["matchs"]), 12)
        self.assertEqual(donnees["contraintes"][0]["rangs"], [1, 4])
        self.assertEqual(donnees["contraintes"][1]["rangs"], [2, 3])

    def test_references_de_match_de_l_editeur(self):
        self.assertEqual(parser_reference("position:12"), {"type": "position", "numero": 12})
        self.assertEqual(parser_reference("vainqueur:7"), {"type": "vainqueur", "match": 7})
        self.assertEqual(
            formater_reference({"type": "perdant", "match": 9}),
            "perdant:9",
        )
        with self.assertRaisesRegex(ValueError, "Référence attendue"):
            parser_reference("joueur 3")

    def test_profondeurs_pour_visualiser_le_tableau(self):
        donnees = generer_configuration_standard(
            8, classement_integral=False, barrages_1_contre_4=True
        )
        profondeurs = calculer_profondeurs_matchs(donnees["matchs"])
        self.assertEqual([profondeurs[n] for n in range(1, 5)], [1, 1, 1, 1])
        self.assertEqual(max(profondeurs.values()), 3)

        donnees["matchs"][0]["participant_1"] = {"type": "vainqueur", "match": 1}
        with self.assertRaisesRegex(ValueError, "Cycle détecté"):
            calculer_profondeurs_matchs(donnees["matchs"])

    def test_generation_tableau_standard_sans_classement(self):
        donnees = generer_configuration_standard(16, classement_integral=False)
        self.assertEqual(len(donnees["matchs"]), 18)

    def test_configuration_v2_charge_matchs_et_contraintes(self):
        donnees = generer_configuration_standard(
            8, classement_integral=False, barrages_1_contre_4=True
        )
        donnees["contraintes"] = [
            {
                "type": "poules_differentes",
                "cible": {"type": "niveau", "niveau": "1/4"},
            },
            {
                "type": "rangs_participants",
                "cible": {"type": "match", "numero": 1},
                "participant_1": [1],
                "participant_2": [4],
            },
        ]
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "tableau.json"
            enregistrer_configuration(chemin, donnees)
            configuration = charger_configuration(chemin)
        self.assertEqual(configuration.nombre_positions, 8)
        self.assertEqual(len(configuration.matchs), 7)
        self.assertEqual(len(configuration.contraintes), 5)
        self.assertEqual(configuration.matchs[1].niveau, "1/4")

    def test_poule_de_trois_completee_par_un_quatrieme_vide(self):
        classements = {
            1: [
                {"rang": 1, "nom": "A", "club": "Club A"},
                {"rang": 2, "nom": "B", "club": "Club B"},
                {"rang": 3, "nom": "C", "club": "Club C"},
            ],
            2: [
                {"rang": rang, "nom": "J{}".format(rang), "club": "Club D"}
                for rang in range(1, 5)
            ],
        }
        joueurs = creer_liste_joueurs(classements, nombre_positions=8)
        self.assertEqual(len(joueurs), 8)
        absent = [joueur for joueur in joueurs if joueur.get("absent")]
        self.assertEqual(absent, [{
            "nom": "", "club": "", "poule": 1, "rang_poule": 4, "absent": True,
        }])

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

    def test_tirage_presente_par_poule_et_par_rang(self):
        solution = [
            {"nom": "A", "poule": 1, "rang_poule": 1},
            {"nom": "B", "poule": 2, "rang_poule": 2},
            {"nom": "C", "poule": 2, "rang_poule": 1},
            {"nom": "D", "poule": 1, "rang_poule": 2},
        ]
        poules, lignes = construire_matrice_tirage(solution)
        self.assertEqual(poules, [1, 2])
        self.assertEqual(lignes, [["", "A", "B"], ["1ER", 1, 3], ["2EME", 4, 2]])

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
                ["Récap", "Poules", "Tirage choisi", "Tous les tirages"],
            )
            self.assertEqual(classeur["Poules"]["B3"].value, "Poule 1")
            self.assertEqual(classeur["Poules"]["C3"].value, "Poule 2")
            self.assertEqual(classeur["Poules"]["A4"].value, "1ER")
            self.assertEqual(classeur["Poules"]["B4"].value, "Alice — A")
            self.assertEqual(classeur["Poules"]["C5"].value, "Benoît — B")
            self.assertEqual(classeur["Tirage choisi"]["B3"].value, 1)
            self.assertEqual(
                classeur["Tirage choisi"]["C3"].value,
                "sur 2 tirages disponibles",
            )
            validation = classeur["Tirage choisi"].data_validations.dataValidation[0]
            self.assertEqual(validation.formula1, "1")
            self.assertEqual(validation.formula2, "2")
            self.assertEqual(classeur["Tirage choisi"]["B6"].value, 1)
            self.assertEqual(classeur["Tirage choisi"]["C6"].value, 2)
            self.assertEqual(classeur["Tirage choisi"]["B7"].value, "A")
            self.assertTrue(classeur["Tirage choisi"]["B8"].value.startswith("=IFERROR(INDEX"))
            self.assertEqual(classeur["Tous les tirages"]["A1"].value, "TIRAGE 1")
            self.assertEqual(classeur["Tous les tirages"]["B4"].value, 1)
            self.assertEqual(classeur["Tous les tirages"]["C5"].value, 2)
            self.assertEqual(classeur["Tous les tirages"]["A7"].value, "TIRAGE 2")
            classeur.close()

            mettre_a_jour_tirage_choisi(chemin, 2)
            classeur = load_workbook(chemin, data_only=False)
            self.assertEqual(classeur["Tirage choisi"]["B3"].value, 2)
            classeur.close()

            with self.assertRaisesRegex(ValueError, "compris entre 1 et 2"):
                mettre_a_jour_tirage_choisi(chemin, 3)


if __name__ == "__main__":
    unittest.main()
