# crawler_v2/parsers/standard.py

from .base import BaseParser

class DefaultParser(BaseParser):
    """
    Sehr einfacher Fallback-Parser für Seiten mit <h1> und <p>.
    Nimmt die ersten 5 Absätze als Beschreibung.
    """

    def __init__(self):
        super().__init__(name="DefaultParser")

    def extract(self, soup):
        try:
            h1 = soup.find("h1")
            if not h1:
                self.log("Kein <h1> gefunden → übersprungen", level="warn")
                return None

            title = self.clean_text(h1.get_text())
            paragraphs = soup.find_all("p")
            description = "\n".join([self.clean_text(p.get_text()) for p in paragraphs[:5]])

            self.log(f"✅ Event erkannt: {title}")
            return {
                "title": title,
                "date": "unbekannt",
                "description": description,
                "location": "unbekannt",
                "age_group": ""
            }

        except Exception as e:
            self.log(f"Fehler im DefaultParser: {e}", level="error")
            return None


class FallbackParser(BaseParser):
    """
    Alternative Fallback-Strategie für minimale Inhalte (z. B. nur <title> und ein <div>).
    """

    def __init__(self):
        super().__init__(name="FallbackParser")

    def extract(self, soup):
        try:
            title_tag = soup.find("title") or soup.find("h1")
            title = self.clean_text(title_tag.get_text()) if title_tag else "ohne Titel"

            first_div = soup.find("div")
            description = self.clean_text(first_div.get_text()) if first_div else ""

            self.log(f"🔁 Fallback-Event: {title}")
            return {
                "title": title,
                "date": "unbekannt",
                "description": description,
                "location": "unbekannt",
                "age_group": ""
            }

        except Exception as e:
            self.log(f"Fehler im FallbackParser: {e}", level="error")
            return None
