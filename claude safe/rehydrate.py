import json
from pathlib import Path

MAPPING_FILE = Path(__file__).parent / "mapping.json"

def rehydrate_text(text):
    if not MAPPING_FILE.exists():
        return text

    mapping = json.loads(MAPPING_FILE.read_text(encoding="utf-8"))

    for token, real_value in mapping.items():
        text = text.replace(token, real_value)

    return text