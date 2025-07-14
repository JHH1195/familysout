# crawler_familienbildung.py

import asyncio
from playwright.async_api import async_playwright
from models import Event

url = "https://www.familienbildung-aachen.de/programm/eltern-kind-angebote"

async def scrape_familienbildung():
    events = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("🌐 Öffne Seite...")
        await page.goto(url, timeout=30000)

        try:
            cookie_button = await page.locator("button#CybotCookiebotDialogBodyButtonDecline").element_handle(timeout=3000)
            if cookie_button:
                await cookie_button.click()
                print("✅ Cookie-Banner geschlossen")
        except:
            print("⚠️ Kein Cookie-Banner gefunden")

        await page.wait_for_selector("table", timeout=10000)
        rows = await page.locator("table tbody tr").all()
        print(f"🔍 {len(rows)} Kurs-Zeilen gefunden.")

        for i, row in enumerate(rows):
            try:
                # Statt nur <a>: kompletten Text aus der ersten Spalte holen
                first_cell = row.locator("td").nth(0)
                title = await first_cell.inner_text(timeout=2000)
                
                date = await row.locator("td").nth(1).inner_text(timeout=2000)

                description = f"Kurs: {title}, Datum: {date}"

                events.append(Event(
                    title=title.strip(),
                    description=description.strip(),
                    date=date.strip(),
                    location="Aachen",
                    category="Eltern-Kind",
                    source_url=url,
                    source_name="Familienbildung Aachen"
                ))
            except Exception as e:
                print(f"⚠️ Fehler beim Parsen einer Zeile {i}: {e}")
                continue

        await browser.close()

    return events
