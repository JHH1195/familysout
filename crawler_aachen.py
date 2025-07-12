import requests
from bs4 import BeautifulSoup
import json

url = "https://www.aachen.de/in-aachen-leben/kultur/kulturkalender/"
resp = requests.get(url)
soup = BeautifulSoup(resp.text, "html.parser")

events = []

# Jeder Event scheint in li-Element: class 'teaser-item'
for item in soup.select("li.teaser-item"):
    title_tag = item.select_one("h3.teaser-headline")
    date_tag = item.select_one("div.teaser-info time")
    location_tag = item.select_one("div.teaser-info span.teaser-location")

    title = title_tag.get_text(strip=True) if title_tag else "Kein Titel"
    date = date_tag.get_text(strip=True) if date_tag else "Kein Datum"
    location = location_tag.get_text(strip=True) if location_tag else "Unbekannt"

    events.append({
        "title": title,
        "date": date,
        "location": location
    })

with open("events_aachen.json", "w", encoding="utf-8") as f:
    json.dump(events, f, indent=2, ensure_ascii=False)

print(f"{len(events)} Events gespeichert.")

