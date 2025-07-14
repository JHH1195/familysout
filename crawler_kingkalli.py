# crawler_kingkalli.py
from playwright.sync_api import sync_playwright
import re
from models import Event

def crawler_kingkalli():
    print("🔍 Crawler KingKalli wird ausgeführt...")

    events = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://kingkalli.de/events/", timeout=60000)

        try:
            page.wait_for_selector("article.type-tribe_events", timeout=15000)
        except:
            print("⚠️ Keine Events gefunden")
            return []

        items = page.query_selector_all("article.type-tribe_events")
        print(f"🔍 {len(items)} Event-Artikel gefunden")

        for item in items:
            try:
                title_el = item.query_selector("h3 a")
                date_el = item.query_selector("span.tribe-event-date-start")
                location_el = item.query_selector("div.tribe-events-venue-details")

                title = title_el.inner_text().strip() if title_el else "Kein Titel"
                date = date_el.inner_text().strip() if date_el else "Unbekannt"

                match = re.search(r"\sin\s([A-ZÄÖÜ][a-zäöüß]+(?:\s[A-ZÄÖÜ][a-zäöüß]+)?)", title)
                location = match.group(1) if match else (
                    location_el.inner_text().strip() if location_el else "Unbekannt"
                )

                event = Event(
                    title=title,
                    description="",
                    date=date,
                    location=location,
                    maps_url=f"https://www.google.com/maps/search/{location.replace(' ', '+')}",
                    category="Familie",
                    source_url="https://kingkalli.de/events/",
                    source_name="KingKalli"
                )

                events.append(event)
            except Exception as e:
                print(f"⚠️ Fehler beim Parsen eines Events: {e}")

        browser.close()

    print(f"✅ {len(events)} Events von KingKalli gespeichert.")
    return events
