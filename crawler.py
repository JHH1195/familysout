import requests
from bs4 import BeautifulSoup
import json

url = "https://kingkalli.de/events/"
response = requests.get(url)
soup = BeautifulSoup(response.text, "html.parser")

events = []

# Jeder Event-Container ist ein 'article' mit class 'event'
for item in soup.select("article.type-tribe_events"):
    title_tag = item.select_one("h3.tribe-event-title")
    date_tag = item.select_one("span.tribe-event-date-start")
    location_tag = item.select_one("div.tribe-events-venue-details")

    if title_tag and date_tag:
        title = title_tag.get_text(strip=True)
        date = date_tag.get_text(strip=True)
        location = location_tag.get_text(strip=True) if location_tag else "Unbekannt"
        events.append({
            "title": title,
            "date": date,
            "location": location
        })

# In Datei speichern
with open("events.json", "w") as f:
    json.dump(events, f, indent=2, ensure_ascii=False)

print(f"{len(events)} Events gespeichert.")

