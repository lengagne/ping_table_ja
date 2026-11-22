"""Interface graphique de lancement du calcul."""

import json
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .configuration_fichier import charger_configuration, configuration_par_defaut
from .excel import creer_fichier_solution, creer_liste_joueurs, lire_classement
from .solveur import resoudre


PREFERENCES = Path.home() / ".ping_table_ja" / "preferences.json"


def construire_matrice_classements(classements):
    """Transforme les classements en lignes de rang et colonnes de poules."""
    numeros_poules = sorted(classements)
    rang_maximum = max(
        (int(joueur["rang"]) for joueurs in classements.values() for joueur in joueurs),
        default=0,
    )
    joueurs_par_poule_et_rang = {
        (numero_poule, int(joueur["rang"])): joueur
        for numero_poule, joueurs in classements.items()
        for joueur in joueurs
    }

    lignes = []
    for rang in range(1, rang_maximum + 1):
        valeurs = [rang]
        for numero_poule in numeros_poules:
            joueur = joueurs_par_poule_et_rang.get((numero_poule, rang))
            if joueur is None:
                valeurs.append("")
                continue
            nom = joueur["nom"]
            club = joueur.get("club", "")
            valeurs.append("{} — {}".format(nom, club) if club else nom)
        lignes.append(valeurs)

    return numeros_poules, lignes


class Application(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=24)
        self.parent = parent
        self.config_var = tk.StringVar()
        self.excel_var = tk.StringVar()
        self.statut_var = tk.StringVar(value="Sélectionnez un fichier Excel pour commencer.")
        self._construire_interface()
        self._charger_preferences()

    def _construire_interface(self):
        self.grid(sticky="nsew")
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(6, weight=1)

        ttk.Label(self, text="Génération du tableau", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 20)
        )
        ttk.Label(self, text="Fichier de configuration").grid(row=1, column=0, sticky="w")
        ttk.Entry(self, textvariable=self.config_var).grid(row=2, column=0, sticky="ew", padx=(0, 8), pady=(4, 16))
        ttk.Button(self, text="Parcourir…", command=self._choisir_configuration).grid(row=2, column=1, pady=(4, 16))

        ttk.Label(self, text="Fichier Excel des classements").grid(row=3, column=0, sticky="w")
        ttk.Entry(self, textvariable=self.excel_var).grid(row=4, column=0, sticky="ew", padx=(0, 8), pady=(4, 20))
        ttk.Button(self, text="Parcourir…", command=self._choisir_excel).grid(row=4, column=1, pady=(4, 20))

        ttk.Label(self, text="Aperçu des joueurs chargés").grid(row=5, column=0, columnspan=2, sticky="w")
        cadre_apercu = ttk.Frame(self)
        cadre_apercu.grid(row=6, column=0, columnspan=2, sticky="nsew", pady=(4, 20))
        cadre_apercu.columnconfigure(0, weight=1)
        cadre_apercu.rowconfigure(0, weight=1)

        self.apercu = ttk.Treeview(
            cadre_apercu,
            columns=("rang",),
            show="headings",
            height=6,
        )
        self.apercu.heading("rang", text="Rang")
        self.apercu.column("rang", width=65, anchor="center", stretch=False)
        self.apercu.grid(row=0, column=0, sticky="nsew")

        defilement_vertical = ttk.Scrollbar(cadre_apercu, orient="vertical", command=self.apercu.yview)
        defilement_vertical.grid(row=0, column=1, sticky="ns")
        defilement_horizontal = ttk.Scrollbar(cadre_apercu, orient="horizontal", command=self.apercu.xview)
        defilement_horizontal.grid(row=1, column=0, sticky="ew")
        self.apercu.configure(
            yscrollcommand=defilement_vertical.set,
            xscrollcommand=defilement_horizontal.set,
        )

        self.bouton_calcul = ttk.Button(self, text="Calculer", style="Accent.TButton", command=self._demarrer_calcul)
        self.bouton_calcul.grid(row=7, column=0, columnspan=2, sticky="ew", ipady=7)
        self.progression = ttk.Progressbar(self, mode="indeterminate")
        self.progression.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(14, 8))
        ttk.Label(self, textvariable=self.statut_var, wraplength=580).grid(row=9, column=0, columnspan=2, sticky="w")

    def _charger_preferences(self):
        configuration = configuration_par_defaut()
        try:
            donnees = json.loads(PREFERENCES.read_text(encoding="utf-8"))
            dernier = Path(donnees.get("dernier_fichier_configuration", ""))
            if dernier.is_file():
                configuration = dernier
        except (OSError, ValueError, TypeError):
            pass
        self.config_var.set(str(configuration))

    def _sauver_preferences(self):
        try:
            PREFERENCES.parent.mkdir(parents=True, exist_ok=True)
            PREFERENCES.write_text(json.dumps({
                "dernier_fichier_configuration": self.config_var.get()
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            # L'application reste utilisable même si le dossier personnel
            # n'autorise pas l'enregistrement des préférences.
            pass

    def _choisir_configuration(self):
        chemin = filedialog.askopenfilename(
            title="Choisir la configuration",
            initialdir=str(Path(self.config_var.get()).parent),
            filetypes=(("Configuration JSON", "*.json"), ("Tous les fichiers", "*.*")),
        )
        if chemin:
            self.config_var.set(chemin)
            self._sauver_preferences()
            if Path(self.excel_var.get()).is_file():
                self._charger_apercu(Path(self.excel_var.get()))

    def _choisir_excel(self):
        chemin = filedialog.askopenfilename(
            title="Choisir le classement Excel",
            filetypes=(("Classeur Excel", "*.xlsx"), ("Tous les fichiers", "*.*")),
        )
        if chemin:
            self.excel_var.set(chemin)
            self._charger_apercu(Path(chemin))

    def _charger_apercu(self, chemin_excel):
        """Lit le classeur sélectionné et affiche ses joueurs dans le tableau."""
        for ligne in self.apercu.get_children():
            self.apercu.delete(ligne)

        try:
            configuration = charger_configuration(Path(self.config_var.get()).expanduser())
            classements = lire_classement(chemin_excel, configuration.onglet_excel)
            numeros_poules, lignes = construire_matrice_classements(classements)
            colonnes = ("rang",) + tuple(
                "poule_{}".format(numero) for numero in numeros_poules
            )
            self.apercu.configure(columns=colonnes)
            self.apercu.heading("rang", text="Rang")
            self.apercu.column("rang", width=65, anchor="center", stretch=False)
            for numero_poule in numeros_poules:
                colonne = "poule_{}".format(numero_poule)
                self.apercu.heading(colonne, text="Poule {}".format(numero_poule))
                self.apercu.column(colonne, width=190, minwidth=130, anchor="w")
            for valeurs in lignes:
                self.apercu.insert("", "end", values=valeurs)

            nombre_joueurs = sum(len(joueurs) for joueurs in classements.values())
            self.statut_var.set(
                "{} joueur{} chargé{} — prêt à lancer le calcul.".format(
                    nombre_joueurs,
                    "s" if nombre_joueurs > 1 else "",
                    "s" if nombre_joueurs > 1 else "",
                )
            )
        except Exception as erreur:
            self.statut_var.set("Impossible de charger l'aperçu.")
            messagebox.showerror("Erreur de lecture", str(erreur))

    def _demarrer_calcul(self):
        configuration = Path(self.config_var.get()).expanduser()
        excel = Path(self.excel_var.get()).expanduser()
        if not configuration.is_file():
            messagebox.showerror("Configuration manquante", "Sélectionnez un fichier de configuration valide.")
            return
        if not excel.is_file() or excel.suffix.lower() != ".xlsx":
            messagebox.showerror("Fichier Excel manquant", "Sélectionnez un fichier Excel .xlsx valide.")
            return

        self._sauver_preferences()
        self.bouton_calcul.state(["disabled"])
        self.progression.start(12)
        self.statut_var.set("Calcul en cours…")
        threading.Thread(target=self._calculer, args=(configuration, excel), daemon=True).start()

    def _calculer(self, chemin_configuration, chemin_excel):
        try:
            configuration = charger_configuration(chemin_configuration)
            classements = lire_classement(chemin_excel, configuration.onglet_excel)
            joueurs = creer_liste_joueurs(classements)
            if len(joueurs) != configuration.nombre_positions:
                raise ValueError(
                    "{} joueurs trouvés ; {} sont attendus.".format(len(joueurs), configuration.nombre_positions)
                )
            solution = resoudre(joueurs, configuration.contraintes, configuration.nombre_positions)
            if solution is None:
                raise ValueError("Aucune solution ne respecte toutes les contraintes.")
            sortie = chemin_excel.with_name(chemin_excel.stem + "_solution.xlsx")
            creer_fichier_solution(sortie, solution, configuration.onglet_sortie)
            self.parent.after(0, self._calcul_termine, sortie)
        except Exception as erreur:
            traceback.print_exc()
            self.parent.after(0, self._calcul_echoue, str(erreur))

    def _calcul_termine(self, sortie):
        self._fin_traitement()
        self.statut_var.set("Calcul terminé : {}".format(sortie))
        messagebox.showinfo("Calcul terminé", "Le fichier a été créé :\n{}".format(sortie))

    def _calcul_echoue(self, message):
        self._fin_traitement()
        self.statut_var.set("Échec du calcul.")
        messagebox.showerror("Erreur", message)

    def _fin_traitement(self):
        self.progression.stop()
        self.bouton_calcul.state(["!disabled"])


def main():
    racine = tk.Tk()
    racine.title("Ping Table JA")
    racine.geometry("1100x610")
    racine.minsize(700, 540)
    style = ttk.Style(racine)
    style.configure("Title.TLabel", font=("TkDefaultFont", 18, "bold"))
    style.configure("Accent.TButton", font=("TkDefaultFont", 11, "bold"))
    Application(racine)
    racine.mainloop()


if __name__ == "__main__":
    main()
