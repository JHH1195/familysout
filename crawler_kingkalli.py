from playwright.sync_api import sync_playwright
import json
import re

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://kingkalli.de/events/", timeout=60000)

        page.wait_for_selector("article.type-tribe_events")

        events = []
        items = page.query_selector_all("article.type-tribe_events")

        for item in items:
            title_el = item.query_selector("h3 a")
            date_el = item.query_selector("span.tribe-event-date-start")
            location_el = item.query_selector("div.tribe-events-venue-details")

            title = title_el.inner_text().strip() if title_el else "Kein Titel"
            date = date_el.inner_text().strip() if date_el else "Kein Datum"

            # Ort aus Titel extrahieren
            match = re.search(r"\sin\s([A-ZÄÖÜ][a-zäöüß]+(?:\s[A-ZÄÖÜ][a-zäöüß]+)?)", title)
            location = match.group(1) if match else (
                location_el.inner_text().strip() if location_el else "Unbekannt"
            )

            maps_query = location.replace(" ", "+")
            maps_url = f"https://www.google.com/maps/search/{maps_query}"

            events.append({
                "title": title,
                "date": date,
                "location": location,
                "maps_url": maps_url
            })

        with open("events_kingkalli.json", "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, ensure_ascii=False)

        print(f"{len(events)} Events gespeichert.")
        browser.close()

if __name__ == "__main__":
    run()
