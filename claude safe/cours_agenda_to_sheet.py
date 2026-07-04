"""
cours_agenda_to_sheet
---------------------
Lit les cours d'un mois depuis Google Calendar et les écrit dans
l'onglet "Gestion paiement cours mensuel" du Google Sheet ECV.

Usage :
    python cours_agenda_to_sheet.py --mois Mai --annee 2026
    python cours_agenda_to_sheet.py --mois Juin          # annee = année courante
    python cours_agenda_to_sheet.py                      # mois + annee courants
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from read_calendar import read_cours_du_mois, anonymize_cours
from write_sheet import ecrire_cours, get_service, SHEET_ID, TAB, MOIS_COLONNES, ensure_mois_initialized

MOIS_VERS_NUM = {
    "Janvier": 1, "Février": 2, "Mars": 3, "Avril": 4,
    "Mai": 5, "Juin": 6, "Juillet": 7, "Août": 8,
    "Septembre": 9, "Octobre": 10, "Novembre": 11, "Décembre": 12,
}

NUM_VERS_MOIS = {v: k for k, v in MOIS_VERS_NUM.items()}


def clear_mois(service, mois):
    col = MOIS_COLONNES[mois]
    service.spreadsheets().values().clear(
        spreadsheetId=SHEET_ID,
        range=f"'{TAB}'!{col}5:{col}Z50",
    ).execute()


def main():
    now = datetime.now()
    parser = argparse.ArgumentParser(description="Sync Google Calendar → Sheet ECV")
    parser.add_argument("--mois", default=NUM_VERS_MOIS[now.month],
                        choices=list(MOIS_VERS_NUM.keys()),
                        help="Mois en français (ex: Mai)")
    parser.add_argument("--annee", type=int, default=now.year,
                        help="Année (ex: 2026)")
    args = parser.parse_args()

    mois_nom = args.mois
    mois_num = MOIS_VERS_NUM[mois_nom]
    annee = args.annee

    print(f"cours_agenda_to_sheet — {mois_nom} {annee}")

    cours_bruts = read_cours_du_mois(year=annee, month=mois_num)
    if not cours_bruts:
        print("Aucun cours trouvé.")
        sys.exit(0)

    cours_anonymises = anonymize_cours(cours_bruts)
    del cours_bruts  # les vraies données quittent la mémoire

    service = get_service()
    ensure_mois_initialized(service, mois_nom, annee)
    clear_mois(service, mois_nom)
    ecrire_cours(cours_anonymises, mois=mois_nom, dry_run=False, silent=True)

    print(f"{len(cours_anonymises)} cours écrits dans '{TAB}' — {mois_nom} {annee}.")


if __name__ == "__main__":
    main()
