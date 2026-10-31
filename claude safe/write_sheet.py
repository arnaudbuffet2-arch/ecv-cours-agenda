from googleapiclient.discovery import build
from google_auth import get_google_credentials
from rehydrate import rehydrate_text

SHEET_ID = "1OReCrVznxOtrxTzSRqpsKEu0lvR0cwdPoCixFKhgyxs"
TAB = "Gestion paiement cours mensuel"

BLOCKED_TABS = [
    "Suivi des revenues annuel",
    "Répartition des revenus mensuel",
    "Préparation des factures",
    "Macro du projet",
]

MOIS_COLONNES = {
    "Septembre": "A", "Octobre": "G", "Novembre": "M", "Décembre": "S",
    "Janvier": "AA", "Février": "AG", "Mars": "AM", "Avril": "AS", "Mai": "AY", "Juin": "BE",
    "Juillet": "BK", "Août": "BQ",
}

# Le Sheet empile un nouveau bloc de 5 colonnes par mois, annee apres annee,
# sans jamais reutiliser une colonne. MOIS_COLONNES ne donne donc que la
# position de la *premiere* occurrence (annee de depart = BASE_YEAR).
# resolve_col() localise la bonne occurrence pour (mois, annee) en comptant
# les repetitions du nom du mois dans la ligne 1, de gauche a droite.
BASE_YEAR = 2025
MOIS_FISCAL_DEBUT = ("Septembre", "Octobre", "Novembre", "Décembre")


def fiscal_cycle(mois, annee):
    if mois in MOIS_FISCAL_DEBUT:
        return annee - BASE_YEAR
    return annee - BASE_YEAR - 1


def _normalize_mois_label(value):
    return value.strip().rstrip("0123456789").strip().lower()


def scan_mois_occurrences(service, mois):
    """Colonnes (gauche->droite) dont le titre ligne 1 correspond a `mois`, annee ignoree."""
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1:HZ1"
    ).execute()
    row = result.get("values", [[]])
    row = row[0] if row else []
    target = mois.strip().lower()
    cols = []
    for i, v in enumerate(row):
        if v and _normalize_mois_label(v) == target:
            cols.append(num_to_col(i + 1))
    return cols


def resolve_col(service, mois, annee):
    if mois not in MOIS_COLONNES:
        raise ValueError(f"Mois inconnu : {mois}")
    cycle = fiscal_cycle(mois, annee)
    if cycle < 0:
        raise ValueError(
            f"{mois} {annee} est anterieur a la premiere annee suivie ({BASE_YEAR})."
        )
    occurrences = scan_mois_occurrences(service, mois)
    if cycle < len(occurrences):
        return occurrences[cycle]
    if cycle > len(occurrences):
        raise ValueError(
            f"Colonne introuvable pour {mois} {annee} : occurrence #{cycle} attendue "
            f"mais seulement {len(occurrences)} trouvee(s) en ligne 1. "
            f"Verifie manuellement avant de creer un nouveau bloc."
        )
    # cycle == len(occurrences) : il faut creer un nouveau bloc, juste apres le dernier utilise
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1:HZ1"
    ).execute()
    row = result.get("values", [[]])
    row = row[0] if row else []
    last_used = max((i + 1 for i, v in enumerate(row) if v and v.strip()), default=0)
    if last_used == 0:
        return "A"
    if mois == "Janvier":
        raise ValueError(
            "Transition Decembre->Janvier : l'ecart entre blocs n'est pas standard sur ce "
            "Sheet, cree la colonne de Janvier manuellement puis relance."
        )
    return num_to_col(last_used + 2)


def col_to_num(col):
    n = 0
    for c in col:
        n = n * 26 + (ord(c) - ord("A") + 1)
    return n

def num_to_col(n):
    result = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        result = chr(ord("A") + r) + result
    return result

_HEADERS = ["Nom de l'élève", "Montant", "Date du cours", "moyen de paiement", "Statut du paiement"]


def get_service():
    creds = get_google_credentials()
    return build("sheets", "v4", credentials=creds)


def _is_mois_initialized(service, col):
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{TAB}'!{col}2",
    ).execute()
    return bool(result.get("values"))


def ensure_mois_initialized(service, mois, annee):
    col = resolve_col(service, mois, annee)
    if _is_mois_initialized(service, col):
        return
    col_num = col_to_num(col)
    col_fin = num_to_col(col_num + 4)
    rows = [
        [f"{mois} {annee}", "", "", "", ""],
        _HEADERS,
    ]
    service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{TAB}'!{col}1:{col_fin}2",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()
    print(f"  → En-têtes {mois} {annee} créés dans le Sheet.")


def get_premiere_ligne_vide(service, col_debut):
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{TAB}'!{col_debut}3:{col_debut}100",
    ).execute()
    rows = result.get("values", [])
    return len(rows) + 3

def ecrire_cours(cours_list, mois="Mai", annee=None, dry_run=False, silent=False):
    if TAB in BLOCKED_TABS:
        raise PermissionError(f"Onglet bloqué : {TAB}")
    if annee is None:
        raise ValueError("annee est requis pour localiser la bonne colonne")

    service = get_service()
    col = resolve_col(service, mois, annee)
    premiere_ligne = get_premiere_ligne_vide(service, col)
    col_fin = num_to_col(col_to_num(col) + 4)
    range_ecriture = f"'{TAB}'!{col}{premiere_ligne}:{col_fin}{premiere_ligne + len(cours_list) - 1}"

    # Réhydratation locale — les vraies valeurs ne quittent pas cette fonction
    rows_to_write = []
    for c in cours_list:
        rows_to_write.append([
            rehydrate_text(c["nom"]),
            rehydrate_text(str(c["montant"])).replace("€", ""),
            rehydrate_text(c["date"]),
            c.get("moyen_paiement", ""),
            c.get("statut", "Finalisé"),
        ])

    if dry_run:
        return

    service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=range_ecriture,
        valueInputOption="USER_ENTERED",
        body={"values": rows_to_write},
    ).execute()
