from playwright.async_api import async_playwright
from models import Event

async def crawler_familienbildung():
    events = []
    url = "https://www.familienbildung-aachen.de/programm/eltern-kind-angebote"

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url)
        await page.wait_for_timeout(3000)  # Wartezeit zur Sicherheit

        links = await page.locator("a.linkProgramTitle").all()
        for link in links[:10]:  # Begrenzung für Testzwecke
            title = await link.text_content()
            href = await link.get_attribute("href")

            event = Event(
                title=title.strip() if title else "Ohne Titel",
                description="",
                date="Unbekannt",
                location="Aachen",
                category="Familie",
                source_url=f"https://www.familienbildung-aachen.de{href}" if href else url,
                source_name="Familienbildung Aachen"
            )
            events.append(event)

        await browser.close()

    return events
