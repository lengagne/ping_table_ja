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
from .disposition_tableau import (
    bloc_match_visualisation,
    calculer_disposition_non_compacte,
    definitions_matchs_visualisation,
    sorties_classement,
)
from .editeur_configuration import ouvrir_editeur
from .excel import (
    creer_fichier_solution,
    creer_liste_joueurs,
    lire_classement,
    mettre_a_jour_tirage_choisi,
)
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


def _nom_colonne_poule(index):
    resultat = ""
    while index:
        index, reste = divmod(index - 1, 26)
        resultat = chr(65 + reste) + resultat
    return resultat


def _libelle_rang(rang):
    return {1: "1ER", 2: "2EME", 3: "3EME", 4: "4EME"}.get(rang, "{}EME".format(rang))


def construire_matrice_tirage(solution):
    """Présente les places d'un tirage par poule et par rang, comme dans Excel."""
    joueurs = [joueur for joueur in solution if joueur is not None]
    numeros_poules = sorted({int(joueur["poule"]) for joueur in joueurs})
    rang_maximum = max((int(joueur["rang_poule"]) for joueur in joueurs), default=0)
    places = {
        (int(joueur["poule"]), int(joueur["rang_poule"])): place
        for place, joueur in enumerate(solution, start=1)
        if joueur is not None
    }
    lettres = [""] + [
        _nom_colonne_poule(index) for index in range(1, len(numeros_poules) + 1)
    ]
    lignes = [lettres]
    for rang in range(1, rang_maximum + 1):
        lignes.append(
            [_libelle_rang(rang)]
            + [places.get((numero_poule, rang), "") for numero_poule in numeros_poules]
        )
    return numeros_poules, lignes


class Application(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=24)
        self.parent = parent
        self.config_var = tk.StringVar()
        self.excel_var = tk.StringVar()
        self.statut_var = tk.StringVar(value="Sélectionnez un fichier Excel pour commencer.")
        self.detail_configuration_var = tk.StringVar(value="—")
        self.detail_excel_var = tk.StringVar(value="—")
        self.detail_mode_var = tk.StringVar(value="Aucun calcul lancé")
        self.detail_etat_var = tk.StringVar(value="En attente")
        self.titre_tirage_var = tk.StringVar(value="Aucun tirage affiché")
        self.solutions = []
        self.solutions_recherche_terminee = False
        self.chemin_excel_solutions = None
        self.configuration_solutions = None
        self.fichier_resultats_solutions = None
        self.solution_affichee = None
        self.numero_tirage_affiche = 1
        self.arret_calcul = threading.Event()
        self._construire_interface()
        self._charger_preferences()

    def _construire_interface(self):
        self.grid(sticky="nsew")
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(6, weight=1)
        self.rowconfigure(10, weight=1)

        ttk.Label(self, text="Génération du tableau", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 20)
        )
        ttk.Label(self, text="Fichier de configuration").grid(row=1, column=0, sticky="w")
        ttk.Entry(self, textvariable=self.config_var).grid(row=2, column=0, sticky="ew", padx=(0, 8), pady=(4, 16))
        cadre_configuration = ttk.Frame(self)
        cadre_configuration.grid(row=2, column=1, pady=(4, 16))
        ttk.Button(
            cadre_configuration,
            text="Parcourir…",
            command=self._choisir_configuration,
        ).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(
            cadre_configuration,
            text="Créer…",
            command=self._creer_configuration,
        ).grid(row=0, column=1, padx=5)
        ttk.Button(
            cadre_configuration,
            text="Éditer…",
            command=self._editer_configuration,
        ).grid(row=0, column=2, padx=(5, 0))

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
        for colonne in range(5):
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
        self.bouton_creer_excel = ttk.Button(
            cadre_actions,
            text="Créer le fichier Excel de solution",
            command=self._creer_excel_solution,
            state="disabled",
        )
        self.bouton_creer_excel.grid(
            row=0, column=4, sticky="ew", padx=(6, 0), ipady=7
        )
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

        self.onglets = ttk.Notebook(self)
        self.onglets.grid(row=10, column=0, columnspan=2, sticky="nsew", pady=(14, 0))

        self.onglet_details = ttk.Frame(self.onglets, padding=16)
        self.onglet_tirage = ttk.Frame(self.onglets, padding=12)
        self.onglet_tableau = ttk.Frame(self.onglets, padding=12)
        self.onglets.add(self.onglet_details, text="Détails du calcul")
        self.onglets.add(self.onglet_tirage, text="Tirage")
        self.onglets.add(self.onglet_tableau, text="Tableau")
        self._construire_onglet_details()
        self._construire_onglet_tirage()
        self._construire_onglet_tableau()

    def _construire_onglet_details(self):
        self.onglet_details.columnconfigure(1, weight=1)
        details = (
            ("Fichier de configuration", self.detail_configuration_var),
            ("Fichier Excel", self.detail_excel_var),
            ("Mode de calcul", self.detail_mode_var),
            ("Progression / résultat", self.detail_etat_var),
        )
        for ligne, (titre, variable) in enumerate(details):
            ttk.Label(self.onglet_details, text=titre + " :", style="DetailTitle.TLabel").grid(
                row=ligne, column=0, sticky="nw", padx=(0, 16), pady=5
            )
            ttk.Label(
                self.onglet_details,
                textvariable=variable,
                wraplength=780,
            ).grid(row=ligne, column=1, sticky="w", pady=5)

    def _construire_onglet_tirage(self):
        self.onglet_tirage.columnconfigure(0, weight=1)
        self.onglet_tirage.rowconfigure(1, weight=1)
        ttk.Label(
            self.onglet_tirage,
            textvariable=self.titre_tirage_var,
            style="DetailTitle.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.tirage = ttk.Treeview(
            self.onglet_tirage,
            columns=("rang",),
            show="headings",
            height=9,
        )
        self.tirage.heading("rang", text="POULES")
        self.tirage.column("rang", width=90, anchor="center", stretch=False)
        self.tirage.grid(row=1, column=0, sticky="nsew")
        defilement_vertical = ttk.Scrollbar(
            self.onglet_tirage,
            orient="vertical",
            command=self.tirage.yview,
        )
        defilement_vertical.grid(row=1, column=1, sticky="ns")
        defilement_horizontal = ttk.Scrollbar(
            self.onglet_tirage,
            orient="horizontal",
            command=self.tirage.xview,
        )
        defilement_horizontal.grid(row=2, column=0, sticky="ew")
        self.tirage.configure(
            yscrollcommand=defilement_vertical.set,
            xscrollcommand=defilement_horizontal.set,
        )

    def _construire_onglet_tableau(self):
        self.onglet_tableau.columnconfigure(0, weight=1)
        self.onglet_tableau.rowconfigure(0, weight=1)
        self.canvas_tableau = tk.Canvas(
            self.onglet_tableau,
            background="white",
            highlightthickness=1,
            highlightbackground="#b8b8b8",
        )
        self.canvas_tableau.grid(row=0, column=0, sticky="nsew")
        barre_y = ttk.Scrollbar(
            self.onglet_tableau, orient="vertical", command=self.canvas_tableau.yview
        )
        barre_y.grid(row=0, column=1, sticky="ns")
        barre_x = ttk.Scrollbar(
            self.onglet_tableau, orient="horizontal", command=self.canvas_tableau.xview
        )
        barre_x.grid(row=1, column=0, sticky="ew")
        self.canvas_tableau.configure(
            xscrollcommand=barre_x.set, yscrollcommand=barre_y.set
        )
        self.canvas_tableau.create_text(
            24, 24, anchor="nw", text="Le tableau apparaîtra après le calcul."
        )

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
        self.detail_configuration_var.set(str(configuration))

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
            self.detail_configuration_var.set(chemin)
            self._sauver_preferences()
            if Path(self.excel_var.get()).is_file():
                self._charger_apercu(Path(self.excel_var.get()))

    def _creer_configuration(self):
        ouvrir_editeur(
            self.parent,
            apres_enregistrement=self._configuration_enregistree,
        )

    def _editer_configuration(self):
        chemin = Path(self.config_var.get()).expanduser()
        if not chemin.is_file():
            messagebox.showerror(
                "Configuration manquante",
                "Sélectionnez d'abord un fichier de configuration valide.",
            )
            return
        ouvrir_editeur(
            self.parent,
            chemin=chemin,
            apres_enregistrement=self._configuration_enregistree,
        )

    def _configuration_enregistree(self, chemin):
        chemin = str(chemin)
        self._invalider_solutions()
        self.config_var.set(chemin)
        self.detail_configuration_var.set(chemin)
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
            self.detail_excel_var.set(chemin)
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
        self.fichier_resultats_solutions = None
        self.solution_affichee = None
        if hasattr(self, "bouton_solution_aleatoire"):
            self.bouton_solution_aleatoire.state(["disabled"])
        if hasattr(self, "bouton_creer_excel"):
            self.bouton_creer_excel.state(["disabled"])
        if hasattr(self, "tirage"):
            self._vider_tirage()
        if hasattr(self, "canvas_tableau"):
            self.canvas_tableau.delete("all")
            self.canvas_tableau.create_text(
                24, 24, anchor="nw", text="Le tableau apparaîtra après le calcul."
            )

    def _vider_tirage(self):
        for ligne in self.tirage.get_children():
            self.tirage.delete(ligne)
        self.titre_tirage_var.set("Aucun tirage affiché")

    def _afficher_tirage(self, solution, numero_tirage=1):
        self._vider_tirage()
        numeros_poules, lignes = construire_matrice_tirage(solution)
        colonnes = ("rang",) + tuple(
            "poule_{}".format(numero) for numero in numeros_poules
        )
        self.tirage.configure(columns=colonnes)
        self.tirage.heading("rang", text="POULES")
        self.tirage.column("rang", width=90, anchor="center", stretch=False)
        for numero_poule in numeros_poules:
            colonne = "poule_{}".format(numero_poule)
            self.tirage.heading(colonne, text=str(numero_poule))
            self.tirage.column(colonne, width=80, minwidth=65, anchor="center")
        for valeurs in lignes:
            self.tirage.insert("", "end", values=valeurs)
        self.titre_tirage_var.set("TIRAGE {}".format(numero_tirage))
        self.solution_affichee = solution
        self.numero_tirage_affiche = numero_tirage
        self.onglets.select(self.onglet_tirage)

    def _afficher_tableau(self, configuration, solution):
        canvas = self.canvas_tableau
        canvas.delete("all")
        matchs = configuration.matchs
        definitions = definitions_matchs_visualisation(matchs)
        taille = len(solution)
        largeur_match, hauteur_match, pas_colonne = 205, 62, 270
        profondeur_max = max(2, (taille.bit_length() - 1) + 1)
        origine = 80 + profondeur_max * pas_colonne
        coordonnees, bandes, fin_y = calculer_disposition_non_compacte(
            definitions, taille, origine, pas_colonne, largeur_match,
            85, 88, 125,
        )
        definitions_par_numero = {definition["numero"]: definition for definition in definitions}

        for bande in bandes:
            for cote, plage in bande["plages"].items():
                x_titre = origine + pas_colonne if cote == "droite" else 25
                texte = (
                    "TABLEAU PLACES {} À {}".format(*plage)
                    if plage[1] - plage[0] > 1
                    else "PLACES {}e / {}e".format(*plage)
                )
                canvas.create_rectangle(
                    x_titre, bande["haut"] - 32, x_titre + 255, bande["haut"] - 7,
                    fill="#eef7ff", outline="#7aa7c7",
                )
                canvas.create_text(
                    x_titre + 8, bande["haut"] - 19, anchor="w", text=texte,
                    font=("TkDefaultFont", 9, "bold"), fill="#334155",
                )
            canvas.create_line(
                20, bande["bas"] + 61, origine * 2 + largeur_match,
                bande["bas"] + 61, fill="#cbd5e1", dash=(7, 6),
            )

        def texte_participant(participant):
            if hasattr(participant, "position"):
                position = int(participant.position)
                joueur = solution[position - 1]
                if joueur is None or joueur.get("absent"):
                    return "Position {} - absent".format(position)
                return "{} (position {})".format(joueur.get("nom", ""), position)
            precedent = participant.match.numero
            return "{} match {}".format(
                "Perdant" if participant.resultat == "perdant" else "Vainqueur",
                precedent,
            )

        for match in sorted(matchs.values(), key=lambda match: match.numero):
            x, y = coordonnees[match.numero]
            definition = definitions_par_numero[match.numero]
            cote, ordre, _plage = bloc_match_visualisation(definition, taille)
            for participant in (match.participant_1, match.participant_2):
                precedent = getattr(participant, "match", None)
                if precedent is None:
                    continue
                definition_precedente = definitions_par_numero[precedent.numero]
                cote_precedent, ordre_precedent, _ = bloc_match_visualisation(
                    definition_precedente, taille
                )
                if ordre_precedent != ordre and participant.resultat == "perdant":
                    continue
                source_x, source_y = coordonnees[precedent.numero]
                direction = -1 if cote == "gauche" else 1
                source_x = source_x if direction < 0 else source_x + largeur_match
                cible_x = x + largeur_match if direction < 0 else x
                milieu_x = (source_x + cible_x) / 2
                canvas.create_line(
                    source_x, source_y, milieu_x, source_y,
                    milieu_x, y, cible_x, y, fill="#64748b",
                )
            canvas.create_rectangle(
                x, y - hauteur_match / 2, x + largeur_match, y + hauteur_match / 2,
                fill="#f8fafc", outline="#64748b",
            )
            canvas.create_text(
                x + 8, y - 23, anchor="nw",
                text="MATCH {} — {}".format(match.numero, match.niveau or ""),
                font=("TkDefaultFont", 9, "bold"),
            )
            canvas.create_text(
                x + 8, y - 3, anchor="nw", text=texte_participant(match.participant_1),
            )
            canvas.create_text(
                x + 8, y + 15, anchor="nw", text=texte_participant(match.participant_2),
            )
            classement = sorties_classement(definition)
            if classement:
                direction = -1 if cote == "gauche" else 1
                x_depart = x if direction < 0 else x + largeur_match
                x_fin = x_depart + direction * 65
                for rang, decalage_y in zip(classement, (-12, 12)):
                    canvas.create_line(x_depart, y + decalage_y, x_fin, y + decalage_y)
                    canvas.create_text(
                        x_fin + direction * 5, y + decalage_y,
                        anchor="w" if direction > 0 else "e",
                        text="{}{}".format(rang, "er" if rang == 1 else "e"),
                        font=("TkDefaultFont", 9, "bold"), fill="#1e3a5f",
                    )
        largeur = origine * 2 + largeur_match + 120
        hauteur = fin_y + 40
        canvas.configure(scrollregion=(0, 0, largeur, hauteur))

    def _creer_excel_solution(self):
        if self.solution_affichee is None or self.configuration_solutions is None:
            messagebox.showinfo(
                "Aucune solution", "Calculez d'abord une solution."
            )
            return
        initial = (
            Path(self.fichier_resultats_solutions).name
            if self.fichier_resultats_solutions
            else "solution.xlsx"
        )
        chemin = filedialog.asksaveasfilename(
            title="Créer le fichier Excel de solution",
            defaultextension=".xlsx",
            filetypes=(("Classeur Excel", "*.xlsx"),),
            initialfile=initial,
        )
        if not chemin:
            return
        try:
            creer_fichier_solution(
                chemin,
                self.solution_affichee,
                solutions=self.solutions or [self.solution_affichee],
                recap={
                    "configuration": self.config_var.get(),
                    "excel": self.excel_var.get(),
                    "mode": self.detail_mode_var.get(),
                    "recherche_terminee": self.solutions_recherche_terminee,
                },
                numero_tirage_choisi=self.numero_tirage_affiche,
                matchs=self.configuration_solutions.matchs,
            )
        except Exception as erreur:
            messagebox.showerror("Création impossible", str(erreur))
            return
        self.fichier_resultats_solutions = Path(chemin)
        messagebox.showinfo("Fichier créé", str(chemin))

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
        noms_modes = {
            "une": "Une seule solution",
            "toutes": "Toutes les solutions",
            "nombre": "Calcul de {} solutions maximum".format(limite),
        }
        self.detail_configuration_var.set(str(configuration))
        self.detail_excel_var.set(str(excel))
        self.detail_mode_var.set(noms_modes[mode])
        self.detail_etat_var.set(messages[mode])
        self.onglets.select(self.onglet_details)
        threading.Thread(
            target=self._calculer,
            args=(configuration, excel, mode, limite),
            daemon=True,
        ).start()

    def _calculer(self, chemin_configuration, chemin_excel, mode, limite):
        try:
            configuration = charger_configuration(chemin_configuration)
            classements = lire_classement(chemin_excel, configuration.onglet_excel)
            joueurs = creer_liste_joueurs(classements, configuration.nombre_positions)
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
                sortie = chemin_excel.with_name(chemin_excel.stem + "_solutions.xlsx")
                mode_recap = (
                    "Toutes les solutions"
                    if limite is None
                    else "Jusqu'à {} solutions".format(limite)
                )
                creer_fichier_solution(
                    sortie,
                    solutions[0],
                    solutions=solutions,
                    recap={
                        "configuration": str(chemin_configuration),
                        "excel": str(chemin_excel),
                        "mode": mode_recap,
                        "recherche_terminee": recherche_terminee,
                    },
                    numero_tirage_choisi=1,
                    matchs=configuration.matchs,
                )
                self.parent.after(
                    0,
                    self._toutes_solutions_terminees,
                    solutions,
                    chemin_excel,
                    configuration,
                    recherche_terminee,
                    self.arret_calcul.is_set(),
                    limite,
                    sortie,
                )
                return

            solution = resoudre(joueurs, configuration.contraintes, configuration.nombre_positions)
            if solution is None:
                raise ValueError("Aucune solution ne respecte toutes les contraintes.")
            sortie = chemin_excel.with_name(chemin_excel.stem + "_solution.xlsx")
            creer_fichier_solution(
                sortie,
                solution,
                recap={
                    "configuration": str(chemin_configuration),
                    "excel": str(chemin_excel),
                    "mode": "Une seule solution",
                    "recherche_terminee": True,
                },
                matchs=configuration.matchs,
            )
            self.parent.after(0, self._calcul_termine, sortie, solution, configuration)
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
        self.detail_etat_var.set(self.statut_var.get())

    def _arreter_calcul(self):
        self.arret_calcul.set()
        self.bouton_arreter.state(["disabled"])
        self.statut_var.set("Arrêt demandé… conservation des solutions déjà trouvées.")
        self.detail_etat_var.set(self.statut_var.get())

    def _toutes_solutions_terminees(
        self,
        solutions,
        chemin_excel,
        configuration,
        recherche_terminee,
        calcul_arrete,
        limite,
        sortie,
    ):
        self.solutions = solutions
        self.solutions_recherche_terminee = recherche_terminee
        self.chemin_excel_solutions = chemin_excel
        self.configuration_solutions = configuration
        self.fichier_resultats_solutions = sortie
        self._fin_traitement()
        self.bouton_solution_aleatoire.state(["!disabled"])
        self.bouton_creer_excel.state(["!disabled"])
        if calcul_arrete:
            resume = "Calcul arrêté : {} solutions conservées.".format(len(solutions))
        elif limite is not None and not recherche_terminee:
            resume = "Objectif atteint : {} solutions calculées.".format(len(solutions))
        else:
            resume = "Calcul terminé : {} solutions calculées.".format(len(solutions))
        self.statut_var.set(resume)
        self.detail_etat_var.set(resume)
        self._afficher_tirage(solutions[0])
        self._afficher_tableau(configuration, solutions[0])
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
        numero_tirage = random.randrange(len(self.solutions)) + 1
        solution = self.solutions[numero_tirage - 1]
        sortie = self.fichier_resultats_solutions
        try:
            mettre_a_jour_tirage_choisi(sortie, numero_tirage)
        except Exception as erreur:
            messagebox.showerror("Erreur", str(erreur))
            return
        self.statut_var.set("Solution aléatoire créée : {}".format(sortie))
        self.detail_etat_var.set(
            "Tirage n°{} choisi parmi {} solution{} trouvée{}. Fichier : {}".format(
                numero_tirage,
                len(self.solutions),
                "s" if len(self.solutions) > 1 else "",
                "s" if len(self.solutions) > 1 else "",
                sortie,
            )
        )
        self._afficher_tirage(solution, numero_tirage)
        self._afficher_tableau(self.configuration_solutions, solution)
        messagebox.showinfo(
            "Solution aléatoire",
            "Le tirage n°{} est maintenant sélectionné dans :\n{}".format(
                numero_tirage,
                sortie,
            ),
        )

    def _calcul_termine(self, sortie, solution, configuration):
        self.solutions = [solution]
        self.solutions_recherche_terminee = True
        self.configuration_solutions = configuration
        self.fichier_resultats_solutions = sortie
        self._fin_traitement()
        self.bouton_creer_excel.state(["!disabled"])
        self.statut_var.set("Calcul terminé : {}".format(sortie))
        self.detail_etat_var.set("Une solution trouvée. Fichier créé : {}".format(sortie))
        self._afficher_tirage(solution)
        self._afficher_tableau(configuration, solution)
        messagebox.showinfo("Calcul terminé", "Le fichier a été créé :\n{}".format(sortie))

    def _calcul_echoue(self, message):
        self._fin_traitement()
        self.statut_var.set("Échec du calcul.")
        self.detail_etat_var.set("Échec : {}".format(message))
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
    racine.geometry("1100x850")
    racine.minsize(760, 680)
    style = ttk.Style(racine)
    style.configure("Title.TLabel", font=("TkDefaultFont", 18, "bold"))
    style.configure("Accent.TButton", font=("TkDefaultFont", 11, "bold"))
    style.configure("DetailTitle.TLabel", font=("TkDefaultFont", 10, "bold"))
    Application(racine)
    racine.mainloop()


if __name__ == "__main__":
    main()
