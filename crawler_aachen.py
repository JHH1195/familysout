# crawler_aachen.py
from bs4 import BeautifulSoup
import requests
from models import Event

def crawler_aachen():
    print("🔍 Crawler Aachen wird ausgeführt...")

    url = "https://www.aachen.de/DE/stadt_buerger/freizeit_kultur/familie_kinder/Veranstaltungen/index.html"
    res = requests.get(url, timeout=10)
    soup = BeautifulSoup(res.text, "html.parser")

    events = []
    blocks = soup.select("div.teaser")

    print(f"🔍 {len(blocks)} Blöcke gefunden")

    for block in blocks:
        title = block.select_one("h3")
        desc = block.select_one("p")

        event = Event(
            title=title.get_text(strip=True) if title else "Ohne Titel",
            description=desc.get_text(strip=True) if desc else "",
            date="Unbekannt",
            location="Aachen",
            category="Familie",
            source_url=url,
            source_name="Stadt Aachen"
        )
        events.append(event)

    print(f"✅ {len(events)} Events von Aachen gespeichert.")
    return events
