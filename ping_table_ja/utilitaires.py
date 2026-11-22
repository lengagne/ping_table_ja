"""Fonctions utilitaires sans dépendance métier."""

import unicodedata


def normaliser_club(club):
    if club is None:
        return ""
    club = unicodedata.normalize("NFD", str(club).strip().casefold())
    club = "".join(c for c in club if unicodedata.category(c) != "Mn")
    return " ".join(club.split())


def nettoyer(valeur):
    """Convertit une cellule Excel en texte propre."""
    return "" if valeur is None else str(valeur).replace("\n", " ").strip()
