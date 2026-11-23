"""Résolution par contraction de Hall et séparation dissymétrique des domaines."""

from collections import deque

from .contraintes import (
    JoueursDansPositions,
    PositionImposee,
    RangsMatchImposes,
    RangsParticipantsImposes,
    RangsPositionImposes,
)
from .modele import identite_joueur


class _ArretRecherche(Exception):
    """Interrompt proprement une contraction lorsque l'utilisateur le demande."""


def _positions_participant(participant, cache_matchs):
    position = getattr(participant, "position", None)
    if position is not None:
        return {int(position) - 1}
    match = getattr(participant, "match", None)
    if match is None:
        return set()
    numero = int(match.numero)
    if numero not in cache_matchs:
        cache_matchs[numero] = (
            _positions_participant(match.participant_1, cache_matchs)
            | _positions_participant(match.participant_2, cache_matchs)
        )
    return set(cache_matchs[numero])


def _filtrer_domaine(domaines, position, predicate):
    avant = domaines[position]
    apres = {index for index in avant if predicate(index)}
    domaines[position] = apres
    return len(avant) - len(apres)


def _appliquer_filtres_statiques(domaines, joueurs, contraintes):
    """Applique les restrictions certaines avant la première bissection."""
    cache_matchs = {}
    reductions = 0
    for contrainte in contraintes:
        if isinstance(contrainte, RangsPositionImposes):
            position = contrainte.position - 1
            reductions += _filtrer_domaine(
                domaines,
                position,
                lambda index, c=contrainte: c._joueur_valide(joueurs[index]),
            )
        elif isinstance(contrainte, PositionImposee):
            position = contrainte.position - 1
            reductions += _filtrer_domaine(
                domaines,
                position,
                lambda index, attendu=contrainte.joueur_attendu: (
                    identite_joueur(joueurs[index]) == attendu
                ),
            )
        elif isinstance(contrainte, JoueursDansPositions):
            positions = {int(position) - 1 for position in contrainte.positions}
            attendus = set(contrainte.joueurs_attendus)
            for position in range(len(domaines)):
                if position in positions:
                    continue
                reductions += _filtrer_domaine(
                    domaines,
                    position,
                    lambda index, identites=attendus: (
                        identite_joueur(joueurs[index]) not in identites
                    ),
                )
        elif isinstance(contrainte, RangsParticipantsImposes):
            participants = (
                contrainte.match.participant_1,
                contrainte.match.participant_2,
            )
            for participant, rangs in zip(participants, contrainte.rangs):
                for position in _positions_participant(participant, cache_matchs):
                    reductions += _filtrer_domaine(
                        domaines,
                        position,
                        lambda index, autorises=rangs: (
                            int(joueurs[index]["rang_poule"]) in autorises
                        ),
                    )
        elif isinstance(contrainte, RangsMatchImposes):
            for participant in (
                contrainte.match.participant_1,
                contrainte.match.participant_2,
            ):
                for position in _positions_participant(participant, cache_matchs):
                    reductions += _filtrer_domaine(
                        domaines,
                        position,
                        lambda index, autorises=contrainte.rangs_attendus: (
                            int(joueurs[index]["rang_poule"]) in autorises
                        ),
                    )
    return reductions


def _trouver_appariement_complet(domaines):
    """Construit une affectation injective par Hopcroft-Karp, si elle existe."""
    nombre = len(domaines)
    affectation_positions = [-1] * nombre
    affectation_joueurs = [-1] * nombre
    distances = [0] * nombre
    infini = nombre + 1

    def preparer_niveau():
        file_positions = deque()
        distance_libre = infini
        for position in range(nombre):
            if affectation_positions[position] == -1:
                distances[position] = 0
                file_positions.append(position)
            else:
                distances[position] = infini
        while file_positions:
            position = file_positions.popleft()
            if distances[position] >= distance_libre:
                continue
            for joueur in domaines[position]:
                autre_position = affectation_joueurs[joueur]
                if autre_position == -1:
                    distance_libre = distances[position] + 1
                elif distances[autre_position] == infini:
                    distances[autre_position] = distances[position] + 1
                    file_positions.append(autre_position)
        return distance_libre != infini

    def augmenter(position):
        for joueur in domaines[position]:
            autre_position = affectation_joueurs[joueur]
            if autre_position == -1 or (
                distances[autre_position] == distances[position] + 1
                and augmenter(autre_position)
            ):
                affectation_positions[position] = joueur
                affectation_joueurs[joueur] = position
                return True
        distances[position] = infini
        return False

    taille = 0
    while preparer_niveau():
        for position in range(nombre):
            if affectation_positions[position] == -1 and augmenter(position):
                taille += 1
    if taille != nombre:
        return None
    return affectation_positions, affectation_joueurs


def _composantes_fortement_connexes(graphe):
    """Numérote les composantes fortement connexes sans récursion."""
    nombre = len(graphe)
    visites = [False] * nombre
    ordre = []

    for depart in range(nombre):
        if visites[depart]:
            continue
        pile = [(depart, False)]
        while pile:
            sommet, termine = pile.pop()
            if termine:
                ordre.append(sommet)
                continue
            if visites[sommet]:
                continue
            visites[sommet] = True
            pile.append((sommet, True))
            for voisin in graphe[sommet]:
                if not visites[voisin]:
                    pile.append((voisin, False))

    graphe_inverse = [[] for _ in range(nombre)]
    for sommet, voisins in enumerate(graphe):
        for voisin in voisins:
            graphe_inverse[voisin].append(sommet)

    composantes = [-1] * nombre
    numero = 0
    for depart in reversed(ordre):
        if composantes[depart] != -1:
            continue
        composantes[depart] = numero
        pile = [depart]
        while pile:
            sommet = pile.pop()
            for voisin in graphe_inverse[sommet]:
                if composantes[voisin] == -1:
                    composantes[voisin] = numero
                    pile.append(voisin)
        numero += 1
    return composantes


def _contracter_hall(domaines, appariement):
    """Retire les couples position-joueur absents de tout appariement complet.

    Une fois un appariement complet connu, les cycles alternés décrivent toutes
    les autres affectations possibles. Les composantes fortement connexes de ce
    graphe permettent d'appliquer la contraction de Hall sans énumérer les
    sous-ensembles de positions.
    """
    affectation_positions, affectation_joueurs = appariement
    graphe = [set() for _ in domaines]
    for position, domaine in enumerate(domaines):
        for joueur in domaine:
            autre_position = affectation_joueurs[joueur]
            if autre_position != position:
                graphe[position].add(autre_position)

    composantes = _composantes_fortement_connexes(graphe)
    reductions = 0
    for position, domaine in enumerate(domaines):
        joueur_affecte = affectation_positions[position]
        conserves = {
            joueur
            for joueur in domaine
            if joueur == joueur_affecte
            or composantes[position] == composantes[affectation_joueurs[joueur]]
        }
        reductions += len(domaine) - len(conserves)
        if conserves != domaine:
            domaines[position] = conserves
    return reductions


def _contracter(domaines, joueurs, contraintes, statistiques, arreter):
    """Contracte une boîte sans jamais supprimer une solution potentielle."""
    statistiques["boites_explorees"] += 1
    domaines = [set(domaine) for domaine in domaines]
    total_avant = sum(map(len, domaines))

    while True:
        if arreter is not None and arreter():
            raise _ArretRecherche()
        if any(not domaine for domaine in domaines):
            statistiques["boites_rejetees"] += 1
            return None

        modifies = False
        singletons = [next(iter(domaine)) for domaine in domaines if len(domaine) == 1]
        if len(singletons) != len(set(singletons)):
            statistiques["boites_rejetees"] += 1
            return None
        joueurs_fixes = set(singletons)
        for domaine in domaines:
            if len(domaine) == 1:
                continue
            avant = len(domaine)
            domaine.difference_update(joueurs_fixes)
            modifies = modifies or len(domaine) != avant

        occurrences = [0] * len(joueurs)
        derniere_position = [-1] * len(joueurs)
        for position, domaine in enumerate(domaines):
            for joueur in domaine:
                occurrences[joueur] += 1
                derniere_position[joueur] = position
        if any(nombre == 0 for nombre in occurrences):
            statistiques["boites_rejetees"] += 1
            return None
        for joueur, nombre in enumerate(occurrences):
            if nombre != 1:
                continue
            position = derniere_position[joueur]
            if len(domaines[position]) > 1:
                domaines[position] = {joueur}
                modifies = True

        placement = [
            joueurs[next(iter(domaine))] if len(domaine) == 1 else None
            for domaine in domaines
        ]
        if not all(contrainte.est_compatible(placement) for contrainte in contraintes):
            statistiques["boites_rejetees"] += 1
            return None

        for position, domaine in enumerate(domaines):
            if len(domaine) <= 1:
                continue
            conserves = set()
            for index_joueur in domaine:
                placement[position] = joueurs[index_joueur]
                if all(
                    contrainte.est_compatible(placement)
                    for contrainte in contraintes
                ):
                    conserves.add(index_joueur)
            placement[position] = None
            if conserves != domaine:
                domaines[position] = conserves
                modifies = True

        if any(not domaine for domaine in domaines):
            statistiques["boites_rejetees"] += 1
            return None
        appariement = _trouver_appariement_complet(domaines)
        if appariement is None:
            statistiques["boites_rejetees"] += 1
            return None
        reductions_hall = _contracter_hall(domaines, appariement)
        if reductions_hall:
            statistiques["reductions_hall"] += reductions_hall
            modifies = True

        if not modifies:
            break

    total_apres = sum(map(len, domaines))
    statistiques["reductions_domaines"] += max(0, total_avant - total_apres)
    return tuple(frozenset(domaine) for domaine in domaines)


def _est_terminale(domaines):
    return all(len(domaine) == 1 for domaine in domaines)


def _solution_depuis_domaines(domaines, joueurs, contraintes):
    indices = [next(iter(domaine)) for domaine in domaines]
    if len(indices) != len(set(indices)):
        return None
    placement = [joueurs[index] for index in indices]
    if all(contrainte.est_respectee(placement) for contrainte in contraintes):
        return placement
    return None


def _bisecter(domaines, joueurs):
    positions = [
        position for position, domaine in enumerate(domaines) if len(domaine) > 1
    ]
    if not positions:
        return None
    position = min(positions, key=lambda index: (len(domaines[index]), index))
    frequences = {}
    for domaine in domaines:
        for index_joueur in domaine:
            frequences[index_joueur] = frequences.get(index_joueur, 0) + 1
    candidats = sorted(
        domaines[position],
        key=lambda index: (
            frequences[index],
            int(joueurs[index].get("rang_poule", 0)),
            int(joueurs[index].get("poule", 0)),
            str(joueurs[index].get("club", "")),
            index,
        ),
    )
    groupes = (frozenset(candidats[:1]), frozenset(candidats[1:]))
    enfants = []
    for groupe in groupes:
        if not groupe:
            continue
        enfant = list(domaines)
        enfant[position] = groupe
        enfants.append(tuple(enfant))
    return enfants


def resoudre_par_bissection(
    joueurs,
    contraintes,
    nombre_positions=32,
    limite=None,
    notifier=None,
    arreter=None,
    notifier_statistiques=None,
    nombre_regions=8,
):
    """Résout par contraction de Hall et exploration de régions alternées.

    Les régions sont parcourues à tour de rôle afin que les premières solutions
    proviennent de parties différentes de l'espace de recherche, sans conserver
    une large file de boîtes en mémoire. Chaque séparation explore d'abord un
    candidat unique, puis conserve tous les autres dans la seconde branche.
    """
    if len(joueurs) != nombre_positions:
        raise ValueError(
            "La bissection attend {} joueurs pour {} positions.".format(
                nombre_positions, nombre_positions
            )
        )
    solutions = []
    recherche_interrompue = False
    statistiques = {
        "boites_explorees": 0,
        "boites_rejetees": 0,
        "bissections": 0,
        "reductions_domaines": 0,
        "reductions_hall": 0,
        "profondeur": 0,
        "profondeur_max": 0,
        "regions": 0,
        "solutions": 0,
    }

    def publier(force=False):
        if notifier_statistiques is None:
            return
        if force or statistiques["boites_explorees"] % 25 == 0:
            notifier_statistiques(dict(statistiques))

    def doit_arreter():
        nonlocal recherche_interrompue
        limite_atteinte = limite is not None and len(solutions) >= limite
        arret_demande = arreter is not None and arreter()
        if limite_atteinte or arret_demande:
            recherche_interrompue = True
            return True
        return False

    domaines = [set(range(nombre_positions)) for _ in range(nombre_positions)]
    statistiques["reductions_domaines"] += _appliquer_filtres_statiques(
        domaines, joueurs, contraintes
    )
    try:
        racine = _contracter(
            tuple(frozenset(domaine) for domaine in domaines),
            joueurs,
            contraintes,
            statistiques,
            arreter,
        )
        publier(force=True)
        if racine is None:
            return [], True

        regions = deque([(racine, 0)])
        objectif_regions = max(1, int(nombre_regions))
        if limite is not None:
            objectif_regions = min(objectif_regions, max(1, int(limite)))
        while regions and len(regions) < objectif_regions:
            boite, profondeur = regions.popleft()
            if _est_terminale(boite):
                regions.append((boite, profondeur))
                break
            enfants = _bisecter(boite, joueurs)
            statistiques["bissections"] += 1
            for enfant in enfants or []:
                contracte = _contracter(
                    enfant, joueurs, contraintes, statistiques, arreter
                )
                if contracte is not None:
                    regions.append((contracte, profondeur + 1))
            publier()
        statistiques["regions"] = len(regions)

        def explorer(boite_initiale, profondeur_initiale):
            pile = [(boite_initiale, profondeur_initiale)]
            while pile:
                if doit_arreter():
                    raise _ArretRecherche()
                boite, profondeur = pile.pop()
                statistiques["profondeur"] = profondeur
                statistiques["profondeur_max"] = max(
                    statistiques["profondeur_max"], profondeur
                )
                if _est_terminale(boite):
                    solution = _solution_depuis_domaines(
                        boite, joueurs, contraintes
                    )
                    if solution is None:
                        statistiques["boites_rejetees"] += 1
                    else:
                        yield solution
                    continue
                enfants = _bisecter(boite, joueurs)
                statistiques["bissections"] += 1
                contractes = []
                for enfant in enfants or []:
                    contracte = _contracter(
                        enfant, joueurs, contraintes, statistiques, arreter
                    )
                    if contracte is not None:
                        contractes.append(contracte)
                for contracte in reversed(contractes):
                    pile.append((contracte, profondeur + 1))
                publier()

        generateurs = deque(
            explorer(boite, profondeur) for boite, profondeur in regions
        )
        while generateurs and not doit_arreter():
            generateur = generateurs.popleft()
            try:
                solution = next(generateur)
            except StopIteration:
                continue
            solutions.append(solution)
            statistiques["solutions"] = len(solutions)
            if notifier is not None:
                notifier(len(solutions))
            publier(force=True)
            generateurs.append(generateur)
    except _ArretRecherche:
        recherche_interrompue = True

    statistiques["profondeur"] = 0
    statistiques["solutions"] = len(solutions)
    publier(force=True)
    return solutions, not recherche_interrompue
