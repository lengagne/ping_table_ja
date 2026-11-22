import json
import tempfile
import unittest
from pathlib import Path

from ping_table_ja.configuration_fichier import charger_configuration, configuration_par_defaut
from ping_table_ja.gui import construire_matrice_classements


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


if __name__ == "__main__":
    unittest.main()
