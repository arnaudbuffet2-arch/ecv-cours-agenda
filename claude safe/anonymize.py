import json
import re
from pathlib import Path

MAPPING_FILE = Path(__file__).parent / "mapping.json"

def load_mapping():
    if MAPPING_FILE.exists():
        return json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
    return {}

def save_mapping(mapping):
    MAPPING_FILE.write_text(json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8")

def get_token(mapping, real_value, kind):
    for token, value in mapping.items():
        if value == real_value:
            return token

    count = sum(1 for token in mapping if token.startswith(f"{{{{{kind}_"))
    token = f"{{{{{kind}_{count + 1:03d}}}}}"
    mapping[token] = real_value
    return token

PATTERNS = {
    "EMAIL":  r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "PHONE":  r"\b(?:\+33|0)[1-9](?:[\s.-]?\d{2}){4}\b",
    "SECRET": r"\b(?:sk-|sk_live_|ghp_|xoxb-|AIza)[A-Za-z0-9_\-]{10,}\b",
    "DATE":   r"\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b",
    "AMOUNT": r"\b\d+(?:[.,]\d{1,2})?\s*€",
    "IBAN":   r"\b[A-Z]{2}\d{2}(?:[A-Z0-9]\s?){4,30}\b",
}

# Mots capitalisés qui ne sont pas des données personnelles
_COMMON_WORDS = {
    "Cours", "Mois", "Total", "Statut", "Stripe", "Calendly", "Podia", "Finalisé",
    "Annulé", "Aucun", "Formation", "Facture", "Janvier", "Février", "Mars", "Avril",
    "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
    "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche",
    "Emile", "Coach", "Vocal",
}

def anonymize_text(text):
    mapping = load_mapping()
    for kind, pattern in PATTERNS.items():
        text = re.sub(pattern, lambda m, k=kind: get_token(mapping, m.group(0), k), text)
    save_mapping(mapping)
    return text

def audit_pii(text):
    """Bloque si un nom complet probable est détecté après anonymisation.

    Appelé sur le texte APRÈS anonymize_text() — détecte ce que les regex ne couvrent pas.
    Lève ValueError pour forcer un pré-traitement structuré (ex: anonymize_cours()).
    """
    # Ignore les tokens déjà remplacés
    cleaned = re.sub(r"\{\{[A-Z_]+_\d+\}\}", "", text)

    # Séquence de 2+ mots capitalisés consécutifs = nom complet probable
    suspects = re.findall(
        r"\b([A-ZÀ-Ÿ][a-zà-ÿ\-]+(?:\s+[A-ZÀ-Ÿ][a-zà-ÿ\-]+)+)\b",
        cleaned
    )
    suspects = [s for s in suspects if not all(w in _COMMON_WORDS for w in s.split())]

    if suspects:
        raise ValueError(
            f"PII potentiel détecté avant envoi à Claude : {suspects}\n"
            "Pré-anonymiser avec anonymize_cours() ou get_token() avant d'appeler ask_secure_claude()."
        )
