from models import Session, Event
from crawler_kingkalli import crawler_kingkalli
from crawler_aachen import crawler_aachen
import asyncio
from crawler_familienbildung import scrape_familienbildung

def speichern(events, quelle_name):
    session = Session()
    count = 0
    for event in events:
        session.add(event)
        count += 1
    session.commit()
    print(f"✅ {count} Events von {quelle_name} gespeichert.")

print("🚀 Starte alle Crawler...")

try:
    print("🔍 Crawler KingKalli wird ausgeführt...")
    events = crawler_kingkalli() or []
    speichern(events, "KingKalli")
    print("✅ KingKalli abgeschlossen")
except Exception as e:
    print(f"❌ Fehler bei KingKalli: {e}")

try:
    print("🔍 Crawler Aachen wird ausgeführt...")
    events = crawler_aachen() or []
    speichern(events, "Aachen")
    print("✅ Aachen abgeschlossen")
except Exception as e:
    print(f"❌ Fehler bei Aachen: {e}")

try:
    print("🔍 Crawler Familienbildung wird ausgeführt...")
    events = asyncio.run(scrape_familienbildung()) or []
    speichern(events, "Familienbildung Aachen")
    print("✅ Familienbildung abgeschlossen")
except Exception as e:
    print(f"❌ Fehler bei Familienbildung: {e}")

print("✅ Crawling abgeschlossen")
