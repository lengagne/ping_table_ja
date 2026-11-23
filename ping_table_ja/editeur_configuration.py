"""Éditeur graphique des configurations JSON v2."""

import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .configuration_fichier import charger_configuration, enregistrer_configuration
from .generateur_tableau import generer_configuration_standard


TYPES_CONTRAINTES = (
    "rangs_position",
    "poules_differentes",
    "clubs_differents",
    "rangs_meme_poule_interdits",
    "rangs_match",
    "rangs_participants",
)


DESCRIPTIONS_CONTRAINTES = {
    "rangs_position": (
        "Limite le rang et, si souhaité, la poule du joueur placé à cette position.",
        "Exemple : position 1, rang 1, poule 1 — la place 1 recevra le premier de la poule 1. "
        "Laissez les poules vides pour accepter toutes les poules.",
    ),
    "poules_differentes": (
        "Interdit que les deux participants possibles d'un match proviennent de la même poule.",
        "Aucun rang à saisir. Ciblez un match, plusieurs matchs ou un niveau complet.",
    ),
    "clubs_differents": (
        "Impose des clubs différents entre les deux participants possibles d'un match.",
        "Aucun rang à saisir. La règle peut viser un match, un ensemble ou un niveau.",
    ),
    "rangs_meme_poule_interdits": (
        "Interdit que deux rangs précis d'une même poule se rencontrent.",
        "Exemple : rangs 1,3 — un 1er et un 3e peuvent se rencontrer seulement "
        "s'ils viennent de poules différentes.",
    ),
    "rangs_match": (
        "Impose les deux rangs présents dans un match, sans imposer leur côté.",
        "Exemple : rangs 1,4 — le match opposera un 1er à un 4e de poule.",
    ),
    "rangs_participants": (
        "Définit séparément les rangs autorisés pour le participant 1 et le participant 2.",
        "Exemple : participant 1 = 1 ; participant 2 = 2,3 — un 1er jouera un 2e ou un 3e.",
    ),
}


DESCRIPTIONS_CIBLES = {
    "position": "La valeur de cible est le numéro de la position, par exemple 12.",
    "match": "La valeur de cible est le numéro d'un match, par exemple 7.",
    "matchs": "Saisissez plusieurs numéros de matchs séparés par des virgules : 3,7,12.",
    "niveau": (
        "Choisissez la colonne graphique complète : Niveau 1, Niveau 2, etc. "
        "Le champ « Matchs exclus » permet de surcharger la règle pour certains matchs."
    ),
}

LIBELLES_CIBLES = {
    "position": "Position",
    "match": "Un seul match",
    "matchs": "Plusieurs matchs",
    "niveau": "Niveau complet",
}
TYPES_CIBLES_PAR_LIBELLE = {libelle: cle for cle, libelle in LIBELLES_CIBLES.items()}


def aide_contrainte(type_contrainte, type_cible):
    description, exemple = DESCRIPTIONS_CONTRAINTES.get(
        type_contrainte,
        ("Type de contrainte inconnu.", ""),
    )
    cible = DESCRIPTIONS_CIBLES.get(type_cible, "Choisissez une cible.")
    return "{}\n{}\n{}".format(description, cible, exemple).strip()


def preparer_donnees_enregistrement(donnees, aucune_contrainte=False):
    """Prépare le JSON final sans enregistrer d'option transitoire."""
    resultat = json.loads(json.dumps(donnees, ensure_ascii=False))
    resultat.pop("aucune_contrainte", None)
    if aucune_contrainte:
        resultat["contraintes"] = []
    return resultat


def ajouter_contrainte_donnees(donnees, contrainte):
    """Ajoute une contrainte et indique que la configuration en contient."""
    donnees.setdefault("contraintes", []).append(contrainte)
    return False


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


def abscisse_match_visualisation(
    profondeur, places, taille_tableau, vue_compacte, origine, pas_colonne
):
    """Place les barrages au centre et déploie les deux tableaux en miroir."""
    if vue_compacte or not places:
        return origine + (profondeur - 1) * pas_colonne
    milieu = taille_tableau // 2
    direction = -1 if min(places) > milieu else 1
    return origine + direction * (profondeur - 1) * pas_colonne


def zone_match_visualisation(match, taille_tableau):
    """Classe un match dans la branche et la zone verticale non compactes."""
    places = [int(place) for place in match.get("places", [])]
    if match.get("niveau") == "barrage_2_3" or not places:
        return "centre"
    milieu = taille_tableau // 2
    gauche = min(places) > milieu
    debut_branche = milieu + 1 if gauche else 1
    principal = min(places) == debut_branche
    if gauche:
        return "gauche_principal" if principal else "gauche_classement"
    return "droite_principal" if principal else "droite_classement"


def indices_contraintes_du_match(match, contraintes, profondeur=None):
    """Retourne les contraintes visant directement le match ou son niveau."""
    resultat = []
    for index, contrainte in enumerate(contraintes):
        cible = contrainte.get("cible", {})
        correspond = (
            cible.get("type") == "match"
            and int(cible.get("numero", 0)) == int(match["numero"])
        ) or (
            cible.get("type") == "matchs"
            and int(match["numero"]) in [int(n) for n in cible.get("numeros", [])]
        ) or (
            cible.get("type") == "niveau"
            and (
                ("numero" in cible and int(cible.get("numero", 0)) == profondeur)
                or (
                    "numero" not in cible
                    and str(cible.get("niveau", "")) == str(match.get("niveau", ""))
                )
            )
            and int(match["numero"]) not in {
                int(numero) for numero in cible.get("exclusions_matchs", [])
            }
        )
        if correspond:
            resultat.append(index)
    return resultat


def indices_contraintes_de_position(numero_position, contraintes):
    return [
        index
        for index, contrainte in enumerate(contraintes)
        if contrainte.get("cible", {}).get("type") == "position"
        and int(contrainte.get("cible", {}).get("numero", 0)) == int(numero_position)
    ]


def indices_contraintes_pour_cible(cible, contraintes, matchs):
    """Retourne une seule fois chaque contrainte liée à la cible cliquée."""
    if not cible:
        return list(range(len(contraintes)))
    if cible.get("type") == "position":
        return indices_contraintes_de_position(cible["numero"], contraintes)
    profondeurs = calculer_profondeurs_matchs(matchs)
    if cible.get("type") == "niveau":
        numeros = [
            numero for numero, profondeur in profondeurs.items()
            if profondeur == int(cible["numero"])
        ]
    else:
        numeros = (
            [cible["numero"]]
            if cible.get("type") == "match"
            else cible.get("numeros", [])
        )
    par_numero = {int(match["numero"]): match for match in matchs}
    return sorted({
        index
        for numero in numeros
        if int(numero) in par_numero
        for index in indices_contraintes_du_match(
            par_numero[int(numero)], contraintes, profondeurs[int(numero)]
        )
    })


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
        self.parent_dialogue = parent
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
    def __init__(self, parent, contrainte=None, cible_initiale=None):
        super().__init__(parent, "Contrainte")
        self.geometry("760x540")
        self.minsize(620, 430)
        self.resizable(True, True)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.corps.rowconfigure(8, weight=1)
        contrainte = contrainte or {}
        cible = contrainte.get("cible", cible_initiale or {})
        type_par_defaut = (
            "rangs_position" if cible.get("type") == "position" else "poules_differentes"
        )
        self.type_contrainte = tk.StringVar(
            value=contrainte.get("type", type_par_defaut)
        )
        self.type_cible = tk.StringVar(value=cible.get("type", "match"))
        self.type_cible_affiche = tk.StringVar(
            value=LIBELLES_CIBLES[self.type_cible.get()]
        )
        self.exclusions_matchs = list(cible.get("exclusions_matchs", []))
        self.exclusions_var = tk.StringVar(
            value=",".join(str(numero) for numero in self.exclusions_matchs)
        )
        valeur_cible = cible.get("numero", cible.get("niveau", ""))
        if cible.get("type") == "niveau" and "numero" in cible:
            valeur_cible = "Niveau {}".format(cible["numero"])
        if cible.get("type") == "matchs":
            valeur_cible = ",".join(str(n) for n in cible.get("numeros", []))
        self.valeur_cible = tk.StringVar(value=str(valeur_cible))
        self.rangs = tk.StringVar(
            value=",".join(str(v) for v in contrainte.get("rangs", []))
        )
        self.poules = tk.StringVar(
            value=",".join(str(v) for v in contrainte.get("poules", []))
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
        ).grid(row=0, column=1, padx=(12, 0), pady=4, sticky="ew")
        ttk.Label(self.corps, text="Cible").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(
            self.corps,
            textvariable=self.type_cible_affiche,
            values=tuple(LIBELLES_CIBLES.values()),
            state="readonly", width=30,
        ).grid(row=1, column=1, padx=(12, 0), pady=4, sticky="ew")
        self.libelle_cible = ttk.Label(self.corps, text="Cible")
        self.libelle_cible.grid(row=2, column=0, sticky="w", pady=4)
        self.entree_cible = ttk.Combobox(
            self.corps, textvariable=self.valeur_cible, width=33
        )
        self.entree_cible.grid(row=2, column=1, padx=(12, 0), pady=4, sticky="ew")
        champs = (
            ("Rangs du match", self.rangs),
            ("Poules autorisées", self.poules),
            ("Rangs participant 1", self.rangs_1),
            ("Rangs participant 2", self.rangs_2),
            ("Matchs exclus du niveau", self.exclusions_var),
        )
        self.entrees_parametres = []
        for ligne, (libelle, variable) in enumerate(champs, start=3):
            etiquette = ttk.Label(self.corps, text=libelle)
            etiquette.grid(row=ligne, column=0, sticky="w", pady=4)
            entree = ttk.Entry(self.corps, textvariable=variable, width=33)
            entree.grid(
                row=ligne, column=1, padx=(12, 0), pady=4, sticky="ew"
            )
            self.entrees_parametres.append((variable, etiquette, entree))
            if variable is self.rangs:
                self.etiquette_rangs = etiquette
        cadre_aide = ttk.LabelFrame(self.corps, text="Comment remplir cette contrainte", padding=10)
        cadre_aide.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self.aide_var = tk.StringVar()
        ttk.Label(
            cadre_aide,
            textvariable=self.aide_var,
            wraplength=560,
            justify="left",
        ).pack(fill="x")
        self.corps.columnconfigure(1, weight=1)
        self.type_contrainte.trace_add("write", lambda *_args: self._mettre_a_jour_aide())
        self.type_cible_affiche.trace_add(
            "write", lambda *_args: self._changer_type_cible()
        )
        self._mettre_a_jour_aide()

    def _changer_type_cible(self):
        nouveau_type = TYPES_CIBLES_PAR_LIBELLE.get(
            self.type_cible_affiche.get(), "match"
        )
        if nouveau_type != self.type_cible.get():
            self.type_cible.set(nouveau_type)
            self.valeur_cible.set("")
            self.exclusions_var.set("")
        self._mettre_a_jour_aide()

    def _mettre_a_jour_aide(self):
        type_contrainte = self.type_contrainte.get()
        type_cible = self.type_cible.get()
        self.aide_var.set(aide_contrainte(type_contrainte, type_cible))
        matchs = getattr(self.parent_dialogue, "donnees", {}).get("matchs", [])
        libelles = {
            "position": "Numéro de position",
            "match": "Numéro du match",
            "matchs": "Numéros des matchs",
            "niveau": "Niveau du tableau",
        }
        self.libelle_cible.configure(text=libelles[type_cible])
        if type_cible == "niveau":
            profondeurs = calculer_profondeurs_matchs(matchs)
            valeurs = [
                "Niveau {}".format(numero)
                for numero in range(1, max(profondeurs.values(), default=0) + 1)
            ]
            valeur_actuelle = self.valeur_cible.get()
            if valeur_actuelle and valeur_actuelle not in valeurs:
                valeurs.append(valeur_actuelle)
            etat = "readonly"
        elif type_cible == "match":
            valeurs = [str(match["numero"]) for match in matchs]
            etat = "readonly"
        elif type_cible == "position":
            taille = int(getattr(self.parent_dialogue, "donnees", {}).get("taille_tableau", 0))
            valeurs = [str(numero) for numero in range(1, taille + 1)]
            etat = "readonly"
        else:
            valeurs = []
            etat = "normal"
        self.entree_cible.configure(values=valeurs, state=etat)
        libelles_rangs = {
            "rangs_position": "Rangs de poule autorisés",
            "rangs_match": "Rangs de poule du match",
            "rangs_meme_poule_interdits": "Rangs de poule interdits",
        }
        self.etiquette_rangs.configure(
            text=libelles_rangs.get(type_contrainte, "Rangs de poule")
        )
        champs_actifs = {
            "rangs_position": [self.rangs, self.poules],
            "rangs_match": [self.rangs],
            "rangs_meme_poule_interdits": [self.rangs],
            "rangs_participants": [self.rangs_1, self.rangs_2],
        }.get(type_contrainte, [])
        for variable, etiquette, entree in self.entrees_parametres:
            visible = (
                (variable is self.exclusions_var and type_cible == "niveau")
                or any(variable is active for active in champs_actifs)
            )
            if visible:
                etiquette.grid()
                entree.grid()
            else:
                etiquette.grid_remove()
                entree.grid_remove()

    def _valider(self):
        try:
            type_cible = self.type_cible.get()
            valeur = self.valeur_cible.get().strip()
            if not valeur:
                raise ValueError("La cible est obligatoire")
            cible = {"type": type_cible}
            if type_cible == "match":
                cible["numero"] = int(valeur)
            elif type_cible == "position":
                cible["numero"] = int(valeur)
            elif type_cible == "matchs":
                numeros = _liste_entiers(valeur, obligatoire=True)
                matchs = {
                    int(match["numero"]): match
                    for match in getattr(self.parent_dialogue, "donnees", {}).get("matchs", [])
                }
                niveaux = {
                    str(matchs[numero].get("niveau", ""))
                    for numero in numeros if numero in matchs
                }
                if len(niveaux) > 1:
                    raise ValueError(
                        "Sélectionnez uniquement des matchs du même niveau"
                    )
                cible["numeros"] = numeros
            else:
                if valeur.lower().startswith("niveau "):
                    cible["numero"] = int(valeur.split(None, 1)[1])
                else:
                    # Ancienne cible nommée conservée lors de sa modification.
                    cible["niveau"] = valeur
                exclusions = _liste_entiers(self.exclusions_var.get())
                if exclusions:
                    cible["exclusions_matchs"] = sorted(set(exclusions))
            resultat = {"type": self.type_contrainte.get(), "cible": cible}
            if resultat["type"] == "rangs_position" and type_cible != "position":
                raise ValueError("La contrainte rangs_position doit cibler une position")
            if type_cible == "position" and resultat["type"] != "rangs_position":
                raise ValueError("Une position accepte actuellement une contrainte de rang")
            if resultat["type"] in (
                "rangs_match", "rangs_position", "rangs_meme_poule_interdits"
            ):
                rangs = _liste_entiers(self.rangs.get(), obligatoire=True)
                if resultat["type"] in (
                    "rangs_match", "rangs_meme_poule_interdits"
                ) and len(rangs) != 2:
                    raise ValueError("Indiquez exactement deux rangs")
                resultat["rangs"] = rangs
                if resultat["type"] == "rangs_position":
                    poules = _liste_entiers(self.poules.get())
                    if poules:
                        resultat["poules"] = sorted(set(poules))
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
        self.aucune_contrainte_var = tk.BooleanVar()
        self.onglet_excel_var = tk.StringVar()
        self.chemin_var = tk.StringVar()
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
        ttk.Label(
            actions,
            textvariable=self.chemin_var,
        ).pack(side="left", fill="x", expand=True)
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
        ttk.Checkbutton(
            self.onglet_general,
            text="Aucune contrainte (enregistrer une configuration sans règle)",
            variable=self.aucune_contrainte_var,
            command=self._mettre_a_jour_etat_contraintes,
        ).grid(row=6, column=1, sticky="w", pady=(10, 2))
        ttk.Label(
            self.onglet_general,
            text=(
                "Lors de l'enregistrement, la liste des contraintes sera vide et aucune option "
                "« aucune_contrainte » ne sera ajoutée au JSON."
            ),
            wraplength=650,
        ).grid(row=7, column=1, sticky="w", pady=(0, 8))
        ttk.Separator(self.onglet_general).grid(row=8, column=0, columnspan=2, sticky="ew", pady=16)
        ttk.Button(
            self.onglet_general, text="Régénérer la structure standard",
            command=self._regenerer_standard,
        ).grid(row=9, column=0, columnspan=2, sticky="ew", pady=5)
        ttk.Button(
            self.onglet_general, text="Partir de zéro (supprimer matchs et contraintes)",
            command=self._partir_de_zero,
        ).grid(row=10, column=0, columnspan=2, sticky="ew", pady=5)
        self.onglet_general.columnconfigure(1, weight=1)

    def _mettre_a_jour_etat_contraintes(self):
        self._synchroniser_general()
        self._rafraichir_visualisation()
        self._rafraichir_json()

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
        self.cible_visualisation = None
        self.filtrer_contraintes_visualisation = False
        self.cible_visualisation_var = tk.StringVar(value="Cible : aucune sélection")
        self.onglet_visualisation.columnconfigure(0, weight=1)
        self.onglet_visualisation.columnconfigure(2, weight=0)
        self.onglet_visualisation.rowconfigure(1, weight=1)
        outils = ttk.Frame(self.onglet_visualisation)
        outils.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        ttk.Label(
            outils,
            text=(
                "Cliquez une position, un match ou une colonne. "
                "Ctrl+clic sélectionne plusieurs matchs. V = vainqueur, P = perdant."
            ),
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
        self.vue_compacte_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            outils,
            text="Vue compacte",
            variable=self.vue_compacte_var,
            command=self._rafraichir_visualisation,
        ).pack(side="right", padx=(12, 8))
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
        panneau.rowconfigure(1, weight=1)
        panneau.columnconfigure(0, weight=1)
        ttk.Label(
            panneau,
            textvariable=self.cible_visualisation_var,
            wraplength=320,
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
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
        self.table_contraintes_visu.grid(row=1, column=0, sticky="nsew")
        barre_contraintes = ttk.Scrollbar(
            panneau,
            orient="vertical",
            command=self.table_contraintes_visu.yview,
        )
        barre_contraintes.grid(row=1, column=1, sticky="ns")
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
        boutons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            boutons,
            text="Ajouter",
            command=self._ajouter_contrainte_visualisation,
        ).pack(
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
        ttk.Button(
            panneau,
            text="Afficher toutes les contraintes du tableau",
            command=self._afficher_toutes_contraintes_visualisation,
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def _texte_cible_visualisation(self, cible):
        suffixe = (
            " — contraintes désactivées"
            if self.aucune_contrainte_var.get()
            else ""
        )
        if not cible:
            return "Cible : aucune sélection{}".format(suffixe)
        if cible.get("type") == "position":
            return "Cible : position {}{}".format(cible["numero"], suffixe)
        if cible.get("type") == "match":
            return "Cible : match {}{}".format(cible["numero"], suffixe)
        if cible.get("type") == "niveau":
            return "Cible : niveau {}{}".format(cible["numero"], suffixe)
        return "Cible : matchs {}{}".format(
            ", ".join(str(numero) for numero in cible.get("numeros", [])), suffixe
        )

    def _selectionner_cible_visualisation(self, cible):
        self.cible_visualisation = cible
        self.filtrer_contraintes_visualisation = cible is not None
        self.cible_visualisation_var.set(self._texte_cible_visualisation(cible))
        indices = self._indices_contraintes_cible(cible)
        self._rafraichir_contraintes_visualisation()
        if indices and hasattr(self, "table_contraintes_visu"):
            self.table_contraintes_visu.selection_set(str(indices[0]))
            self.table_contraintes_visu.see(str(indices[0]))
        elif hasattr(self, "table_contraintes_visu"):
            self.table_contraintes_visu.selection_remove(
                *self.table_contraintes_visu.selection()
            )
        self._rafraichir_visualisation()

    def _indices_contraintes_cible(self, cible):
        contraintes = self.donnees.get("contraintes", [])
        return indices_contraintes_pour_cible(
            cible, contraintes, self.donnees.get("matchs", [])
        )

    def _numeros_matchs_cible_visualisation(self):
        cible = self.cible_visualisation or {}
        if cible.get("type") == "match":
            return [int(cible["numero"])]
        if cible.get("type") == "matchs":
            return [int(numero) for numero in cible.get("numeros", [])]
        if cible.get("type") == "niveau":
            profondeurs = calculer_profondeurs_matchs(self.donnees.get("matchs", []))
            return sorted(
                numero for numero, profondeur in profondeurs.items()
                if profondeur == int(cible["numero"])
            )
        return []

    def _afficher_toutes_contraintes_visualisation(self):
        self.cible_visualisation = None
        self.filtrer_contraintes_visualisation = False
        self.cible_visualisation_var.set("Toutes les contraintes du tableau")
        self._rafraichir_contraintes_visualisation()
        self._rafraichir_visualisation()

    def _clic_cible_visualisation(self, evenement):
        tags = self.canvas_tableau.gettags("current")
        tag_cible = next((tag for tag in tags if tag.startswith("cible:")), None)
        if not tag_cible:
            return
        _prefixe, type_cible, valeur = tag_cible.split(":", 2)
        if type_cible == "position":
            cible = {"type": "position", "numero": int(valeur)}
        elif type_cible == "niveau":
            cible = {"type": "niveau", "numero": int(valeur)}
        else:
            numeros = [int(numero) for numero in valeur.split(",") if numero]
            if type_cible == "match" and evenement.state & 0x0004:
                existants = []
                if self.cible_visualisation:
                    if self.cible_visualisation.get("type") == "match":
                        existants = [self.cible_visualisation["numero"]]
                    elif self.cible_visualisation.get("type") == "matchs":
                        existants = list(self.cible_visualisation.get("numeros", []))
                numero = numeros[0]
                if numero in existants:
                    existants = [n for n in existants if n != numero]
                else:
                    existants.append(numero)
                numeros = sorted(set(existants))
                if not numeros:
                    self._selectionner_cible_visualisation(None)
                    return
            cible = (
                {"type": "match", "numero": numeros[0]}
                if len(numeros) == 1
                else {"type": "matchs", "numeros": numeros}
            )
        self._selectionner_cible_visualisation(cible)

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
        profondeur_max = max(profondeurs.values(), default=1)
        vue_compacte = self.vue_compacte_var.get()
        if vue_compacte:
            origine_tableau = marge_x + 85 * z
            x_positions = marge_x
        else:
            # Les barrages forment l'axe central. On réserve autant de place
            # à gauche qu'à droite pour les deux tableaux en miroir.
            origine_tableau = marge_x + (profondeur_max - 1) * pas_colonne + 170 * z
            x_positions = origine_tableau - 85 * z
        positions_coordonnees = {
            numero: (x_positions, marge_y + (numero - 1) * pas_joueur)
            for numero in range(1, taille + 1)
        }
        contraintes = self.donnees.get("contraintes", [])
        position_selectionnee = (
            int(self.cible_visualisation["numero"])
            if self.cible_visualisation
            and self.cible_visualisation.get("type") == "position"
            else None
        )
        matchs_selectionnes = set()
        if self.cible_visualisation:
            if self.cible_visualisation.get("type") == "match":
                matchs_selectionnes.add(int(self.cible_visualisation["numero"]))
            elif self.cible_visualisation.get("type") == "matchs":
                matchs_selectionnes.update(
                    int(numero) for numero in self.cible_visualisation.get("numeros", [])
                )
            elif self.cible_visualisation.get("type") == "niveau":
                niveau_selectionne = int(self.cible_visualisation["numero"])
                matchs_selectionnes.update(
                    numero for numero, profondeur in profondeurs.items()
                    if profondeur == niveau_selectionne
                )
        for numero, (x, y) in positions_coordonnees.items():
            tags = ("cible_cliquable", "cible:position:{}".format(numero))
            contraintes_position = indices_contraintes_de_position(numero, contraintes)
            contrainte_position_selectionnee = (
                index_contrainte_selectionnee in contraintes_position
            )
            canvas.create_rectangle(
                x - 30 * z,
                y - 13 * z,
                x + 53 * z,
                y + 13 * z,
                fill="#e0f2fe" if numero == position_selectionnee else "",
                outline=(
                    "#0284c7" if numero == position_selectionnee
                    else "#ea580c" if contrainte_position_selectionnee
                    else ""
                ),
                width=max(1, int((3 if contrainte_position_selectionnee else 2) * z)),
                tags=tags,
            )
            canvas.create_text(
                x, y, text=str(numero), anchor="e",
                font=("TkDefaultFont", max(8, int(10 * z)), "bold"), fill="#333333",
                tags=tags,
            )
            canvas.create_line(
                x + 8 * z, y, x + 50 * z, y, fill="#8a8a8a", tags=tags
            )
            if contraintes_position:
                canvas.create_oval(
                    x + 33 * z, y - 11 * z, x + 49 * z, y + 5 * z,
                    fill="#ea580c" if contrainte_position_selectionnee else "#dc2626",
                    outline="", tags=tags,
                )
                canvas.create_text(
                    x + 41 * z, y - 3 * z, text=str(len(contraintes_position)),
                    fill="white", font=("TkDefaultFont", max(7, int(8 * z)), "bold"),
                    tags=tags,
                )

        par_numero = {int(match["numero"]): match for match in matchs}
        coordonnees_matchs = {}

        def coordonnee_source(reference, direction=1):
            type_reference = reference.get("type")
            if type_reference == "position":
                numero = int(reference.get("numero", 0))
                if numero not in positions_coordonnees:
                    raise ValueError("Position introuvable : {}".format(numero))
                x, y = positions_coordonnees[numero]
                return x + (50 * z if direction > 0 else -30 * z), y
            numero_match = int(reference.get("match", 0))
            if numero_match not in coordonnees_matchs:
                raise ValueError("Match précédent non positionné : {}".format(numero_match))
            x, y = coordonnees_matchs[numero_match]
            zone_source = zone_match_visualisation(par_numero[numero_match], taille)
            if not vue_compacte and zone_source.startswith("gauche"):
                return x, y
            return x + largeur_match, y

        for profondeur in range(1, profondeur_max + 1):
            groupe = [
                match for match in matchs
                if profondeurs[int(match["numero"])] == profondeur
            ]
            tags_colonne = (
                "cible_cliquable",
                "cible:niveau:{}".format(profondeur),
            )
            if vue_compacte:
                groupes_entetes = [(
                    origine_tableau + (profondeur - 1) * pas_colonne,
                    groupe,
                )]
            else:
                groupes_par_x = {}
                for match in groupe:
                    x_entete = abscisse_match_visualisation(
                        profondeur, match.get("places", []), taille, False,
                        origine_tableau, pas_colonne,
                    )
                    groupes_par_x.setdefault(x_entete, []).append(match)
                groupes_entetes = sorted(groupes_par_x.items())
            for x_colonne, groupe_entete in groupes_entetes:
                numeros_entete = {
                    int(match["numero"]) for match in groupe_entete
                }
                noms_niveaux = list(dict.fromkeys(
                    str(match.get("niveau", "")) for match in groupe_entete
                ))
                niveaux_principaux = [
                    nom for nom in noms_niveaux
                    if nom.startswith("1/") or nom == "finale"
                ]
                libelle_tour = ", ".join(niveaux_principaux)
                if not libelle_tour:
                    if noms_niveaux == ["barrage_2_3"]:
                        libelle_tour = "Barrages 2–3"
                    else:
                        libelle_tour = "Classement"
                entete_selectionne = bool(numeros_entete) and numeros_entete.issubset(
                    matchs_selectionnes
                )
                canvas.create_rectangle(
                    x_colonne,
                    8 * z,
                    x_colonne + largeur_match,
                    42 * z,
                    fill="#e0f2fe" if entete_selectionne else "#f4f4f5",
                    outline="#0284c7" if entete_selectionne else "#a1a1aa",
                    tags=tags_colonne,
                )
                canvas.create_text(
                    x_colonne + largeur_match / 2,
                    25 * z,
                    text="NIVEAU {} — {}\n{} match(s)".format(
                        profondeur, libelle_tour, len(groupe_entete)
                    ),
                    justify="center",
                    font=("TkDefaultFont", max(7, int(8 * z)), "bold"),
                    tags=tags_colonne,
                )
            souhaits = []
            for match in groupe:
                direction = (
                    -1 if not vue_compacte
                    and zone_match_visualisation(match, taille).startswith("gauche")
                    else 1
                )
                sources = [
                    coordonnee_source(match.get("participant_1", {}), direction),
                    coordonnee_source(match.get("participant_2", {}), direction),
                ]
                souhaits.append((sum(source[1] for source in sources) / 2, match, sources))
            souhaits.sort(key=lambda element: element[0])
            precedents_y_principaux = {
                "centre": marge_y - espace_match,
                "gauche_principal": marge_y - espace_match,
                "droite_principal": marge_y - espace_match,
            }
            precedent_y_classement_gauche = debut_classements = (
                marge_y + taille * pas_joueur + 120 * z
            ) - espace_match
            precedent_y_classement_droite = debut_classements - espace_match
            index_classement_gauche = 0
            index_classement_droite = 0
            for souhaite_y, match, sources in souhaits:
                zone = zone_match_visualisation(match, taille)
                est_classement = not vue_compacte and zone.endswith("classement")
                if est_classement:
                    if zone.startswith("gauche"):
                        y = max(
                            souhaite_y,
                            debut_classements + index_classement_gauche * espace_match,
                            precedent_y_classement_gauche + espace_match,
                        )
                        precedent_y_classement_gauche = y
                        index_classement_gauche += 1
                    else:
                        y = max(
                            souhaite_y,
                            debut_classements + index_classement_droite * espace_match,
                            precedent_y_classement_droite + espace_match,
                        )
                        precedent_y_classement_droite = y
                        index_classement_droite += 1
                else:
                    cle_principale = zone if zone in precedents_y_principaux else "centre"
                    y = max(
                        souhaite_y,
                        precedents_y_principaux[cle_principale] + espace_match,
                    )
                    precedents_y_principaux[cle_principale] = y
                x = abscisse_match_visualisation(
                    profondeur,
                    match.get("places", []),
                    taille,
                    vue_compacte,
                    origine_tableau,
                    pas_colonne,
                )
                coordonnees_matchs[int(match["numero"])] = (x, y)
                direction = -1 if not vue_compacte and zone.startswith("gauche") else 1
                for index, (source_x, source_y) in enumerate(sources, start=1):
                    reference = match.get("participant_{}".format(index), {})
                    numero_source = int(reference.get("match", 0))
                    source_est_barrage = (
                        numero_source in par_numero
                        and par_numero[numero_source].get("niveau") == "barrage_2_3"
                    )
                    if (
                        not vue_compacte
                        and reference.get("type") == "perdant"
                        and not source_est_barrage
                    ):
                        canvas.create_text(
                            x - 8 * z if direction > 0 else x + largeur_match + 8 * z,
                            y - hauteur_match * 0.23 if index == 1 else y + hauteur_match * 0.23,
                            text="Perdant match {}".format(numero_source),
                            anchor="e" if direction > 0 else "w",
                            fill="#9a3412",
                            font=("TkDefaultFont", max(7, int(8 * z)), "italic"),
                        )
                        continue
                    cible_y = y - hauteur_match * 0.23 if index == 1 else y + hauteur_match * 0.23
                    cible_x = x if direction > 0 else x + largeur_match
                    sortie_verticale_barrage = (
                        not vue_compacte
                        and source_est_barrage
                        and reference.get("type") == "perdant"
                        and direction < 0
                    )
                    if sortie_verticale_barrage:
                        # Le trait du perdant ne traverse plus la case du barrage :
                        # il quitte le milieu du bord le plus proche (haut ou bas),
                        # puis rejoint le tableau gauche.
                        x_barrage, y_barrage = coordonnees_matchs[numero_source]
                        source_x = x_barrage + largeur_match / 2
                        source_y = y_barrage + (
                            -hauteur_match / 2
                            if cible_y < y_barrage
                            else hauteur_match / 2
                        )
                    milieu_x = (source_x + cible_x) / 2
                    canvas.create_line(
                        source_x, source_y, milieu_x, source_y, milieu_x, cible_y,
                        cible_x, cible_y,
                        fill="#5f6368", width=max(1, int(z)),
                    )
                    if reference.get("type") in ("vainqueur", "perdant"):
                        decalage_etiquette = 7 * z if direction > 0 else -7 * z
                        ancre_etiquette = "w" if direction > 0 else "e"
                        if sortie_verticale_barrage:
                            decalage_etiquette = 0
                            ancre_etiquette = "center"
                        canvas.create_text(
                            source_x + decalage_etiquette,
                            source_y + (-7 * z if cible_y < y_barrage else 7 * z)
                            if sortie_verticale_barrage else source_y - 7 * z,
                            text="V" if reference["type"] == "vainqueur" else "P",
                            anchor=ancre_etiquette,
                            fill="#166534" if reference["type"] == "vainqueur" else "#9a3412",
                            font=("TkDefaultFont", max(7, int(8 * z)), "bold"),
                        )
                couleur = "#dbeafe" if str(match.get("niveau", "")).startswith("1/") or match.get("niveau") == "finale" else "#fef3c7"
                contraintes_match = indices_contraintes_du_match(
                    match, self.donnees.get("contraintes", []), profondeur
                )
                selectionne = index_contrainte_selectionnee in contraintes_match
                contour = "#dc2626" if contraintes_match else "#3f3f46"
                if selectionne:
                    contour = "#ea580c"
                numero_match = int(match["numero"])
                if numero_match in matchs_selectionnes:
                    contour = "#0284c7"
                tags_match = (
                    "cible_cliquable",
                    "cible:match:{}".format(numero_match),
                )
                canvas.create_rectangle(
                    x, y - hauteur_match / 2, x + largeur_match, y + hauteur_match / 2,
                    fill=couleur,
                    outline=contour,
                    width=max(1, int((3 if selectionne or numero_match in matchs_selectionnes else 2 if contraintes_match else 1) * z)),
                    tags=tags_match,
                )
                canvas.create_text(
                    x + 8 * z, y - 8 * z, anchor="w",
                    text="MATCH {}".format(match["numero"]),
                    font=("TkDefaultFont", max(8, int(10 * z)), "bold"),
                    tags=tags_match,
                )
                canvas.create_text(
                    x + 8 * z, y + 9 * z, anchor="w",
                    text=str(match.get("niveau", "")), fill="#52525b",
                    font=("TkDefaultFont", max(7, int(9 * z))),
                    tags=tags_match,
                )
                if contraintes_match:
                    canvas.create_oval(
                        x + largeur_match - 25 * z,
                        y - 17 * z,
                        x + largeur_match - 7 * z,
                        y + 1 * z,
                        fill="#dc2626" if not selectionne else "#ea580c",
                        outline="",
                        tags=tags_match,
                    )
                    canvas.create_text(
                        x + largeur_match - 16 * z,
                        y - 8 * z,
                        text=str(len(contraintes_match)),
                        fill="white",
                        font=("TkDefaultFont", max(7, int(8 * z)), "bold"),
                        tags=tags_match,
                    )

        hauteur = max(
            marge_y + taille * pas_joueur,
            max((y for _x, y in coordonnees_matchs.values()), default=0) + 100 * z,
        )
        largeur = (
            marge_x + 150 * z + profondeur_max * pas_colonne
            if vue_compacte
            else origine_tableau + profondeur_max * pas_colonne + largeur_match + marge_x
        )
        canvas.configure(scrollregion=(0, 0, largeur, hauteur))
        canvas.tag_bind(
            "cible_cliquable",
            "<Button-1>",
            self._clic_cible_visualisation,
        )

    def _charger_variables(self):
        self.nom_var.set(self.donnees.get("nom", ""))
        self.taille_var.set(str(self.donnees.get("taille_tableau", 32)))
        self.integral_var.set(bool(self.donnees.get("classement_integral", False)))
        self.barrages_var.set(bool(self.donnees.get("barrages_1_contre_4", False)))
        self.aucune_contrainte_var.set(
            bool(self.donnees.get("aucune_contrainte", False))
            or not self.donnees.get("contraintes", [])
        )
        self.onglet_excel_var.set(self.donnees.get("onglet_excel", "classement poules"))

    def _mettre_a_jour_titre(self):
        nom = self.chemin.name if self.chemin else "Nouvelle configuration"
        self.title("Éditeur de configuration — {}".format(nom))
        self.chemin_var.set(
            "Fichier JSON : {}".format(self.chemin if self.chemin else "non enregistré")
        )

    def _remplacer_configuration(self, donnees, chemin=None):
        self.donnees = donnees
        self.chemin = Path(chemin) if chemin else None
        if hasattr(self, "cible_visualisation_var"):
            self.cible_visualisation = None
            self.filtrer_contraintes_visualisation = False
            self.cible_visualisation_var.set("Cible : aucune sélection")
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
        self.donnees.pop("aucune_contrainte", None)

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
        if type_contrainte == "rangs_position":
            texte = "Rangs : {}".format(
                ", ".join(map(str, contrainte.get("rangs", [])))
            )
            poules = contrainte.get("poules", [])
            if poules:
                texte += " ; poules : {}".format(", ".join(map(str, poules)))
            return texte
        if type_contrainte == "rangs_match":
            return "Rangs : {}".format(", ".join(map(str, contrainte.get("rangs", []))))
        if type_contrainte == "rangs_meme_poule_interdits":
            return "Même poule interdite pour les rangs : {}".format(
                ", ".join(map(str, contrainte.get("rangs", [])))
            )
        if type_contrainte == "rangs_participants":
            return "P1 : {} ; P2 : {}".format(
                ", ".join(map(str, contrainte.get("participant_1", []))),
                ", ".join(map(str, contrainte.get("participant_2", []))),
            )
        return ""

    def _texte_cible_contrainte(self, contrainte, contexte_visualisation=False):
        cible = contrainte.get("cible", {})
        type_cible = cible.get("type")
        if type_cible == "position":
            texte = "Position {}".format(cible.get("numero", ""))
        elif type_cible == "match":
            texte = "Directe : match {}".format(cible.get("numero", ""))
        elif type_cible == "matchs":
            numeros = [int(n) for n in cible.get("numeros", [])]
            matchs = {
                int(match["numero"]): match for match in self.donnees.get("matchs", [])
            }
            niveaux = sorted({
                str(matchs[numero].get("niveau", ""))
                for numero in numeros if numero in matchs
            })
            niveau = niveaux[0] if len(niveaux) == 1 else "niveau mixte"
            texte = "Groupe : {} matchs ({})".format(len(numeros), niveau)
        elif type_cible == "niveau":
            prefixe = "Héritée du niveau" if contexte_visualisation else "Niveau entier"
            if "numero" in cible:
                texte = "{} {}".format(prefixe, cible.get("numero", ""))
            else:
                texte = "{} {} (ancienne notation)".format(
                    prefixe, cible.get("niveau", "")
                )
        else:
            texte = "Cible inconnue"
        exclusions = cible.get("exclusions_matchs", [])
        if exclusions:
            texte += " (sauf {})".format(
                ", ".join("M{}".format(numero) for numero in exclusions)
            )
        return texte

    def _rafraichir_contraintes(self):
        self.table_contraintes.delete(*self.table_contraintes.get_children())
        for index, contrainte in enumerate(self.donnees.get("contraintes", [])):
            texte_cible = self._texte_cible_contrainte(contrainte)
            self.table_contraintes.insert("", "end", iid=str(index), values=(
                contrainte.get("type", ""),
                texte_cible,
                self._description_contrainte(contrainte),
            ))
        self._rafraichir_contraintes_visualisation()

    def _rafraichir_contraintes_visualisation(self):
        if not hasattr(self, "table_contraintes_visu"):
            return
        self.table_contraintes_visu.delete(
            *self.table_contraintes_visu.get_children()
        )
        contraintes = self.donnees.get("contraintes", [])
        indices = (
            self._indices_contraintes_cible(self.cible_visualisation)
            if self.filtrer_contraintes_visualisation
            else list(range(len(contraintes)))
        )
        for index in indices:
            contrainte = contraintes[index]
            texte_cible = self._texte_cible_contrainte(
                contrainte,
                contexte_visualisation=self.filtrer_contraintes_visualisation,
            )
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
            ajouter_contrainte_donnees(self.donnees, contrainte)
            self.aucune_contrainte_var.set(False)
            self._rafraichir_tout()

    def _ajouter_contrainte_visualisation(self):
        if not self.cible_visualisation:
            messagebox.showinfo(
                "Choisir une cible",
                "Cliquez d'abord sur une position, un match ou une colonne du tableau.",
                parent=self,
            )
            return
        contrainte = DialogueContrainte(
            self,
            cible_initiale=dict(self.cible_visualisation),
        ).afficher()
        if contrainte:
            ajouter_contrainte_donnees(self.donnees, contrainte)
            self.aucune_contrainte_var.set(False)
            self._rafraichir_tout()

    def _modifier_contrainte(self, table=None):
        table = table or self.table_contraintes
        index = self._index_selectionne(table)
        if index is None:
            return
        contrainte = DialogueContrainte(self, self.donnees["contraintes"][index]).afficher()
        if contrainte:
            self.donnees["contraintes"][index] = contrainte
            self.aucune_contrainte_var.set(False)
            self._rafraichir_tout()

    def _supprimer_contrainte(self, table=None):
        table = table or self.table_contraintes
        index = self._index_selectionne(table)
        if index is None:
            return
        contrainte = self.donnees["contraintes"][index]
        cible = contrainte.get("cible", {})
        depuis_visualisation = (
            hasattr(self, "table_contraintes_visu")
            and table is self.table_contraintes_visu
            and self.cible_visualisation
        )
        if depuis_visualisation and cible.get("type") == "niveau":
            numeros = self._numeros_matchs_cible_visualisation()
            matchs = {
                int(match["numero"]): match for match in self.donnees.get("matchs", [])
            }
            profondeurs = calculer_profondeurs_matchs(self.donnees.get("matchs", []))
            if "numero" in cible:
                niveau = int(cible["numero"])
                numeros = [numero for numero in numeros if profondeurs.get(numero) == niveau]
                numeros_niveau = {
                    numero for numero, profondeur in profondeurs.items()
                    if profondeur == niveau
                }
                description_niveau = "Niveau {}".format(niveau)
            else:
                niveau = str(cible.get("niveau", ""))
                numeros = [
                    numero for numero in numeros
                    if numero in matchs and str(matchs[numero].get("niveau", "")) == niveau
                ]
                numeros_niveau = {
                    numero for numero, match in matchs.items()
                    if str(match.get("niveau", "")) == niveau
                }
                description_niveau = niveau
            if numeros and messagebox.askyesno(
                "Retirer la contrainte héritée",
                "Retirer cette contrainte de niveau uniquement des matchs {} ?\n\n"
                "La contrainte restera active sur les autres matchs du niveau {}.".format(
                    ", ".join(map(str, numeros)), description_niveau
                ),
                parent=self,
            ):
                exclusions = {int(n) for n in cible.get("exclusions_matchs", [])}
                exclusions.update(numeros)
                if numeros_niveau and numeros_niveau.issubset(exclusions):
                    del self.donnees["contraintes"][index]
                else:
                    cible["exclusions_matchs"] = sorted(exclusions)
                self._rafraichir_tout()
            return
        if depuis_visualisation and cible.get("type") == "matchs":
            selection = set(self._numeros_matchs_cible_visualisation())
            actuels = [int(n) for n in cible.get("numeros", [])]
            restants = [numero for numero in actuels if numero not in selection]
            if len(restants) != len(actuels) and messagebox.askyesno(
                "Retirer des matchs",
                "Retirer cette contrainte des matchs sélectionnés ?",
                parent=self,
            ):
                if restants:
                    cible["numeros"] = restants
                else:
                    del self.donnees["contraintes"][index]
                self._rafraichir_tout()
            return
        if messagebox.askyesno(
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
            if self.aucune_contrainte_var.get():
                nouvelles["contraintes"] = []
        except ValueError as erreur:
            messagebox.showerror("Génération impossible", str(erreur), parent=self)
            return
        self.donnees = nouvelles
        self.cible_visualisation = None
        self.filtrer_contraintes_visualisation = False
        self.cible_visualisation_var.set("Cible : aucune sélection")
        self._charger_variables()
        self._rafraichir_tout()

    def _partir_de_zero(self):
        if messagebox.askyesno(
            "Partir de zéro", "Supprimer tous les matchs et toutes les contraintes ?", parent=self
        ):
            self.donnees["format"] = "personnalise"
            self.donnees["matchs"] = []
            self.donnees["contraintes"] = []
            self.cible_visualisation = None
            self.filtrer_contraintes_visualisation = False
            self.cible_visualisation_var.set("Cible : aucune sélection")
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
            donnees_enregistrees = preparer_donnees_enregistrement(
                self.donnees,
                aucune_contrainte=self.aucune_contrainte_var.get(),
            )
            enregistrer_configuration(chemin, donnees_enregistrees)
        except Exception as erreur:
            messagebox.showerror("Configuration invalide", str(erreur), parent=self)
            return
        self.chemin = chemin
        self.donnees = donnees_enregistrees
        self.aucune_contrainte_var.set(not bool(self.donnees.get("contraintes")))
        self._mettre_a_jour_titre()
        self._rafraichir_tout()
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
