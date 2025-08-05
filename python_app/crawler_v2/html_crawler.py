# 📦 Pfadkonfiguration: ermöglicht Import von models.py aus Parent-Verzeichnis
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 🔍 Web & Parsing
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# 🧠 Parser-Mapping & Datenmodelle
from crawler_v2.extractors import extract_event
from python_app.models import Session, Event

# 💾 Event in die Datenbank speichern
def save_event(event_data):
    session = Session()

    # 🧠 Duplikat verhindern: gleiche Kombination aus Titel, Datum, Ort
    exists = session.query(Event).filter_by(
        title=event_data["title"],
        date=event_data["date"],
        location=event_data["location"]
    ).first()

    if exists:
        print(f"⚠️ Event bereits vorhanden: {event_data['title']} @ {event_data['date']}")
        session.close()
        return

    # 📦 Neues Event-Objekt anlegen
    new_event = Event(
        title=event_data.get("title"),
        description=event_data.get("description"),
        date=event_data.get("date"),
        location=event_data.get("location"),
        image_url=event_data.get("image_url", ""),
        maps_url=event_data.get("maps_url", ""),
        category=event_data.get("category", "Unbekannt"),
        source_url=event_data.get("url", ""),
        source_name=event_data.get("source", "Crawler"),
        price=None,
        is_free=None,
        is_outdoor=None,
        age_group=event_data.get("age_group", "")
    )

    session.add(new_event)
    session.commit()
    print(f"💾 Gespeichert: {new_event.title}")
    session.close()

# 🌐 HTML-Seite abrufen und als BeautifulSoup zurückgeben
def get_soup(url):
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

# 🕷 Hauptfunktion für den Crawl einer Quelle
def crawl_source(source, max_pages=1):
    visited_urls = set()  # Duplikate vermeiden

    for page in range(max_pages):
        paged_url = f"{source['start_url']}?page={page}"
        try:
            soup = get_soup(paged_url)
        except Exception as e:
            print(f"⛔ Fehler beim Laden von {paged_url}: {e}")
            break

        links = soup.select(source["detail_link_selector"])
        if not links:
            print(f"⛔ Seite {page} leer – abbreche Crawl.")
            break

        print(f"📄 Seite {page} → {len(links)} Events gefunden")

        for link in links:
            href = link.get("href")
            if not href:
                continue
            detail_url = urljoin(source["base_url"], href)

            if detail_url in visited_urls:
                continue
            visited_urls.add(detail_url)

            try:
                detail_soup = get_soup(detail_url)
                event_data = extract_event(detail_soup, source["parser"])

                if event_data:
                    print(f"✅ {event_data['title']} @ {event_data['date']}")
                    save_event(event_data)

            except Exception as e:
                print(f"⚠️ Fehler bei {detail_url}: {e}")

