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

_HEADERS = ["Nom", "Montant (€)", "Date", "Paiement", "Statut"]


def get_service():
    creds = get_google_credentials()
    return build("sheets", "v4", credentials=creds)


def _is_mois_initialized(service, col):
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{TAB}'!{col}3",
    ).execute()
    return bool(result.get("values"))


def ensure_mois_initialized(service, mois, annee):
    if mois not in MOIS_COLONNES:
        raise ValueError(f"Mois inconnu : {mois}")
    col = MOIS_COLONNES[mois]
    if _is_mois_initialized(service, col):
        return
    col_num = col_to_num(col)
    col_fin = num_to_col(col_num + 4)
    montant_col = num_to_col(col_num + 1)
    rows = [
        [f"{mois} {annee}", "", "", "", ""],
        ["", "", "", "", ""],
        _HEADERS,
        ["Total :", f"=SUM({montant_col}5:{montant_col}200)", "", "", ""],
    ]
    service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{TAB}'!{col}1:{col_fin}4",
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

def ecrire_cours(cours_list, mois="Mai", dry_run=False, silent=False):
    if TAB in BLOCKED_TABS:
        raise PermissionError(f"Onglet bloqué : {TAB}")
    if mois not in MOIS_COLONNES:
        raise ValueError(f"Mois inconnu : {mois}")

    col = MOIS_COLONNES[mois]
    service = get_service()
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
