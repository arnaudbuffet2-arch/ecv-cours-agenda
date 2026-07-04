from datetime import datetime, timezone
from googleapiclient.discovery import build
from google_auth import get_google_credentials
from anonymize import get_token, load_mapping, save_mapping

BLOCKED_CALENDARS = []

def get_month_boundaries(year=None, month=None):
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start.isoformat(), end.isoformat()

def is_cours_event(event):
    title = event.get("summary", "")
    description = event.get("description", "") or ""
    is_calendly = "calendly" in description.lower()
    is_manual = "!)" in title
    return is_calendly or is_manual

def get_duration_minutes(event):
    start = event.get("start", {})
    end = event.get("end", {})
    fmt = "%Y-%m-%dT%H:%M:%S%z"
    try:
        t_start = datetime.fromisoformat(start.get("dateTime", ""))
        t_end = datetime.fromisoformat(end.get("dateTime", ""))
        return int((t_end - t_start).total_seconds() / 60)
    except Exception:
        return 0

def get_tarif(duration_minutes, is_ce=False):
    if is_ce:
        if duration_minutes >= 55:
            return 80
        if duration_minutes >= 25:
            return 50
        return 0
    if duration_minutes >= 55:
        return 88.6
    if duration_minutes >= 25:
        return 58.55
    return 0

def extract_client_name(event):
    title = event.get("summary", "")
    description = event.get("description", "") or ""

    if "calendly" in description.lower():
        # "Nom Prenom et Emile Coach Vocal" → "Nom Prenom"
        if " et " in title:
            return title.split(" et ")[0].strip()
        return title.strip()

    if "!)" in title:
        # "Nom Prenom (quelque chose !)" → "Nom Prenom"
        return title.split("(")[0].strip()

    return "Inconnu"

def read_cours_du_mois(year=None, month=None):
    creds = get_google_credentials()
    service = build("calendar", "v3", credentials=creds)

    time_min, time_max = get_month_boundaries(year, month)

    events_result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = events_result.get("items", [])
    cours = []

    for event in events:
        if not is_cours_event(event):
            continue

        duration = get_duration_minutes(event)
        is_ce = "ce!)" in event.get("summary", "").lower()
        tarif = get_tarif(duration, is_ce=is_ce)
        if tarif == 0:
            continue

        client = extract_client_name(event)
        date_str = event["start"].get("dateTime", event["start"].get("date", ""))
        date = datetime.fromisoformat(date_str).strftime("%d/%m/%Y")

        cours.append({
            "nom": client,
            "date": date,
            "duree_minutes": duration,
            "montant": tarif,
            "moyen_paiement": "stripe",
            "statut": "Finalisé",
        })

    return cours

def anonymize_cours(cours_list):
    """Retourne une liste de cours avec tokens à la place des vraies valeurs."""
    mapping = load_mapping()
    result = []
    for c in cours_list:
        result.append({
            "nom": get_token(mapping, c["nom"], "PERSON"),
            "date": get_token(mapping, c["date"], "DATE"),
            "duree_minutes": c["duree_minutes"],
            "montant": get_token(mapping, f"{c['montant']}€", "AMOUNT"),
            "moyen_paiement": c.get("moyen_paiement", ""),
            "statut": c.get("statut", "À confirmer"),
        })
    save_mapping(mapping)
    return result

def cours_to_anonymized_text(cours_list):
    if not cours_list:
        return "Aucun cours trouvé ce mois-ci."
    mapping = load_mapping()
    lines = ["Cours du mois :"]
    for c in cours_list:
        nom_token = get_token(mapping, c["nom"], "PERSON")
        date_token = get_token(mapping, c["date"], "DATE")
        amount_token = get_token(mapping, f"{c['montant']}€", "AMOUNT")
        lines.append(
            f"- {nom_token} | {date_token} | {c['duree_minutes']}min | {amount_token} | {c['statut']}"
        )
    save_mapping(mapping)
    return "\n".join(lines)
