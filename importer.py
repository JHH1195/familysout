import json
from models import Session, Event

# Lade Events aus JSON
with open("events_kingkalli.json", encoding="utf-8") as f:
    items = json.load(f)

session = Session()

# Kategorie-Funktion (vorerst simpel)
def bestimme_kategorie(title):
    title = title.lower()
    if "zirkus" in title or "musik" in title:
        return "Musik"
    if "park" in title or "wandern" in title or "spielplatz" in title:
        return "Draußen"
    if "museum" in title or "theater" in title:
        return "Drinnen"
    return "Unbekannt"

# Speichern in DB
for item in items:
    category = bestimme_kategorie(item["title"])
    event = Event(
        title=item["title"],
        date=item["date"],
        location=item["location"],
        maps_url=item["maps_url"],
        category=category
    )
    session.add(event)

session.commit()
print(f"✅ {len(items)} Events in die Datenbank eingefügt.")
