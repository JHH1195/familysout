# crawler_v2/parsers/special_cases.py

from .base import BaseParser
import re

class KingKalliParser(BaseParser):
    """
    Extrahiert Events aus KingKalli-ähnlichen Seiten mit JSON-LD innerhalb von <script>.
    Häufig wenig strukturierter HTML-Inhalt, daher spezielle Behandlung.
    """

    def __init__(self):
        super().__init__(name="KingKalliParser")

    def extract(self, soup):
        try:
            script_tag = soup.find("script", type="application/ld+json")
            if not script_tag or not script_tag.string:
                self.log("Kein JSON-LD gefunden", level="warn")
                return None

            import json
            data = json.loads(script_tag.string)
            if isinstance(data, list):
                data = data[0]
            if not data or data.get("@type") != "Event":
                self.log("Kein Event in JSON-LD", level="warn")
                return None

            title = self.clean_text(data.get("name", "ohne Titel"))
            date = self.clean_text(data.get("startDate", "unbekannt"))[:10]
            description = self.clean_text(data.get("description", ""))
            location = self._extract_location(data.get("location"))

            self.log(f"🧸 KingKalli-Event: {title}")
            return {
                "title": title,
                "date": date,
                "description": description,
                "location": location,
                "age_group": ""
            }

        except Exception as e:
            self.log(f"Fehler beim KingKalli-Parsing: {e}", level="error")
            return None

    def _extract_location(self, loc_data):
        if isinstance(loc_data, dict):
            return self.clean_text(loc_data.get("name") or loc_data.get("address", {}).get("addressLocality", "unbekannt"))
        return self.clean_text(str(loc_data)) if loc_data else "unbekannt"


class PdfLinkParser(BaseParser):
    """
    Für statische Seiten, auf denen nur ein PDF-Link angegeben wird.
    Z.B. Bistum Aachen mit „Veranstaltungsflyer“.
    """

    def __init__(self):
        super().__init__(name="PdfLinkParser")

    def extract(self, soup):
        try:
            title = soup.title.string.strip() if soup.title else "PDF-Veranstaltung"
            pdf_tag = soup.find("a", href=lambda h: h and h.endswith(".pdf"))

            if not pdf_tag:
                self.log("Kein PDF-Link gefunden", level="warn")
                return None

            pdf_url = pdf_tag["href"]
            self.log(f"📎 PDF-Event: {title} ({pdf_url})")

            return {
                "title": title,
                "date": "unbekannt",
                "description": f"PDF-Link: {pdf_url}",
                "location": "unbekannt",
                "age_group": ""
            }

        except Exception as e:
            self.log(f"Fehler beim PDF-Link-Parser: {e}", level="error")
            return None


class StaticPageParser(BaseParser):
    """
    Für einfache statische Seiten mit <title>/<h1> und <p>-Absätzen.
    """

    def __init__(self):
        super().__init__(name="StaticPageParser")

    def extract(self, soup):
        try:
            title_tag = soup.find("h1") or soup.find("title")
            title = self.clean_text(title_tag.get_text()) if title_tag else "ohne Titel"

            paragraphs = soup.find_all("p")
            description = "\n".join([self.clean_text(p.get_text()) for p in paragraphs[:5]])

            self.log(f"📄 Statischer Event: {title}")
            return {
                "title": title,
                "date": "unbekannt",
                "description": description,
                "location": "unbekannt",
                "age_group": ""
            }

        except Exception as e:
            self.log(f"Fehler beim StaticPageParser: {e}", level="error")
            return None

class AachenTourismusParser(BaseParser):
    def __init__(self):
        super().__init__(name="AachenTourismusParser")

    def extract(self, soup):
        try:
            # Titel aus H1
            h1 = soup.select_one("h1.page-title")
            title = self.clean_text(h1.get_text()) if h1 else "ohne Titel"

            # Beschreibung aus erstem Absatz im Fließtext
            desc = ""
            desc_block = soup.select_one("div.text--body")
            if desc_block:
                paragraphs = desc_block.find_all("p")
                desc = "\n".join(self.clean_text(p.get_text()) for p in paragraphs)

            # Datum aus Text mit Format: 22.06. | 27.07. | ...
            dates_found = re.findall(r"\d{2}\.\d{2}\.\d{4}", desc)
            date = dates_found[0] if dates_found else "unbekannt"

            return {
                "title": title,
                "date": date,
                "description": desc,
                "location": "Aachen Innenstadt",
                "age_group": ""
            }

        except Exception as e:
            self.log(f"Fehler bei AachenTourismusParser: {e}", level="error")
            return None