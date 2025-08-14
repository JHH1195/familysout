import os
import yaml
from datetime import datetime

# Absolutpfad zur YAML in crawler/data
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "data", "always_open.yaml")

def load_always_open():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"always_open.yaml nicht gefunden unter {DATA_PATH}")
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f).get("locations", [])

def match_always_open(location_name: str):
    if not location_name:
        return None

    locations = load_always_open()
    location_name_lower = location_name.lower()

    for loc in locations:
        patterns = [loc.get("name", "")] + loc.get("match", [])
        for pattern in patterns:
            if pattern.lower() in location_name_lower:
                season = loc.get("season")
                if season:
                    today = datetime.today()
                    start = datetime.strptime(f"{season['start']}-{today.year}", "%m-%d-%Y")
                    end = datetime.strptime(f"{season['end']}-{today.year}", "%m-%d-%Y")
                    if not (start <= today <= end):
                        return None
                return loc
    return None
