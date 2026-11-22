"""Éditeur graphique des configurations JSON v2."""

import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .configuration_fichier import charger_configuration, enregistrer_configuration
from .generateur_tableau import generer_configuration_standard


TYPES_CONTRAINTES = (
    "poules_differentes",
    "clubs_differents",
    "rangs_match",
    "rangs_participants",
)


def parser_reference(texte):
    """Convertit ``position:3`` ou ``vainqueur:2`` en référence JSON."""
    morceaux = str(texte).strip().lower().split(":", 1)
    if len(morceaux) != 2 or morceaux[0] not in ("position", "vainqueur", "perdant"):
        raise ValueError("Référence attendue : position:N, vainqueur:N ou perdant:N")
    try:
        numero = int(morceaux[1])
    except ValueError as erreur:
        raise ValueError("Le numéro de la référence doit être un entier") from erreur
    if numero <= 0:
        raise ValueError("Le numéro de la référence doit être positif")
    return {
        "type": morceaux[0],
        "numero" if morceaux[0] == "position" else "match": numero,
    }


def formater_reference(reference):
    type_reference = reference.get("type", "")
    cle = "numero" if type_reference == "position" else "match"
    return "{}:{}".format(type_reference, reference.get(cle, ""))


def calculer_profondeurs_matchs(matchs):
    """Calcule la colonne graphique de chaque match et détecte les cycles."""
    par_numero = {int(match["numero"]): match for match in matchs}
    profondeurs = {}
    en_cours = set()

    def profondeur(numero):
        if numero in profondeurs:
            return profondeurs[numero]
        if numero in en_cours:
            raise ValueError("Cycle détecté autour du match {}".format(numero))
        if numero not in par_numero:
            raise ValueError("Match référencé introuvable : {}".format(numero))
        en_cours.add(numero)
        dependances = []
        for cle in ("participant_1", "participant_2"):
            reference = par_numero[numero].get(cle, {})
            if reference.get("type") in ("vainqueur", "perdant"):
                dependances.append(profondeur(int(reference.get("match", 0))))
        en_cours.remove(numero)
        profondeurs[numero] = 1 + max(dependances, default=0)
        return profondeurs[numero]

    for numero in par_numero:
        profondeur(numero)
    return profondeurs


def indices_contraintes_du_match(match, contraintes):
    """Retourne les contraintes visant directement le match ou son niveau."""
    resultat = []
    for index, contrainte in enumerate(contraintes):
        cible = contrainte.get("cible", {})
        correspond = (
            cible.get("type") == "match"
            and int(cible.get("numero", 0)) == int(match["numero"])
        ) or (
            cible.get("type") == "niveau"
            and str(cible.get("niveau", "")) == str(match.get("niveau", ""))
        )
        if correspond:
            resultat.append(index)
    return resultat


def _liste_entiers(texte, obligatoire=False):
    valeurs = [element.strip() for element in str(texte).split(",") if element.strip()]
    if obligatoire and not valeurs:
        raise ValueError("Au moins une valeur est obligatoire")
    try:
        resultat = [int(valeur) for valeur in valeurs]
    except ValueError as erreur:
        raise ValueError("Utilisez des nombres séparés par des virgules") from erreur
    if any(valeur <= 0 for valeur in resultat):
        raise ValueError("Les nombres doivent être positifs")
    return resultat


class _DialogueBase(tk.Toplevel):
    def __init__(self, parent, titre):
        super().__init__(parent)
        self.title(titre)
        self.transient(parent)
        self.resizable(False, False)
        self.resultat = None
        self.corps = ttk.Frame(self, padding=16)
        self.corps.grid(sticky="nsew")
        self.boutons = ttk.Frame(self, padding=(16, 0, 16, 16))
        self.boutons.grid(sticky="ew")
        ttk.Button(self.boutons, text="Annuler", command=self.destroy).pack(side="right")
        ttk.Button(self.boutons, text="Valider", command=self._valider).pack(
            side="right", padx=(0, 8)
        )
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def afficher(self):
        self.grab_set()
        self.wait_window()
        return self.resultat

    def _erreur(self, erreur):
        messagebox.showerror("Valeur invalide", str(erreur), parent=self)


class DialogueMatch(_DialogueBase):
    def __init__(self, parent, match=None, numero_suggere=1):
        super().__init__(parent, "Match")
        match = match or {}
        self.numero = tk.StringVar(value=str(match.get("numero", numero_suggere)))
        self.niveau = tk.StringVar(value=str(match.get("niveau", "")))
        self.participant_1 = tk.StringVar(
            value=formater_reference(match.get("participant_1", {"type": "position", "numero": 1}))
        )
        self.participant_2 = tk.StringVar(
            value=formater_reference(match.get("participant_2", {"type": "position", "numero": 2}))
        )
        self.places = tk.StringVar(
            value=",".join(str(valeur) for valeur in match.get("places", []))
        )
        champs = (
            ("Numéro", self.numero),
            ("Niveau", self.niveau),
            ("Participant 1", self.participant_1),
            ("Participant 2", self.participant_2),
            ("Places concernées", self.places),
        )
        for ligne, (libelle, variable) in enumerate(champs):
            ttk.Label(self.corps, text=libelle).grid(row=ligne, column=0, sticky="w", pady=4)
            ttk.Entry(self.corps, textvariable=variable, width=38).grid(
                row=ligne, column=1, sticky="ew", padx=(12, 0), pady=4
            )
        ttk.Label(
            self.corps,
            text="Références : position:1, vainqueur:2 ou perdant:2",
        ).grid(row=len(champs), column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _valider(self):
        try:
            numero = int(self.numero.get())
            if numero <= 0:
                raise ValueError("Le numéro du match doit être positif")
            self.resultat = {
                "numero": numero,
                "niveau": self.niveau.get().strip(),
                "places": _liste_entiers(self.places.get()),
                "participant_1": parser_reference(self.participant_1.get()),
                "participant_2": parser_reference(self.participant_2.get()),
            }
        except ValueError as erreur:
            self._erreur(erreur)
            return
        self.destroy()


class DialogueContrainte(_DialogueBase):
    def __init__(self, parent, contrainte=None):
        super().__init__(parent, "Contrainte")
        contrainte = contrainte or {}
        cible = contrainte.get("cible", {})
        self.type_contrainte = tk.StringVar(
            value=contrainte.get("type", TYPES_CONTRAINTES[0])
        )
        self.type_cible = tk.StringVar(value=cible.get("type", "match"))
        self.valeur_cible = tk.StringVar(
            value=str(cible.get("numero", cible.get("niveau", "")))
        )
        self.rangs = tk.StringVar(
            value=",".join(str(v) for v in contrainte.get("rangs", []))
        )
        self.rangs_1 = tk.StringVar(
            value=",".join(str(v) for v in contrainte.get("participant_1", []))
        )
        self.rangs_2 = tk.StringVar(
            value=",".join(str(v) for v in contrainte.get("participant_2", []))
        )
        ttk.Label(self.corps, text="Type").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(
            self.corps, textvariable=self.type_contrainte, values=TYPES_CONTRAINTES,
            state="readonly", width=30,
        ).grid(row=0, column=1, padx=(12, 0), pady=4)
        ttk.Label(self.corps, text="Cible").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(
            self.corps, textvariable=self.type_cible, values=("match", "niveau"),
            state="readonly", width=30,
        ).grid(row=1, column=1, padx=(12, 0), pady=4)
        champs = (
            ("N° match ou niveau", self.valeur_cible),
            ("Rangs du match", self.rangs),
            ("Rangs participant 1", self.rangs_1),
            ("Rangs participant 2", self.rangs_2),
        )
        for ligne, (libelle, variable) in enumerate(champs, start=2):
            ttk.Label(self.corps, text=libelle).grid(row=ligne, column=0, sticky="w", pady=4)
            ttk.Entry(self.corps, textvariable=variable, width=33).grid(
                row=ligne, column=1, padx=(12, 0), pady=4
            )
        ttk.Label(
            self.corps,
            text="Les rangs sont séparés par des virgules. Ils ne servent que pour les contraintes de rang.",
            wraplength=470,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _valider(self):
        try:
            type_cible = self.type_cible.get()
            valeur = self.valeur_cible.get().strip()
            if not valeur:
                raise ValueError("La cible est obligatoire")
            cible = {"type": type_cible}
            if type_cible == "match":
                cible["numero"] = int(valeur)
            else:
                cible["niveau"] = valeur
            resultat = {"type": self.type_contrainte.get(), "cible": cible}
            if resultat["type"] == "rangs_match":
                rangs = _liste_entiers(self.rangs.get(), obligatoire=True)
                if len(rangs) != 2:
                    raise ValueError("Indiquez exactement deux rangs")
                resultat["rangs"] = rangs
            elif resultat["type"] == "rangs_participants":
                resultat["participant_1"] = _liste_entiers(
                    self.rangs_1.get(), obligatoire=True
                )
                resultat["participant_2"] = _liste_entiers(
                    self.rangs_2.get(), obligatoire=True
                )
            self.resultat = resultat
        except ValueError as erreur:
            self._erreur(erreur)
            return
        self.destroy()


class EditeurConfiguration(tk.Toplevel):
    def __init__(self, parent, chemin=None, apres_enregistrement=None):
        super().__init__(parent)
        self.geometry("1050x720")
        self.minsize(820, 580)
        self.chemin = Path(chemin) if chemin else None
        self.apres_enregistrement = apres_enregistrement
        self.donnees = self._charger_donnees()
        self.nom_var = tk.StringVar()
        self.taille_var = tk.StringVar()
        self.integral_var = tk.BooleanVar()
        self.barrages_var = tk.BooleanVar()
        self.onglet_excel_var = tk.StringVar()
        self._construire()
        self._charger_variables()
        self._rafraichir_tout()
        self._mettre_a_jour_titre()

    def _charger_donnees(self):
        if self.chemin is None:
            return generer_configuration_standard(32)
        donnees = json.loads(self.chemin.read_text(encoding="utf-8"))
        if donnees.get("version") != 2:
            raise ValueError(
                "Cette configuration utilise l'ancien format v1. Créez une configuration v2 avant de l'éditer."
            )
        return donnees

    def _construire(self):
        barre_menu = tk.Menu(self)
        menu_fichier = tk.Menu(barre_menu, tearoff=False)
        menu_fichier.add_command(
            label="Nouveau",
            accelerator="Ctrl+N",
            command=self._nouveau_fichier,
        )
        menu_fichier.add_command(
            label="Ouvrir…",
            accelerator="Ctrl+O",
            command=self._ouvrir_fichier,
        )
        menu_fichier.add_separator()
        menu_fichier.add_command(
            label="Enregistrer",
            accelerator="Ctrl+S",
            command=self._enregistrer,
        )
        menu_fichier.add_command(
            label="Enregistrer sous…",
            accelerator="Ctrl+Maj+S",
            command=self._enregistrer_sous,
        )
        menu_fichier.add_separator()
        menu_fichier.add_command(label="Fermer", command=self.destroy)
        barre_menu.add_cascade(label="Fichier", menu=menu_fichier)
        self.configure(menu=barre_menu)
        self.bind("<Control-n>", lambda _e: self._nouveau_fichier())
        self.bind("<Control-o>", lambda _e: self._ouvrir_fichier())
        self.bind("<Control-s>", lambda _e: self._enregistrer())
        self.bind("<Control-Shift-S>", lambda _e: self._enregistrer_sous())

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.onglets = ttk.Notebook(self)
        self.onglets.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.onglet_general = ttk.Frame(self.onglets, padding=18)
        self.onglet_matchs = ttk.Frame(self.onglets, padding=12)
        self.onglet_contraintes = ttk.Frame(self.onglets, padding=12)
        self.onglet_visualisation = ttk.Frame(self.onglets, padding=8)
        self.onglet_json = ttk.Frame(self.onglets, padding=12)
        for cadre, titre in (
            (self.onglet_general, "Général"), (self.onglet_matchs, "Matchs"),
            (self.onglet_contraintes, "Contraintes"),
            (self.onglet_visualisation, "Visualisation"),
            (self.onglet_json, "Aperçu JSON"),
        ):
            self.onglets.add(cadre, text=titre)
        self.onglets.bind("<<NotebookTabChanged>>", self._onglet_change)
        self._construire_general()
        self.table_matchs = self._construire_liste(
            self.onglet_matchs,
            ("numero", "niveau", "participant_1", "participant_2", "places"),
            ("N°", "Niveau", "Participant 1", "Participant 2", "Places"),
            (60, 160, 180, 180, 130),
            self._ajouter_match, self._modifier_match, self._supprimer_match,
        )
        self.table_contraintes = self._construire_liste(
            self.onglet_contraintes,
            ("type", "cible", "parametres"),
            ("Type", "Cible", "Paramètres"),
            (230, 180, 420),
            self._ajouter_contrainte, self._modifier_contrainte, self._supprimer_contrainte,
        )
        self._construire_visualisation()
        self.texte_json = tk.Text(self.onglet_json, wrap="none", font=("TkFixedFont", 10))
        self.texte_json.pack(fill="both", expand=True)
        actions = ttk.Frame(self, padding=(12, 0, 12, 12))
        actions.grid(row=1, column=0, sticky="ew")
        ttk.Button(actions, text="Fermer", command=self.destroy).pack(side="right")
        ttk.Button(actions, text="Enregistrer sous…", command=self._enregistrer_sous).pack(
            side="right", padx=8
        )
        ttk.Button(actions, text="Enregistrer", command=self._enregistrer).pack(side="right")

    def _construire_general(self):
        champs = (
            ("Nom", self.nom_var),
            ("Taille du tableau", self.taille_var),
            ("Onglet Excel", self.onglet_excel_var),
        )
        for ligne, (libelle, variable) in enumerate(champs):
            ttk.Label(self.onglet_general, text=libelle).grid(row=ligne, column=0, sticky="w", pady=6)
            ttk.Entry(self.onglet_general, textvariable=variable, width=45).grid(
                row=ligne, column=1, sticky="ew", padx=(12, 0), pady=6
            )
        ttk.Checkbutton(
            self.onglet_general, text="Classement intégral", variable=self.integral_var
        ).grid(row=3, column=1, sticky="w", pady=6)
        ttk.Checkbutton(
            self.onglet_general,
            text="Jouer aussi les barrages 1er contre 4e",
            variable=self.barrages_var,
        ).grid(row=4, column=1, sticky="w", pady=6)
        ttk.Label(
            self.onglet_general,
            text=(
                "Non coché : barrage 2e–3e, puis le gagnant rejoint un 1er dans le tableau "
                "supérieur et le perdant un 4e dans le tableau inférieur."
            ),
            wraplength=650,
        ).grid(row=5, column=1, sticky="w", pady=(0, 8))
        ttk.Separator(self.onglet_general).grid(row=6, column=0, columnspan=2, sticky="ew", pady=16)
        ttk.Button(
            self.onglet_general, text="Régénérer la structure standard",
            command=self._regenerer_standard,
        ).grid(row=7, column=0, columnspan=2, sticky="ew", pady=5)
        ttk.Button(
            self.onglet_general, text="Partir de zéro (supprimer matchs et contraintes)",
            command=self._partir_de_zero,
        ).grid(row=8, column=0, columnspan=2, sticky="ew", pady=5)
        self.onglet_general.columnconfigure(1, weight=1)

    def _construire_liste(self, parent, colonnes, titres, largeurs, ajouter, modifier, supprimer):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        table = ttk.Treeview(parent, columns=colonnes, show="headings", selectmode="browse")
        for colonne, titre, largeur in zip(colonnes, titres, largeurs):
            table.heading(colonne, text=titre)
            table.column(colonne, width=largeur, minwidth=60)
        table.grid(row=0, column=0, sticky="nsew")
        barre = ttk.Scrollbar(parent, orient="vertical", command=table.yview)
        barre.grid(row=0, column=1, sticky="ns")
        table.configure(yscrollcommand=barre.set)
        table.bind("<Double-1>", lambda _e: modifier())
        boutons = ttk.Frame(parent)
        boutons.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Button(boutons, text="Ajouter", command=ajouter).pack(side="left")
        ttk.Button(boutons, text="Modifier", command=modifier).pack(side="left", padx=8)
        ttk.Button(boutons, text="Supprimer", command=supprimer).pack(side="left")
        return table

    def _construire_visualisation(self):
        self.onglet_visualisation.columnconfigure(0, weight=1)
        self.onglet_visualisation.columnconfigure(2, weight=0)
        self.onglet_visualisation.rowconfigure(1, weight=1)
        outils = ttk.Frame(self.onglet_visualisation)
        outils.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        ttk.Label(
            outils,
            text="Les places sont numérotées de haut en bas. V = vainqueur, P = perdant.",
        ).pack(side="left")
        ttk.Button(outils, text="Actualiser", command=self._rafraichir_visualisation).pack(
            side="right"
        )
        ttk.Button(outils, text="Zoom +", command=lambda: self._changer_zoom(0.15)).pack(
            side="right", padx=5
        )
        ttk.Button(outils, text="Zoom −", command=lambda: self._changer_zoom(-0.15)).pack(
            side="right"
        )
        self.zoom_visualisation = 1.0
        self.canvas_tableau = tk.Canvas(
            self.onglet_visualisation,
            background="white",
            highlightthickness=1,
            highlightbackground="#b8b8b8",
        )
        self.canvas_tableau.grid(row=1, column=0, sticky="nsew")
        barre_y = ttk.Scrollbar(
            self.onglet_visualisation, orient="vertical", command=self.canvas_tableau.yview
        )
        barre_y.grid(row=1, column=1, sticky="ns")
        barre_x = ttk.Scrollbar(
            self.onglet_visualisation, orient="horizontal", command=self.canvas_tableau.xview
        )
        barre_x.grid(row=2, column=0, sticky="ew")
        self.canvas_tableau.configure(
            xscrollcommand=barre_x.set,
            yscrollcommand=barre_y.set,
        )

        panneau = ttk.LabelFrame(
            self.onglet_visualisation,
            text="Contraintes du tableau",
            padding=8,
        )
        panneau.grid(row=1, column=2, rowspan=2, sticky="nsew", padx=(10, 0))
        panneau.rowconfigure(0, weight=1)
        panneau.columnconfigure(0, weight=1)
        self.table_contraintes_visu = ttk.Treeview(
            panneau,
            columns=("type", "cible"),
            show="headings",
            selectmode="browse",
        )
        self.table_contraintes_visu.heading("type", text="Type")
        self.table_contraintes_visu.heading("cible", text="Cible")
        self.table_contraintes_visu.column("type", width=185, minwidth=130)
        self.table_contraintes_visu.column("cible", width=130, minwidth=90)
        self.table_contraintes_visu.grid(row=0, column=0, sticky="nsew")
        barre_contraintes = ttk.Scrollbar(
            panneau,
            orient="vertical",
            command=self.table_contraintes_visu.yview,
        )
        barre_contraintes.grid(row=0, column=1, sticky="ns")
        self.table_contraintes_visu.configure(yscrollcommand=barre_contraintes.set)
        self.table_contraintes_visu.bind(
            "<<TreeviewSelect>>",
            lambda _e: self._rafraichir_visualisation(),
        )
        self.table_contraintes_visu.bind(
            "<Double-1>",
            lambda _e: self._modifier_contrainte(self.table_contraintes_visu),
        )
        boutons = ttk.Frame(panneau)
        boutons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(boutons, text="Ajouter", command=self._ajouter_contrainte).pack(
            side="left"
        )
        ttk.Button(
            boutons,
            text="Modifier",
            command=lambda: self._modifier_contrainte(self.table_contraintes_visu),
        ).pack(side="left", padx=5)
        ttk.Button(
            boutons,
            text="Supprimer",
            command=lambda: self._supprimer_contrainte(self.table_contraintes_visu),
        ).pack(side="left")

    def _onglet_change(self, _evenement=None):
        self._rafraichir_json()
        if self.onglets.select() == str(self.onglet_visualisation):
            self._rafraichir_visualisation()

    def _changer_zoom(self, delta):
        self.zoom_visualisation = min(2.0, max(0.55, self.zoom_visualisation + delta))
        self._rafraichir_visualisation()

    def _rafraichir_visualisation(self):
        if not hasattr(self, "canvas_tableau"):
            return
        canvas = self.canvas_tableau
        canvas.delete("all")
        index_contrainte_selectionnee = None
        if hasattr(self, "table_contraintes_visu"):
            selection = self.table_contraintes_visu.selection()
            if selection:
                index_contrainte_selectionnee = int(selection[0])
        try:
            self._synchroniser_general()
            taille = int(self.donnees.get("taille_tableau", 0))
            matchs = self.donnees.get("matchs", [])
            profondeurs = calculer_profondeurs_matchs(matchs)
            if not matchs:
                raise ValueError("Ajoutez au moins un match pour afficher le tableau")
        except Exception as erreur:
            canvas.create_text(
                25, 25, anchor="nw", text="Visualisation impossible : {}".format(erreur),
                fill="#b00020", font=("TkDefaultFont", 11, "bold"),
            )
            canvas.configure(scrollregion=(0, 0, 800, 300))
            return

        z = self.zoom_visualisation
        marge_x, marge_y = 45 * z, 60 * z
        pas_joueur = 36 * z
        largeur_match, hauteur_match = 150 * z, 42 * z
        pas_colonne, espace_match = 235 * z, 56 * z
        positions_coordonnees = {
            numero: (marge_x, marge_y + (numero - 1) * pas_joueur)
            for numero in range(1, taille + 1)
        }
        for numero, (x, y) in positions_coordonnees.items():
            canvas.create_text(
                x, y, text=str(numero), anchor="e",
                font=("TkDefaultFont", max(8, int(10 * z)), "bold"), fill="#333333",
            )
            canvas.create_line(x + 8 * z, y, x + 50 * z, y, fill="#8a8a8a")

        par_numero = {int(match["numero"]): match for match in matchs}
        coordonnees_matchs = {}

        def coordonnee_source(reference):
            type_reference = reference.get("type")
            if type_reference == "position":
                numero = int(reference.get("numero", 0))
                if numero not in positions_coordonnees:
                    raise ValueError("Position introuvable : {}".format(numero))
                x, y = positions_coordonnees[numero]
                return x + 50 * z, y
            numero_match = int(reference.get("match", 0))
            if numero_match not in coordonnees_matchs:
                raise ValueError("Match précédent non positionné : {}".format(numero_match))
            x, y = coordonnees_matchs[numero_match]
            return x + largeur_match, y

        profondeur_max = max(profondeurs.values(), default=1)
        for profondeur in range(1, profondeur_max + 1):
            groupe = [
                match for match in matchs
                if profondeurs[int(match["numero"])] == profondeur
            ]
            souhaits = []
            for match in groupe:
                sources = [
                    coordonnee_source(match.get("participant_1", {})),
                    coordonnee_source(match.get("participant_2", {})),
                ]
                souhaits.append((sum(source[1] for source in sources) / 2, match, sources))
            souhaits.sort(key=lambda element: element[0])
            precedent_y = marge_y - espace_match
            for souhaite_y, match, sources in souhaits:
                y = max(souhaite_y, precedent_y + espace_match)
                precedent_y = y
                x = marge_x + 85 * z + (profondeur - 1) * pas_colonne
                coordonnees_matchs[int(match["numero"])] = (x, y)
                for index, (source_x, source_y) in enumerate(sources, start=1):
                    cible_y = y - hauteur_match * 0.23 if index == 1 else y + hauteur_match * 0.23
                    milieu_x = (source_x + x) / 2
                    canvas.create_line(
                        source_x, source_y, milieu_x, source_y, milieu_x, cible_y, x, cible_y,
                        fill="#5f6368", width=max(1, int(z)),
                    )
                    reference = match.get("participant_{}".format(index), {})
                    if reference.get("type") in ("vainqueur", "perdant"):
                        canvas.create_text(
                            source_x + 7 * z, source_y - 7 * z,
                            text="V" if reference["type"] == "vainqueur" else "P",
                            anchor="w", fill="#166534" if reference["type"] == "vainqueur" else "#9a3412",
                            font=("TkDefaultFont", max(7, int(8 * z)), "bold"),
                        )
                couleur = "#dbeafe" if str(match.get("niveau", "")).startswith("1/") or match.get("niveau") == "finale" else "#fef3c7"
                contraintes_match = indices_contraintes_du_match(
                    match, self.donnees.get("contraintes", [])
                )
                selectionne = index_contrainte_selectionnee in contraintes_match
                contour = "#dc2626" if contraintes_match else "#3f3f46"
                if selectionne:
                    contour = "#ea580c"
                canvas.create_rectangle(
                    x, y - hauteur_match / 2, x + largeur_match, y + hauteur_match / 2,
                    fill=couleur,
                    outline=contour,
                    width=max(1, int((3 if selectionne else 2 if contraintes_match else 1) * z)),
                )
                canvas.create_text(
                    x + 8 * z, y - 8 * z, anchor="w",
                    text="MATCH {}".format(match["numero"]),
                    font=("TkDefaultFont", max(8, int(10 * z)), "bold"),
                )
                canvas.create_text(
                    x + 8 * z, y + 9 * z, anchor="w",
                    text=str(match.get("niveau", "")), fill="#52525b",
                    font=("TkDefaultFont", max(7, int(9 * z))),
                )
                if contraintes_match:
                    canvas.create_oval(
                        x + largeur_match - 25 * z,
                        y - 17 * z,
                        x + largeur_match - 7 * z,
                        y + 1 * z,
                        fill="#dc2626" if not selectionne else "#ea580c",
                        outline="",
                    )
                    canvas.create_text(
                        x + largeur_match - 16 * z,
                        y - 8 * z,
                        text=str(len(contraintes_match)),
                        fill="white",
                        font=("TkDefaultFont", max(7, int(8 * z)), "bold"),
                    )

        hauteur = max(
            marge_y + taille * pas_joueur,
            max((y for _x, y in coordonnees_matchs.values()), default=0) + 100 * z,
        )
        largeur = marge_x + 150 * z + profondeur_max * pas_colonne
        canvas.configure(scrollregion=(0, 0, largeur, hauteur))

    def _charger_variables(self):
        self.nom_var.set(self.donnees.get("nom", ""))
        self.taille_var.set(str(self.donnees.get("taille_tableau", 32)))
        self.integral_var.set(bool(self.donnees.get("classement_integral", False)))
        self.barrages_var.set(bool(self.donnees.get("barrages_1_contre_4", False)))
        self.onglet_excel_var.set(self.donnees.get("onglet_excel", "classement poules"))

    def _mettre_a_jour_titre(self):
        nom = self.chemin.name if self.chemin else "Nouvelle configuration"
        self.title("Éditeur de configuration — {}".format(nom))

    def _remplacer_configuration(self, donnees, chemin=None):
        self.donnees = donnees
        self.chemin = Path(chemin) if chemin else None
        self._charger_variables()
        self._rafraichir_tout()
        self._mettre_a_jour_titre()

    def _nouveau_fichier(self):
        if not messagebox.askyesno(
            "Nouvelle configuration",
            "Créer une nouvelle configuration ? Les modifications non enregistrées seront perdues.",
            parent=self,
        ):
            return
        self._remplacer_configuration(generer_configuration_standard(32))

    def _ouvrir_fichier(self):
        chemin = filedialog.askopenfilename(
            parent=self,
            title="Ouvrir une configuration",
            filetypes=(("Configuration JSON", "*.json"), ("Tous les fichiers", "*.*")),
        )
        if not chemin:
            return
        try:
            donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
            if donnees.get("version") != 2:
                raise ValueError(
                    "Ce fichier utilise l'ancien format v1 et ne peut pas être édité visuellement."
                )
            # La validation complète est effectuée sans modifier le fichier.
            charger_configuration(Path(chemin))
        except Exception as erreur:
            messagebox.showerror("Ouverture impossible", str(erreur), parent=self)
            return
        self._remplacer_configuration(donnees, chemin)

    def _synchroniser_general(self):
        taille = int(self.taille_var.get())
        if taille < 2:
            raise ValueError("La taille doit être supérieure ou égale à 2")
        self.donnees.update({
            "version": 2,
            "nom": self.nom_var.get().strip(),
            "taille_tableau": taille,
            "classement_integral": bool(self.integral_var.get()),
            "barrages_1_contre_4": bool(self.barrages_var.get()),
            "onglet_excel": self.onglet_excel_var.get().strip() or "classement poules",
        })

    def _rafraichir_tout(self):
        self._rafraichir_matchs()
        self._rafraichir_contraintes()
        self._rafraichir_visualisation()
        self._rafraichir_json()

    def _rafraichir_matchs(self):
        self.table_matchs.delete(*self.table_matchs.get_children())
        for index, match in enumerate(self.donnees.get("matchs", [])):
            self.table_matchs.insert("", "end", iid=str(index), values=(
                match.get("numero"), match.get("niveau", ""),
                formater_reference(match.get("participant_1", {})),
                formater_reference(match.get("participant_2", {})),
                ", ".join(str(v) for v in match.get("places", [])),
            ))

    def _description_contrainte(self, contrainte):
        type_contrainte = contrainte.get("type")
        if type_contrainte == "rangs_match":
            return "Rangs : {}".format(", ".join(map(str, contrainte.get("rangs", []))))
        if type_contrainte == "rangs_participants":
            return "P1 : {} ; P2 : {}".format(
                ", ".join(map(str, contrainte.get("participant_1", []))),
                ", ".join(map(str, contrainte.get("participant_2", []))),
            )
        return ""

    def _rafraichir_contraintes(self):
        self.table_contraintes.delete(*self.table_contraintes.get_children())
        if hasattr(self, "table_contraintes_visu"):
            self.table_contraintes_visu.delete(
                *self.table_contraintes_visu.get_children()
            )
        for index, contrainte in enumerate(self.donnees.get("contraintes", [])):
            cible = contrainte.get("cible", {})
            valeur = cible.get("numero", cible.get("niveau", ""))
            texte_cible = "{} : {}".format(cible.get("type", ""), valeur)
            self.table_contraintes.insert("", "end", iid=str(index), values=(
                contrainte.get("type", ""),
                texte_cible,
                self._description_contrainte(contrainte),
            ))
            if hasattr(self, "table_contraintes_visu"):
                self.table_contraintes_visu.insert(
                    "",
                    "end",
                    iid=str(index),
                    values=(contrainte.get("type", ""), texte_cible),
                )

    def _rafraichir_json(self):
        try:
            self._synchroniser_general()
        except (TypeError, ValueError):
            pass
        if not hasattr(self, "texte_json"):
            return
        self.texte_json.configure(state="normal")
        self.texte_json.delete("1.0", "end")
        self.texte_json.insert("1.0", json.dumps(self.donnees, ensure_ascii=False, indent=2))
        self.texte_json.configure(state="disabled")

    def _index_selectionne(self, table):
        selection = table.selection()
        return int(selection[0]) if selection else None

    def _ajouter_match(self):
        numeros = [m.get("numero", 0) for m in self.donnees.get("matchs", [])]
        match = DialogueMatch(self, numero_suggere=max(numeros, default=0) + 1).afficher()
        if match:
            self.donnees.setdefault("matchs", []).append(match)
            self._rafraichir_tout()

    def _modifier_match(self):
        index = self._index_selectionne(self.table_matchs)
        if index is None:
            return
        match = DialogueMatch(self, self.donnees["matchs"][index]).afficher()
        if match:
            self.donnees["matchs"][index] = match
            self._rafraichir_tout()

    def _supprimer_match(self):
        index = self._index_selectionne(self.table_matchs)
        if index is not None and messagebox.askyesno(
            "Supprimer le match", "Supprimer le match sélectionné ?", parent=self
        ):
            del self.donnees["matchs"][index]
            self._rafraichir_tout()

    def _ajouter_contrainte(self):
        contrainte = DialogueContrainte(self).afficher()
        if contrainte:
            self.donnees.setdefault("contraintes", []).append(contrainte)
            self._rafraichir_tout()

    def _modifier_contrainte(self, table=None):
        table = table or self.table_contraintes
        index = self._index_selectionne(table)
        if index is None:
            return
        contrainte = DialogueContrainte(self, self.donnees["contraintes"][index]).afficher()
        if contrainte:
            self.donnees["contraintes"][index] = contrainte
            self._rafraichir_tout()

    def _supprimer_contrainte(self, table=None):
        table = table or self.table_contraintes
        index = self._index_selectionne(table)
        if index is not None and messagebox.askyesno(
            "Supprimer la contrainte", "Supprimer la contrainte sélectionnée ?", parent=self
        ):
            del self.donnees["contraintes"][index]
            self._rafraichir_tout()

    def _regenerer_standard(self):
        if not messagebox.askyesno(
            "Régénérer", "Les matchs et contraintes actuels seront remplacés. Continuer ?", parent=self
        ):
            return
        try:
            taille = int(self.taille_var.get())
            nouvelles = generer_configuration_standard(
                taille,
                classement_integral=self.integral_var.get(),
                barrages_1_contre_4=self.barrages_var.get(),
                nom=self.nom_var.get().strip() or None,
            )
            nouvelles["onglet_excel"] = self.onglet_excel_var.get().strip() or "classement poules"
        except ValueError as erreur:
            messagebox.showerror("Génération impossible", str(erreur), parent=self)
            return
        self.donnees = nouvelles
        self._charger_variables()
        self._rafraichir_tout()

    def _partir_de_zero(self):
        if messagebox.askyesno(
            "Partir de zéro", "Supprimer tous les matchs et toutes les contraintes ?", parent=self
        ):
            self.donnees["format"] = "personnalise"
            self.donnees["matchs"] = []
            self.donnees["contraintes"] = []
            self._rafraichir_tout()

    def _enregistrer_sous(self):
        chemin = filedialog.asksaveasfilename(
            parent=self, title="Enregistrer la configuration", defaultextension=".json",
            filetypes=(("Configuration JSON", "*.json"),),
            initialfile=self.chemin.name if self.chemin else "nouvelle_configuration.json",
        )
        if chemin:
            self._enregistrer(Path(chemin))

    def _enregistrer(self, chemin=None):
        if isinstance(chemin, bool):
            chemin = None
        chemin = Path(chemin) if chemin else self.chemin
        if chemin is None:
            self._enregistrer_sous()
            return
        try:
            self._synchroniser_general()
            enregistrer_configuration(chemin, self.donnees)
        except Exception as erreur:
            messagebox.showerror("Configuration invalide", str(erreur), parent=self)
            return
        self.chemin = chemin
        self._mettre_a_jour_titre()
        if self.apres_enregistrement:
            self.apres_enregistrement(chemin)
        messagebox.showinfo("Configuration enregistrée", str(chemin), parent=self)


def ouvrir_editeur(parent, chemin=None, apres_enregistrement=None):
    try:
        return EditeurConfiguration(parent, chemin, apres_enregistrement)
    except Exception as erreur:
        messagebox.showerror("Ouverture impossible", str(erreur), parent=parent)
        return None


def main():
    """Lance directement l'éditeur, indépendamment de l'écran de calcul."""
    racine = tk.Tk()
    racine.withdraw()
    chemin = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else None
    editeur = ouvrir_editeur(racine, chemin=chemin)
    if editeur is None:
        racine.destroy()
        return

    def fermer():
        racine.destroy()

    editeur.protocol("WM_DELETE_WINDOW", fermer)
    editeur.bind(
        "<Destroy>",
        lambda evenement: racine.destroy() if evenement.widget is editeur else None,
        add="+",
    )
    racine.mainloop()


if __name__ == "__main__":
    main()
