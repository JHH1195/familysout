import requests
from bs4 import BeautifulSoup
from models import Session, Quelle, Event
from datetime import datetime
from dateparser import parse as date_parse
import re

def extract_event_blocks(html):
    soup = BeautifulSoup(html, "html.parser")
    return soup.find_all(["article", "section", "div"], recursive=True)

def extract_event_data(block, quelle, url):
    """
    Versucht HTML-Daten zu extrahieren. Nutzt GPT-4o nur, wenn nötig.
    """
    try:
        # 1. Titel aus h1–h3
        title_tag = block.find(["h1", "h2", "h3"])
        title = title_tag.get_text(strip=True) if title_tag else None

        # 2. Beschreibung (HTML-Flachtext)
        import trafilatura
        description = trafilatura.extract(str(block)) or block.get_text(" ", strip=True)


        # 3. Datum im deutschen Format
        date_match = re.search(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b", description)
        parsed_date = date_parse(date_match.group(0), languages=["de"]) if date_match else None
        date_str = parsed_date.strftime("%Y-%m-%d") if parsed_date else None

        return {
            "title": title or "Titel unbekannt",
            "description": description,
            "date": date_str or "2099-12-31",
            "location": quelle.stadt or "Ort unbekannt",
            "source_url": quelle.url,
            "source_name": quelle.name
        }

    except Exception as e:
        print("❌ Fehler in extract_event_data:", e)
        return None

def crawl_pending_quellen():
    session = Session()
    quellen = session.query(Quelle).filter_by(status='pending', aktiv=True).all()
    print(f"🔍 Starte Crawl für {len(quellen)} Quellen...")

    for quelle in quellen:
        try:
            print(f"🌐 Lade: {quelle.url}")
            response = requests.get(quelle.url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            html = response.text

            blocks = extract_event_blocks(html)
            print(f"🔎 {len(blocks)} potenzielle Blöcke auf Seite gefunden")

            events_gespeichert = 0
            übersprungen = 0

            for block in blocks:
                data = extract_event_data(block, quelle, quelle.url)
                if not data:
                    übersprungen += 1
                    continue

                already_exists = session.query(Event).filter_by(
                    title=data["title"],
                    date=data["date"],
                    location=data["location"]
                ).first()

                if not already_exists:
                    session.add(Event(**data))
                    events_gespeichert += 1

            quelle.status = "success"
            session.commit()

            if events_gespeichert:
                print(f"✅ {events_gespeichert} Event(s) gespeichert von {quelle.url}")
            else:
                print(f"⚠️ Keine neuen Eventdaten bei {quelle.url}")
            if übersprungen:
                print(f"↪️ {übersprungen} Blöcke übersprungen (Fehler beim Parsen)")

        except Exception as e:
            print(f"❌ Fehler bei {quelle.url}: {e}")
            quelle.status = "error"

    session.commit()
    session.close()
    print("🏁 Crawl abgeschlossen.")

if __name__ == "__main__":
    crawl_pending_quellen()
