"""Interface graphique de lancement du calcul."""

import json
import random
import threading
import time
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .configuration_fichier import charger_configuration, configuration_par_defaut
from .excel import creer_fichier_solution, creer_liste_joueurs, lire_classement
from .solveur import resoudre, resoudre_plusieurs


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
        self.solutions = []
        self.solutions_recherche_terminee = False
        self.chemin_excel_solutions = None
        self.configuration_solutions = None
        self.arret_calcul = threading.Event()
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

        cadre_actions = ttk.Frame(self)
        cadre_actions.grid(row=7, column=0, columnspan=2, sticky="ew")
        for colonne in range(4):
            cadre_actions.columnconfigure(colonne, weight=1)

        self.bouton_une_solution = ttk.Button(
            cadre_actions,
            text="Calculer une solution",
            style="Accent.TButton",
            command=lambda: self._demarrer_calcul(mode="une"),
        )
        self.bouton_une_solution.grid(row=0, column=0, sticky="ew", padx=(0, 6), ipady=7)
        self.bouton_toutes_solutions = ttk.Button(
            cadre_actions,
            text="Calculer toutes les solutions",
            command=lambda: self._demarrer_calcul(mode="toutes"),
        )
        self.bouton_toutes_solutions.grid(row=0, column=1, sticky="ew", padx=6, ipady=7)
        self.bouton_n_solutions = ttk.Button(
            cadre_actions,
            text="Calculer N solutions",
            command=lambda: self._demarrer_calcul(mode="nombre"),
        )
        self.bouton_n_solutions.grid(row=0, column=2, sticky="ew", padx=6, ipady=7)
        self.bouton_solution_aleatoire = ttk.Button(
            cadre_actions,
            text="Choisir une solution aléatoire",
            command=self._choisir_solution_aleatoire,
            state="disabled",
        )
        self.bouton_solution_aleatoire.grid(row=0, column=3, sticky="ew", padx=(6, 0), ipady=7)
        self.progression = ttk.Progressbar(self, mode="indeterminate")
        self.progression.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(14, 8))
        cadre_statut = ttk.Frame(self)
        cadre_statut.grid(row=9, column=0, columnspan=2, sticky="ew")
        cadre_statut.columnconfigure(0, weight=1)
        ttk.Label(cadre_statut, textvariable=self.statut_var, wraplength=800).grid(row=0, column=0, sticky="w")
        self.bouton_arreter = ttk.Button(
            cadre_statut,
            text="Arrêter le calcul",
            command=self._arreter_calcul,
            state="disabled",
        )
        self.bouton_arreter.grid(row=0, column=1, sticky="e", padx=(12, 0))

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
            self._invalider_solutions()
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
            self._invalider_solutions()
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

    def _invalider_solutions(self):
        self.solutions = []
        self.solutions_recherche_terminee = False
        self.chemin_excel_solutions = None
        self.configuration_solutions = None
        if hasattr(self, "bouton_solution_aleatoire"):
            self.bouton_solution_aleatoire.state(["disabled"])

    def _demarrer_calcul(self, mode):
        configuration = Path(self.config_var.get()).expanduser()
        excel = Path(self.excel_var.get()).expanduser()
        if not configuration.is_file():
            messagebox.showerror("Configuration manquante", "Sélectionnez un fichier de configuration valide.")
            return
        if not excel.is_file() or excel.suffix.lower() != ".xlsx":
            messagebox.showerror("Fichier Excel manquant", "Sélectionnez un fichier Excel .xlsx valide.")
            return

        limite = None
        if mode == "nombre":
            limite = simpledialog.askinteger(
                "Nombre de solutions",
                "Combien de solutions faut-il rechercher ?",
                initialvalue=10,
                minvalue=1,
                parent=self.parent,
            )
            if limite is None:
                return
        if mode == "toutes" and not messagebox.askyesno(
            "Calcul exhaustif",
            "Le calcul de toutes les solutions peut être long et utiliser beaucoup de mémoire. Continuer ?",
        ):
            return

        self._sauver_preferences()
        self._invalider_solutions()
        self.arret_calcul.clear()
        self.bouton_une_solution.state(["disabled"])
        self.bouton_toutes_solutions.state(["disabled"])
        self.bouton_n_solutions.state(["disabled"])
        if mode != "une":
            self.bouton_arreter.state(["!disabled"])
        self.progression.start(12)
        messages = {
            "une": "Calcul d'une solution en cours…",
            "toutes": "Calcul de toutes les solutions en cours — 0 trouvée.",
            "nombre": "Recherche de {} solutions en cours — 0 trouvée.".format(limite),
        }
        self.statut_var.set(messages[mode])
        threading.Thread(
            target=self._calculer,
            args=(configuration, excel, mode, limite),
            daemon=True,
        ).start()

    def _calculer(self, chemin_configuration, chemin_excel, mode, limite):
        try:
            configuration = charger_configuration(chemin_configuration)
            classements = lire_classement(chemin_excel, configuration.onglet_excel)
            joueurs = creer_liste_joueurs(classements)
            if len(joueurs) != configuration.nombre_positions:
                raise ValueError(
                    "{} joueurs trouvés ; {} sont attendus.".format(len(joueurs), configuration.nombre_positions)
                )
            if mode != "une":
                derniere_notification = [0.0]

                def notifier(nombre):
                    maintenant = time.monotonic()
                    if maintenant - derniere_notification[0] >= 0.1:
                        derniere_notification[0] = maintenant
                        self.parent.after(0, self._afficher_progression_solutions, nombre, limite)

                solutions, recherche_terminee = resoudre_plusieurs(
                    joueurs,
                    configuration.contraintes,
                    configuration.nombre_positions,
                    limite=limite,
                    notifier=notifier,
                    arreter=self.arret_calcul.is_set,
                )
                if not solutions:
                    if self.arret_calcul.is_set():
                        self.parent.after(0, self._calcul_echoue, "Calcul arrêté avant de trouver une solution.")
                        return
                    raise ValueError("Aucune solution ne respecte toutes les contraintes.")
                self.parent.after(
                    0,
                    self._toutes_solutions_terminees,
                    solutions,
                    chemin_excel,
                    configuration,
                    recherche_terminee,
                    self.arret_calcul.is_set(),
                    limite,
                )
                return

            solution = resoudre(joueurs, configuration.contraintes, configuration.nombre_positions)
            if solution is None:
                raise ValueError("Aucune solution ne respecte toutes les contraintes.")
            sortie = chemin_excel.with_name(chemin_excel.stem + "_solution.xlsx")
            creer_fichier_solution(sortie, solution, configuration.onglet_sortie)
            self.parent.after(0, self._calcul_termine, sortie)
        except Exception as erreur:
            traceback.print_exc()
            self.parent.after(0, self._calcul_echoue, str(erreur))

    def _afficher_progression_solutions(self, nombre, limite):
        objectif = " / {}".format(limite) if limite is not None else ""
        self.statut_var.set("Calcul en cours — {}{} solution{} trouvée{}.".format(
            nombre,
            objectif,
            "s" if nombre > 1 else "",
            "s" if nombre > 1 else "",
        ))

    def _arreter_calcul(self):
        self.arret_calcul.set()
        self.bouton_arreter.state(["disabled"])
        self.statut_var.set("Arrêt demandé… conservation des solutions déjà trouvées.")

    def _toutes_solutions_terminees(
        self,
        solutions,
        chemin_excel,
        configuration,
        recherche_terminee,
        calcul_arrete,
        limite,
    ):
        self.solutions = solutions
        self.solutions_recherche_terminee = recherche_terminee
        self.chemin_excel_solutions = chemin_excel
        self.configuration_solutions = configuration
        self._fin_traitement()
        self.bouton_solution_aleatoire.state(["!disabled"])
        if calcul_arrete:
            resume = "Calcul arrêté : {} solutions conservées.".format(len(solutions))
        elif limite is not None and not recherche_terminee:
            resume = "Objectif atteint : {} solutions calculées.".format(len(solutions))
        else:
            resume = "Calcul terminé : {} solutions calculées.".format(len(solutions))
        self.statut_var.set(resume)
        messagebox.showinfo(
            "Calcul terminé",
            resume + "\nVous pouvez maintenant en choisir une aléatoirement.",
        )

    def _choisir_solution_aleatoire(self):
        if not self.solutions:
            return
        if not self.solutions_recherche_terminee:
            messagebox.showwarning(
                "Recherche incomplète",
                "La recherche n'était pas terminée. Le choix sera effectué uniquement parmi les {} solutions trouvées.".format(
                    len(self.solutions)
                ),
            )
        solution = random.choice(self.solutions)
        chemin_excel = self.chemin_excel_solutions
        sortie = chemin_excel.with_name(chemin_excel.stem + "_solution_aleatoire.xlsx")
        try:
            creer_fichier_solution(
                sortie,
                solution,
                self.configuration_solutions.onglet_sortie,
            )
        except Exception as erreur:
            messagebox.showerror("Erreur", str(erreur))
            return
        self.statut_var.set("Solution aléatoire créée : {}".format(sortie))
        messagebox.showinfo("Solution aléatoire", "Le fichier a été créé :\n{}".format(sortie))

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
        self.bouton_une_solution.state(["!disabled"])
        self.bouton_toutes_solutions.state(["!disabled"])
        self.bouton_n_solutions.state(["!disabled"])
        self.bouton_arreter.state(["disabled"])


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
